// Programmatic selection changes queue the native select event on the original
// element. The callback owns its target through a traced function slot.
#include "document_model/html_input.h"
#include "browser_environment/environment.h"
#include "interaction/realm.h"
#include "jsfriendapi.h"
#include "js/Object.h"
#include "js/Realm.h"
#include "js/Wrapper.h"

namespace ruyijs::document_model {
namespace {
bool FireSelect(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  JS::RootedObject target(cx, js::CheckedUnwrapStatic(
      &js::GetFunctionNativeReserved(&args.callee(), 0).toObject()));
  // callee aliases the return slot: capture the traced target first.
  args.rval().setUndefined();
  if (!target) return true;
  auto* entry = static_cast<Wrapper*>(JS::GetReservedSlot(target, 0).toPrivate());
  if (!entry || entry->dead || !entry->owner) return true;
  JSAutoRealm realm(cx, entry->owner->page);
  if (!JS_WrapObject(cx, &target)) return false;
  return entry->owner->interaction.Fire(target, "select", true, false);
}
}
bool QueueInputSelect(Wrapper& entry) {
  State& state = *entry.owner;
  JSContext* cx = state.cx;
  JS::RootedFunction function(cx, js::NewFunctionWithReserved(cx, FireSelect, 0, 0, "Input select task"));
  if (!function) return false;
  JS::RootedObject callback(cx, JS_GetFunctionObject(function)), target(cx, entry.object);
  if (!JS_WrapObject(cx, &target)) return false;
  js::SetFunctionNativeReserved(callback, 0, JS::ObjectValue(*target));
  return state.environment.PostTask(callback);
}
bool UpdateInputSelection(Wrapper& entry, uint32_t start, uint32_t end,
                          DomStringView direction, int field) {
  State& state = *entry.owner;
  uint32_t oldStart = 0, oldEnd = 0, nextStart = 0, nextEnd = 0;
  DomString oldDirection, nextDirection;
  if (!state.Check(state.model.InputSelection(entry.key, &oldStart, &oldEnd, &oldDirection)) ||
      !state.Check(state.model.SetInputSelection(entry.key, start, end, direction, field)) ||
      !state.Check(state.model.InputSelection(entry.key, &nextStart, &nextEnd, &nextDirection))) return false;
  return (oldStart == nextStart && oldEnd == nextEnd && oldDirection == nextDirection) || QueueInputSelect(entry);
}
}
