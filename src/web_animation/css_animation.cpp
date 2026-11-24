// CSS-created animations use the same effect, timeline and task queue as WAAPI.
// This adds lifecycle and typed events; style interpolation remains the existing
// Web Animations deviation of this runtime.
#include "web_animation/animation_internal.h"
#include "interaction/realm.h"
#include "jsfriendapi.h"
#include "js/Array.h"
#include "js/PropertyAndElement.h"
#include "js/Realm.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

namespace ruyijs::web_animation {
namespace {
bool CssEventTask(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  State& s = *static_cast<State*>(WebKit::Owner(args));
  JS::RootedObject data(cx, &js::GetFunctionNativeReserved(&args.callee(), 1).toObject());
  args.rval().setUndefined();
  JS::RootedValue target(cx), type(cx), name(cx), elapsed(cx);
  std::string eventType, animationName;
  if (!JS_GetElement(cx, data, 0, &target) || !JS_GetElement(cx, data, 1, &type) ||
      !JS_GetElement(cx, data, 2, &name) || !JS_GetElement(cx, data, 3, &elapsed) ||
      !Text(cx, type, &eventType) || !Text(cx, name, &animationName)) return false;
  JS::RootedObject node(cx, &target.toObject());
  return s.events.FireAnimation(node, eventType.c_str(), animationName, elapsed.toNumber(),
      s.scheduling.now ? s.scheduling.now(s.scheduling.context, s.kit.page) : -1);
}
bool QueueCssEvent(State& s, JS::HandleObject a, const char* type, double elapsed) {
  JSContext* cx = s.cx;
  JS::RootedObject effect(cx, EffectOf(a));
  if (!effect) return true;
  JS::RootedValue node(cx, JS::GetReservedSlot(effect, kETarget)), eventType(cx);
  if (!node.isObject()) return true;
  JS::RootedObject data(cx, JS::NewArrayObject(cx, 0));
  JS::RootedValue name(cx, JS::GetReservedSlot(a, kACssName)), time(cx, JS::DoubleValue(elapsed / 1000));
  if (!data || !NewString(cx, type, &eventType) || !JS_DefineElement(cx, data, 0, node, 0) ||
      !JS_DefineElement(cx, data, 1, eventType, 0) || !JS_DefineElement(cx, data, 2, name, 0) ||
      !JS_DefineElement(cx, data, 3, time, 0)) return false;
  JS::RootedObject task(cx, NewTask(s, CssEventTask, data));
  return task && (!s.scheduling.post || s.scheduling.post(s.scheduling.context, task));
}
bool CssBoundary(JSContext* cx, unsigned argc, JS::Value* vp) {
  auto args = JS::CallArgsFromVp(argc, vp);
  State& s = *static_cast<State*>(WebKit::Owner(args));
  JS::RootedObject a(cx, &js::GetFunctionNativeReserved(&args.callee(), 1).toObject());
  const bool current = JS::GetReservedSlot(a, kACssTask) == JS::ObjectValue(args.callee());
  args.rval().setUndefined();
  if (!current) return true;
  JS::SetReservedSlot(a, kACssTask, JS::NullValue());
  return UpdateFinished(s, a, false, false);
}
bool SameName(State& s, JS::HandleObject a, const std::string& name) {
  JS::RootedValue value(s.cx, JS::GetReservedSlot(a, kACssName));
  std::string previous;
  return Text(s.cx, value, &previous) && previous == name;
}
}

bool UpdateCssEvents(State& s, JS::HandleObject a, bool cancel) {
  if (JS::GetClass(a) != &kCssAnimationClass || JS::GetReservedSlot(a, kACssName).isNull()) return true;
  JS::SetReservedSlot(a, kACssTask, JS::NullValue());
  JS::RootedObject effect(s.cx, EffectOf(a));
  if (!effect) return true;
  const auto timing = ReadTiming(effect);
  const auto local = CurrentTime(a);
  const double active = local ? std::clamp(*local - timing.delay, 0.0, timing.ActiveDuration()) : 0;
  if (cancel) {
    const bool ended = Flag(a, kACssEnded);
    SetFlag(a, kACssEnded, true);
    return ended || !local || QueueCssEvent(s, a, "animationcancel", active);
  }
  if (Flag(a, kACssEnded) || !local || Pending(a)) return true;
  const bool started = *local >= std::max(timing.delay, 0.0);
  if (started && !Flag(a, kACssStarted)) {
    SetFlag(a, kACssStarted, true);
    if (!QueueCssEvent(s, a, "animationstart", std::min(std::max(-timing.delay, 0.0), timing.ActiveDuration())))
      return false;
  }
  const double duration = timing.IterationDuration();
  double last = JS::GetReservedSlot(a, kACssIteration).toDouble();
  if (started && duration > 0) {
    const double iteration = std::floor(active / duration);
    for (size_t budget = 0; last < iteration && (last + 1) * duration < timing.ActiveDuration() && budget < 1000; ++budget) {
      ++last;
      if (!QueueCssEvent(s, a, "animationiteration", last * duration)) return false;
    }
    JS::SetReservedSlot(a, kACssIteration, JS::DoubleValue(last));
  }
  if (started && *local >= timing.delay + timing.ActiveDuration()) {
    SetFlag(a, kACssEnded, true);
    return QueueCssEvent(s, a, "animationend", timing.ActiveDuration());
  }
  if (!std::strcmp(PlayState(a), "running") && Rate(a) > 0 && s.scheduling.postDelayed) {
    double boundary = timing.delay;
    if (started) boundary = duration > 0
        ? std::min(timing.delay + (last + 1) * duration, timing.delay + timing.ActiveDuration())
        : timing.delay + timing.ActiveDuration();
    const double delay = (boundary - *local) / Rate(a);
    if (std::isfinite(delay) && delay > 0) {
      JS::RootedObject task(s.cx, NewTask(s, CssBoundary, a));
      if (!task) return false;
      JS::SetReservedSlot(a, kACssTask, JS::ObjectValue(*task));
      return s.scheduling.postDelayed(s.scheduling.context, task, delay);
    }
  }
  return true;
}

bool SampleCss(State& s) {
  if (s.samplingCss || !s.css.revision || !s.css.read) return true;
  const uint64_t revision = s.css.revision(s.css.context);
  if (revision == s.cssRevision) return true;
  s.samplingCss = true;
  struct Guard { bool& flag; ~Guard() { flag = false; } } guard{s.samplingCss};
  JSContext* cx = s.cx;
  JSAutoRealm realm(cx, s.kit.page);
  JS::RootedObjectVector targets(cx);
  std::vector<CssAnimationInput> inputs;
  if (!s.css.read(s.css.context, &targets, &inputs)) return false;
  JS::RootedObject old(cx, s.cssAnimations), current(cx, JS::NewArrayObject(cx, 0));
  uint32_t oldLength = 0;
  if (!current || (old && !JS::GetArrayLength(cx, old, &oldLength))) return false;
  std::vector<bool> used(oldLength, false);
  uint32_t count = 0;
  for (const auto& input : inputs) {
    if (input.target >= targets.length()) continue;
    JS::RootedObject target(cx, targets[input.target]), a(cx), effect(cx);
    for (uint32_t i = oldLength; i-- > 0;) {
      if (used[i]) continue;
      JS::RootedValue value(cx);
      if (!JS_GetElement(cx, old, i, &value)) return false;
      JS::RootedObject candidate(cx, &value.toObject()), e(cx, EffectOf(candidate));
      if (e && JS::GetReservedSlot(e, kETarget) == JS::ObjectValue(*target) && SameName(s, candidate, input.name)) {
        a = candidate; effect = e; used[i] = true; break;
      }
    }
    const bool fresh = !a;
    if (fresh) {
      JS::RootedObject proto(cx, s.keyframeEffect.prototype), frames(cx, JS::NewArrayObject(cx, 0));
      effect = NewEffectObject(s, proto);
      if (!effect || !frames || !StoreTiming(effect, input.timing)) return false;
      JS::SetReservedSlot(effect, kETarget, JS::ObjectValue(*target));
      JS::SetReservedSlot(effect, kEFrames, JS::ObjectValue(*frames));
      JS::RootedObject document(cx), timeline(cx), animationProto(cx, s.cssAnimation.prototype);
      if (!s.dom.document(s.dom.context, target, &document) || !DocumentTimeline(s, document, &timeline) ||
          !NewAnimation(s, animationProto, effect, timeline, &a, true)) return false;
      JS::RootedValue name(cx);
      if (!NewString(cx, input.name, &name)) return false;
      JS::SetReservedSlot(a, kACssName, name);
      if (!Play(s, a, true, "CSS animation: ")) return false;
    } else if (!StoreTiming(effect, input.timing)) return false;
    if (fresh || Flag(a, kACssPaused) != input.paused) {
      SetFlag(a, kACssPaused, input.paused);
      if (input.paused) { if (!Pause(s, a, "CSS animation: ")) return false; }
      else if (!fresh && !Play(s, a, false, "CSS animation: ")) return false;
    }
    if (!UpdateFinished(s, a, false, false)) return false;
    JS::RootedValue value(cx, JS::ObjectValue(*a));
    if (!JS_DefineElement(cx, current, count++, value, 0)) return false;
  }
  for (uint32_t i = 0; i < oldLength; ++i) {
    if (used[i]) continue;
    JS::RootedValue value(cx);
    if (!JS_GetElement(cx, old, i, &value)) return false;
    JS::RootedObject a(cx, &value.toObject());
    if (!Cancel(s, a)) return false;
  }
  s.cssAnimations = current;
  s.cssRevision = s.css.revision(s.css.context);
  return true;
}
}
