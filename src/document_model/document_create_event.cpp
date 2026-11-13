#include "document_model/state.h"
#include "interaction/realm.h"
#include "js/PropertyAndElement.h"
#include "js/Object.h"
#include "js/Realm.h"
#include "js/Wrapper.h"

namespace ruyijs::document_model {
namespace {
bool CreateEvent(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  JS::RootedObject receiver(cx, args.thisv().isObject() ?
      js::CheckedUnwrapStatic(&args.thisv().toObject()) : nullptr);
  Wrapper* document = DocumentReceiver(cx, receiver, &args);
  if (!document) return false;
  if (!argc) return TypeError(cx, "createEvent requires an event type");
  State& owner = *document->owner;
  owner.Observe("Document", "createEvent", int(ApiAccess::Call));
  DomString name;
  if (!String(cx, args[0], &name)) return false;
  {
    JSAutoRealm realm(cx, owner.page);
    JS::RootedObject view(cx, Same(owner.main, document->key) ? owner.page.get() : nullptr);
    if (!owner.interaction.CreateLegacyEvent(name, view, args.rval())) return false;
  }
  return JS_WrapValue(cx, args.rval());
}
}
bool InstallDocumentCreateEvent(State& state) {
  return state.Method("Document", "createEvent", CreateEvent, 1, 0);
}
}

namespace ruyijs::document_model {
namespace {
bool TouchFactory(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  JS::RootedObject receiver(cx, args.thisv().isObject()
      ? js::CheckedUnwrapStatic(&args.thisv().toObject()) : nullptr);
  Wrapper* document = DocumentReceiver(cx, receiver, &args);
  if (!document) return false;
  State& owner = *document->owner;
  const bool list = FunctionSlot(args) != 0;
  owner.Observe("Document", list ? "createTouchList" : "createTouch", int(ApiAccess::Call));
  {
    JSAutoRealm realm(cx, owner.page);
    if (list ? !owner.interaction.CreateLegacyTouchList(args, args.rval())
             : !owner.interaction.CreateLegacyTouch(args, args.rval())) return false;
  }
  return JS_WrapValue(cx, args.rval());
}
}
bool ConfigureTouchFactories(State& state, bool enabled) {
  if (enabled) return state.Method("Document", "createTouch", TouchFactory, 0, 0) &&
                      state.Method("Document", "createTouchList", TouchFactory, 0, 1);
  JS::RootedObject prototype(state.cx, state.Find("Document")->prototype);
  return JS_DeleteProperty(state.cx, prototype, "createTouch") &&
         JS_DeleteProperty(state.cx, prototype, "createTouchList");
}
}
