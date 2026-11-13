#include "interaction/touch.h"
#include "interaction/event_keyboard.h"
#include "interaction/event_creation.h"
#include "runtime/native_constructor_trace.h"
#include "js/Conversions.h"
#include "js/Object.h"
#include "js/PropertyAndElement.h"
#include "js/Realm.h"
#include "js/Wrapper.h"
#include <cmath>
#include <limits>

namespace ruyijs::interaction {
const JSClass kTouchClass = {"Touch", JSCLASS_HAS_RESERVED_SLOTS(kTouchSlotCount)};
bool IsTouch(JSObject* object) {
  return object && JS::GetClass(object) == &kTouchClass &&
      JS::GetReservedSlot(object, kTouchOriginalTarget).isObjectOrNull();
}
JSObject* TouchReceiver(JSContext* cx, JS::HandleValue value) {
  JSObject* object = value.isObject() ? js::CheckedUnwrapStatic(&value.toObject()) : nullptr;
  if (IsTouch(object)) return object;
  Error(cx, "TypeError", "Touch receiver is incompatible");
  return nullptr;
}
bool TouchConstructorPrototype(JSContext* cx, const JS::CallArgs& args,
                               bool event, JS::MutableHandleObject result) {
  JS::RootedObject target(cx, &args.newTarget().toObject());
  JS::RootedValue value(cx);
  if (!JS_GetProperty(cx, target, "prototype", &value)) return false;
  if (value.isObject()) { result.set(&value.toObject()); return true; }
  JS::Realm* realm = JS::GetFunctionRealm(cx, target);
  if (!realm) return false;
  JSObject* global = JS::GetRealmGlobalOrNull(realm);
  State* owner = activeState;
  while (owner && (owner->cx != cx || owner->page != global)) owner = owner->previous;
  if (!owner) return Error(cx, "TypeError", "Touch factory realm is not installed");
  if (event) {
    JSAutoRealm enter(cx, owner->page);
    if (!ReadInstalledEventPrototype(*owner, Iface::Touch, result)) return false;
  } else result.set(owner->touchPrototype);
  return result && JS_WrapObject(cx, result);
}
namespace {
struct Field { const char* name; unsigned slot; bool floating; };
constexpr Field kFields[] = {
  {"clientX", kTouchClientX, false}, {"clientY", kTouchClientY, false},
  {"force", kTouchForce, true}, {"identifier", kTouchIdentifier, false},
  {"pageX", kTouchPageX, false}, {"pageY", kTouchPageY, false},
  {"radiusX", kTouchRadiusX, true}, {"radiusY", kTouchRadiusY, true},
  {"rotationAngle", kTouchRotation, true}, {"screenX", kTouchScreenX, false},
  {"screenY", kTouchScreenY, false}
};
bool Number(JSContext* cx, JS::HandleValue input, const Field& field,
            JS::MutableHandleValue output) {
  if (!field.floating) {
    int32_t value;
    if (!JS::ToInt32(cx, input, &value)) return false;
    output.setInt32(value); return true;
  }
  double value;
  if (!JS::ToNumber(cx, input, &value)) return false;
  const float rounded = static_cast<float>(value);
  if (!std::isfinite(rounded))
    return Error(cx, "TypeError", "Touch values require finite floats");
  if (field.slot == kTouchRadiusX || field.slot == kTouchRadiusY) {
    // The donor stores a finite float in int32_t; its native out-of-range
    // conversion yields INT32_MIN (independent precision probe), not modulo.
    const int32_t radius = rounded >= 2147483648.0f || rounded < -2147483648.0f
        ? std::numeric_limits<int32_t>::min() : static_cast<int32_t>(rounded);
    output.setInt32(radius);
  } else output.setDouble(double(rounded));
  return true;
}
}
bool CreateTouchForInput(JSContext* cx, JS::HandleObject target,
                         JS::HandleObject dict, JS::MutableHandleObject result) {
  State* state = Owner(cx, target, false);
  if (!state || !state->touchPrototype)
    return Error(cx, "TypeError", "Touch input target is not installed");
  JS::RootedValueArray<kTouchSlotCount> values(cx);
  JS::RootedValue input(cx);
  for (const auto& field : kFields) {
    if (!JS_GetProperty(cx, dict, field.name, &input)) return false;
    if (input.isUndefined()) input.setInt32(field.slot == kTouchIdentifier ? 1 : 0);
    if (!Number(cx, input, field, values[field.slot])) return false;
  }
  values[kTouchTarget].setObject(*target);
  values[kTouchOriginalTarget].setObject(*target);
  JS::RootedObject prototype(cx, state->touchPrototype);
  result.set(JS_NewObjectWithGivenProto(cx, &kTouchClass, prototype));
  if (!result) return false;
  for (unsigned slot = 0; slot < kTouchSlotCount; ++slot)
    JS::SetReservedSlot(result, slot, values[slot]);
  return true;
}
bool TouchValueConstructor(JSContext* cx, unsigned argc, JS::Value* vp) {
  const auto args = JS::CallArgsFromVp(argc, vp);
  NativeConstructorTrace trace(cx, args);
  if (!args.isConstructing()) return Error(cx, "TypeError", "Touch requires new");
  JS::RootedObject prototype(cx);
  if (!TouchConstructorPrototype(cx, args, false, &prototype)) return false;
  if (!argc || !args[0].isObject()) return Error(cx, "TypeError", "Touch requires a dictionary");
  JS::RootedObject dict(cx, &args[0].toObject());
  JS::RootedValueArray<kTouchSlotCount> values(cx);
  JS::RootedValue input(cx);
  for (const auto& field : kFields) {
    if (!JS_GetProperty(cx, dict, field.name, &input)) return false;
    if (input.isUndefined()) {
      if (field.slot == kTouchIdentifier) return Error(cx, "TypeError", "Touch requires identifier");
      input.setInt32(0);
    }
    if (!Number(cx, input, field, values[field.slot])) return false;
  }
  if (!JS_GetProperty(cx, dict, "target", &input)) return false;
  JS::RootedObject target(cx, input.isObject() ? js::CheckedUnwrapStatic(&input.toObject()) : nullptr);
  State* target_owner = target ? Owner(cx, target, false) : nullptr;
  if (!target_owner || !target_owner->target(target))
    return Error(cx, "TypeError", "Touch requires an EventTarget target");
  values[kTouchTarget].set(input);
  values[kTouchOriginalTarget].set(input);
  JS::RootedObject object(cx, JS_NewObjectWithGivenProto(cx, &kTouchClass, prototype));
  if (!object) return false;
  for (unsigned slot = 0; slot < kTouchSlotCount; ++slot)
    JS::SetReservedSlot(object, slot, values[slot]);
  State* state = RealmState(cx);
  if (state) state->Observe("Touch", "constructor", int(ApiAccess::Construct));
  args.rval().setObject(*object);
  return trace.Finish(true);
}
}

namespace ruyijs::interaction {
bool Realm::CreateLegacyTouch(const JS::HandleValueArray& args, JS::MutableHandleValue result) {
  State& state = *state_;
  JSContext* cx = state.cx;
  JSAutoRealm enter(cx, state.page);
  JS::RootedValueArray<13> input(cx);
  for (unsigned i = 0; i < 13; ++i) {
    input[i].set(i < args.length() ? args[i].get() : JS::UndefinedValue());
    if (!JS_WrapValue(cx, input[i])) return false;
  }
  JS::RootedValue view(cx);
  if (!KeyboardView(cx, input[0], &view)) return false;
  JS::RootedValue target(cx, input[1]);
  if (target.isNullOrUndefined()) target.setNull();
  else {
    JS::RootedObject raw(cx, target.isObject()
        ? js::CheckedUnwrapStatic(&target.toObject()) : nullptr);
    State* owner = raw ? Owner(cx, raw, false) : nullptr;
    if (!owner || !owner->target(raw))
      return Error(cx, "TypeError", "createTouch target requires an EventTarget");
  }
  JS::RootedValueArray<kTouchSlotCount> values(cx);
  const unsigned slots[] = {kTouchIdentifier, kTouchPageX, kTouchPageY,
      kTouchScreenX, kTouchScreenY, kTouchClientX, kTouchClientY,
      kTouchRadiusX, kTouchRadiusY, kTouchRotation, kTouchForce};
  for (unsigned i = 0; i < 11; ++i) {
    JS::RootedValue value(cx, input[i+2]);
    if (value.isUndefined()) value.setInt32(0);
    if (i < 9) {
      int32_t converted;
      if (!JS::ToInt32(cx, value, &converted)) return false;
      values[slots[i]].setInt32(converted);
    } else {
      Field field{"", slots[i], true};
      if (!Number(cx, value, field, values[slots[i]])) return false;
    }
  }
  values[kTouchTarget].set(target);
  values[kTouchOriginalTarget].set(target);
  JS::RootedObject prototype(cx, state.touchPrototype);
  JS::RootedObject object(cx, JS_NewObjectWithGivenProto(cx, &kTouchClass, prototype));
  if (!object) return false;
  for (unsigned i = 0; i < kTouchSlotCount; ++i) JS::SetReservedSlot(object, i, values[i]);
  result.setObject(*object);
  return true;
}
}
