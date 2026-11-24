#include "runtime/web_kit.h"
#include "resource_network/state.h"
#include "resource_network/body_acquire.h"
#include "resource_network/xhr.h"
#include "resource_network/abort.h"
#include "runtime/page_helpers.h"
#include "runtime/native_constructor_trace.h"
#include "jsfriendapi.h"
#include "js/PropertyAndElement.h"
#include "js/Conversions.h"
#include "js/CharacterEncoding.h"
#include "js/String.h"
#include "js/Proxy.h"
#include "js/Class.h"
#include "js/PropertyDescriptor.h"
#include "js/Wrapper.h"
#include <string>

namespace ruyijs::resource_network {
// Instance identity for localStorage and sessionStorage. Slot 0 keeps the one
// StorageArea this page owns, slot 1 selects which area; both are set by the
// unique installer and never by script.
static const JSClass kStorageClassDefinition = PROXY_CLASS_DEF("Storage", JSCLASS_HAS_RESERVED_SLOTS(2));
const JSClass kStorageClass = kStorageClassDefinition;

State::~State() { DetachBodyOperations(*this); DetachXhrs(*this); DetachAbortSignals(*this); Release(arena); if (owns_store) DeleteStorage(store); }

enum class StorageOp { GetItem, SetItem, RemoveItem, Clear, Key, Length };

// The native function holds the owning State in reserved slot 0, so a method
// reports through that realm's port and reads the one store it owns.
static State* Owner(const JS::CallArgs& args) {
  return static_cast<State*>(
      js::GetFunctionNativeReserved(&args.callee(), 0).toPrivate());
}
// The installed member name of each Storage operation; static names only.
static const char* StorageName(StorageOp op) {
  switch (op) {
    case StorageOp::GetItem: return "getItem";
    case StorageOp::SetItem: return "setItem";
    case StorageOp::RemoveItem: return "removeItem";
    case StorageOp::Clear: return "clear";
    case StorageOp::Key: return "key";
    case StorageOp::Length: return "length";
  }
  return "";
}
static StorageOp OpOf(const JS::CallArgs& args) {
  return StorageOp(js::GetFunctionNativeReserved(&args.callee(), 1).toInt32());
}
static JSObject* Native(State& s, JSNative callback, const char* name,
                        unsigned length, StorageOp op, unsigned flags = 0) {
  JS::RootedFunction fn(s.cx, js::NewFunctionWithReserved(s.cx, callback, length, flags, name));
  if (!fn) return nullptr;
  JS::RootedObject object(s.cx, JS_GetFunctionObject(fn));
  js::SetFunctionNativeReserved(object, 0, JS::PrivateValue(&s));
  js::SetFunctionNativeReserved(object, 1, JS::Int32Value(int32_t(op)));
  return object;
}

// A prototype method requires a real Storage receiver, so calling it on a plain
// object throws instead of reading another page's state.
static bool Which(JSContext* cx, const JS::CallArgs& args, bool* session, StorageArea** area) {
  if (args.thisv().isObject()) {
    JSObject* receiver = js::CheckedUnwrapStatic(&args.thisv().toObject());
    if (receiver && JS::GetClass(receiver) == &kStorageClass) {
      *session = js::GetProxyReservedSlot(receiver, 1).toInt32() != 0;
      *area = static_cast<StorageArea*>(js::GetProxyReservedSlot(receiver, 0).toPrivate());
      return true;
    }
  }
  WebKit::FailBrand(cx, args, "Storage");
  return false;
}

// Storage keys and values are DOMStrings (Firefox), held as UTF-8 by the store,
// the same encoding profile/host imports use. A lone surrogate becomes U+FFFD.
static bool Text(JSContext* cx, JS::HandleValue input, std::string* result) {
  JS::RootedString text(cx, JS::ToString(cx, input));
  if (!text) return false;
  JSLinearString* linear = JS_EnsureLinearString(cx, text);
  if (!linear) return false;
  // Sized, not NUL-terminated: a value may contain U+0000.
  result->resize(JS::GetDeflatedUTF8StringLength(linear));
  JS::DeflateStringToUTF8Buffer(linear, mozilla::Span<char>(result->data(), result->size()));
  return true;
}
static bool Text(JSContext* cx, const std::string& source, JS::MutableHandleValue result) {
  JSString* text = JS_NewStringCopyUTF8N(cx, JS::UTF8Chars(source.data(), source.size()));
  if (!text) return false;
  result.setString(text);
  return true;
}

static bool Access(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  bool session = false;
  StorageArea* area = nullptr;
  if (!Which(cx, args, &session, &area)) return false;
  // Reported after receiver validation, so an invalid receiver still throws
  // from the same place and records nothing.
  const StorageOp operation = OpOf(args);
  Owner(args)->Observe("Storage", StorageName(operation),
                       operation == StorageOp::Length ? int(ApiAccess::Read)
                                                      : int(ApiAccess::Call));
  std::string key, value;
  bool found = false;
  switch (operation) {
    case StorageOp::GetItem:
      if (!argc || !Text(cx, args[0], &key)) return Error(cx, "Storage.getItem requires a key");
      if (!Report(cx, StorageGet(area, session, key, &value, &found))) return false;
      if (!found) { args.rval().setNull(); return true; }
      return Text(cx, value, args.rval());
    case StorageOp::SetItem:
      if (argc < 2 || !Text(cx, args[0], &key) || !Text(cx, args[1], &value))
        return Error(cx, "Storage.setItem requires a key and value");
      if (!Report(cx, StorageSet(area, session, key, value))) return false;
      args.rval().setUndefined();
      return true;
    case StorageOp::RemoveItem:
      if (!argc || !Text(cx, args[0], &key)) return Error(cx, "Storage.removeItem requires a key");
      if (!Report(cx, StorageRemove(area, session, key))) return false;
      args.rval().setUndefined();
      return true;
    case StorageOp::Clear:
      if (!Report(cx, StorageClear(area, session))) return false;
      args.rval().setUndefined();
      return true;
    case StorageOp::Key: {
      double index = 0;
      if (!argc || !JS::ToNumber(cx, args[0], &index))
        return Error(cx, "Storage.key requires an index");
      // A negative or non-finite index is out of range, never a wrapped offset.
      if (!(index >= 0) || index != index) { args.rval().setNull(); return true; }
      if (!Report(cx, StorageKeyAt(area, session, size_t(index), &key, &found))) return false;
      if (!found) { args.rval().setNull(); return true; }
      return Text(cx, key, args.rval());
    }
    case StorageOp::Length: {
      size_t length = 0;
      if (!Report(cx, StorageLength(area, session, &length))) return false;
      args.rval().setInt32(int32_t(length));
      return true;
    }
  }
  return Error(cx, "Unknown Storage operation");
}

static bool StorageConstructor(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  NativeConstructorTrace trace(cx, args);
  return Error(cx, "Illegal constructor.");
}

namespace {
char storageFamily;
StorageArea* Store(JS::HandleObject proxy) {
  return static_cast<StorageArea*>(js::GetProxyReservedSlot(proxy, 0).toPrivate());
}
bool Session(JS::HandleObject proxy) {
  return js::GetProxyReservedSlot(proxy, 1).toInt32() != 0;
}
JSObject* Expando(JS::HandleObject proxy) { return &js::GetProxyPrivate(proxy).toObject(); }
bool Key(JSContext* cx, JS::HandleId id, std::string* key) {
  JS::RootedValue value(cx);
  return JS_IdToValue(cx, id, &value) && Text(cx, value, key);
}
// Storage has no LegacyOverrideBuiltIns: existing prototype members win over
// a stored name, while assignments still invoke the named setter.
bool Visible(JSContext* cx, JS::HandleObject proxy, JS::HandleId id, bool* visible) {
  JS::RootedObject prototype(cx);
  bool inherited = false;
  if (!JS_GetPrototype(cx, proxy, &prototype) ||
      (prototype && !JS_HasPropertyById(cx, prototype, id, &inherited))) return false;
  *visible = !inherited;
  return true;
}
class StorageHandler final : public js::BaseProxyHandler {
 public:
  constexpr StorageHandler() : BaseProxyHandler(&storageFamily) {}
  bool getOwnPropertyDescriptor(JSContext* cx, JS::HandleObject proxy, JS::HandleId id,
      JS::MutableHandle<mozilla::Maybe<JS::PropertyDescriptor>> desc) const override {
    JS::RootedObject expando(cx, Expando(proxy));
    if (id.isSymbol()) return JS_GetOwnPropertyDescriptorById(cx, expando, id, desc);
    desc.reset();
    bool visible = false, found = false;
    std::string key, value;
    if (!Visible(cx, proxy, id, &visible)) return false;
    if (!visible) return true;
    if (!Key(cx, id, &key) || !Report(cx, StorageGet(Store(proxy), Session(proxy), key, &value, &found))) return false;
    if (!found) return true;
    JS::RootedValue text(cx);
    if (!Text(cx, value, &text)) return false;
    desc.set(mozilla::Some(JS::PropertyDescriptor::Data(text,
        {JS::PropertyAttribute::Enumerable, JS::PropertyAttribute::Configurable,
         JS::PropertyAttribute::Writable})));
    return true;
  }
  bool defineProperty(JSContext* cx, JS::HandleObject proxy, JS::HandleId id,
      JS::Handle<JS::PropertyDescriptor> desc, JS::ObjectOpResult& result) const override {
    JS::RootedObject expando(cx, Expando(proxy));
    if (id.isSymbol()) return JS_DefinePropertyById(cx, expando, id, desc, result);
    if (desc.isAccessorDescriptor()) return result.failNotDataDescriptor();
    JS::RootedValue input(cx, desc.hasValue() ? desc.value() : JS::UndefinedValue());
    std::string key, value;
    return Key(cx, id, &key) && Text(cx, input, &value) &&
        Report(cx, StorageSet(Store(proxy), Session(proxy), key, value)) && result.succeed();
  }
  bool ownPropertyKeys(JSContext* cx, JS::HandleObject proxy,
                       JS::MutableHandleIdVector keys) const override {
    size_t length = 0;
    if (!Report(cx, StorageLength(Store(proxy), Session(proxy), &length))) return false;
    for (size_t index = 0; index < length; ++index) {
      bool found = false, visible = false;
      std::string key;
      if (!Report(cx, StorageKeyAt(Store(proxy), Session(proxy), index, &key, &found))) return false;
      if (!found) continue;
      JS::RootedString text(cx, JS_NewStringCopyUTF8N(cx, JS::UTF8Chars(key.data(), key.size())));
      JS::RootedId id(cx);
      if (!text || !JS_StringToId(cx, text, &id) || !Visible(cx, proxy, id, &visible)) return false;
      if (visible && !keys.append(id)) return false;
    }
    JS::RootedObject expando(cx, Expando(proxy));
    JS::RootedIdVector symbols(cx);
    return js::GetPropertyKeys(cx, expando, JSITER_OWNONLY | JSITER_HIDDEN | JSITER_SYMBOLS,
                               &symbols) && keys.appendAll(symbols);
  }
  bool delete_(JSContext* cx, JS::HandleObject proxy, JS::HandleId id,
               JS::ObjectOpResult& result) const override {
    JS::RootedObject expando(cx, Expando(proxy));
    if (id.isSymbol()) return JS_DeletePropertyById(cx, expando, id, result);
    std::string key;
    return Key(cx, id, &key) && Report(cx, StorageRemove(Store(proxy), Session(proxy), key)) && result.succeed();
  }
  bool set(JSContext* cx, JS::HandleObject proxy, JS::HandleId id, JS::HandleValue input,
           JS::HandleValue receiver, JS::ObjectOpResult& result) const override {
    if (id.isSymbol() || !receiver.isObject() || &receiver.toObject() != proxy)
      return BaseProxyHandler::set(cx, proxy, id, input, receiver, result);
    std::string key, value;
    return Key(cx, id, &key) && Text(cx, input, &value) &&
        Report(cx, StorageSet(Store(proxy), Session(proxy), key, value)) && result.succeed();
  }
  bool getPrototypeIfOrdinary(JSContext* cx, JS::HandleObject proxy, bool* ordinary,
                              JS::MutableHandleObject proto) const override {
    *ordinary = true;
    return JS_GetPrototype(cx, proxy, proto);
  }
  bool preventExtensions(JSContext*, JS::HandleObject, JS::ObjectOpResult& result) const override {
    return result.failCantPreventExtensions();
  }
  bool isExtensible(JSContext*, JS::HandleObject, bool* extensible) const override {
    *extensible = true;
    return true;
  }
  const char* className(JSContext*, JS::HandleObject) const override { return "Storage"; }
};
const StorageHandler storageHandler;
}  // namespace

// One instance per area, created by this installer from the realm's own
// prototype; script cannot construct another.
static bool Instance(State& s, JS::HandleObject prototype, const char* name, bool session) {
  JSContext* cx = s.cx;
  JS::RootedObject expando(cx, JS_NewObjectWithGivenProto(cx, nullptr, nullptr));
  if (!expando) return false;
  JS::RootedValue priv(cx, JS::ObjectValue(*expando));
  js::ProxyOptions options;
  options.setClass(&kStorageClass);
  JS::RootedObject object(cx, js::NewProxyObject(cx, &storageHandler, priv, prototype, options));
  if (!object) return false;
  js::SetProxyReservedSlot(object, 0, JS::PrivateValue(s.store));
  js::SetProxyReservedSlot(object, 1, JS::Int32Value(session ? 1 : 0));
  return JS_DefineProperty(cx, s.page, name, object, JSPROP_ENUMERATE);
}

static bool InstallStorageInterface(State& s, PageHelpers& helpers) {
  JSContext* cx = s.cx;
  JS::RootedObject prototype(cx, JS_NewPlainObject(cx));
  JS::RootedObject constructor(cx, Native(s, StorageConstructor, "Storage", 0,
                                          StorageOp::Length, JSFUN_CONSTRUCTOR));
  if (!prototype || !constructor ||
      !JS_DefineProperty(cx, constructor, "prototype", prototype,
                         JSPROP_READONLY | JSPROP_PERMANENT) ||
      !JS_DefineProperty(cx, prototype, "constructor", constructor, 0) ||
      !Tag(cx, prototype, "Storage")) return false;
  struct Definition { const char* name; unsigned length; StorageOp op; };
  static const Definition definitions[] = {
    {"getItem", 1, StorageOp::GetItem}, {"setItem", 2, StorageOp::SetItem},
    {"removeItem", 1, StorageOp::RemoveItem}, {"clear", 0, StorageOp::Clear},
    {"key", 1, StorageOp::Key}
  };
  for (const auto& definition : definitions) {
    JS::RootedObject method(cx, Native(s, Access, definition.name, definition.length, definition.op));
    if (!method || !JS_DefineProperty(cx, prototype, definition.name, method, JSPROP_ENUMERATE) ||
        !helpers.Member(method, "Storage", definition.name, "call")) return false;
  }
  JS::RootedObject length(cx, Native(s, Access, "get length", 0, StorageOp::Length));
  if (!length || !JS_DefineProperty(cx, prototype, "length", length, nullptr, JSPROP_ENUMERATE) ||
      !helpers.Member(length, "Storage", "get length", "get") ||
      !helpers.Constructor("Storage", constructor) ||
      !JS_DefineProperty(cx, s.page, "Storage", constructor, 0)) return false;
  return Instance(s, prototype, "localStorage", false) &&
         Instance(s, prototype, "sessionStorage", true);
}

bool InstallStorage(State& s, PageHelpers& helpers) {
  // A child realm's view already points at the owning realm's store and must
  // keep sharing it; only the realm that owns the store creates it.
  if (!s.store && !Report(s.cx, NewStorage(&s.store))) return false;
  JSContext* cx = s.cx;
  JS::RootedValue document(cx), prototype(cx);
  JS::RootedObject constructor(cx), proto(cx);
  if (!JS_GetProperty(cx, s.page, "Document", &document) ||
      !document.isObject()) return false;
  constructor = &document.toObject();
  if (!JS_GetProperty(cx, constructor, "prototype", &prototype) || !prototype.isObject())
    return false;
  proto = &prototype.toObject();
  return InstallCookie(s,helpers,proto) &&
         InstallStorageInterface(s, helpers) && InstallCookieStore(s,helpers);
}
}
