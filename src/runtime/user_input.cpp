// Host user input (ARCHITECTURE.md, host user input). The sequences follow
// Firefox 158 as recorded on a real Google session: a pointer entering from
// outside, down/up/click with click as a PointerEvent (pointerId 0), and per
// character typing (user_keyboard.cpp).
#include "runtime/user_input.h"
#include "runtime/exception_capture.h"
#include <cstdio>
#include "runtime/input_control.h"
#include "runtime/runtime.h"
#include "runtime/user_input_internal.h"
#include "runtime/browsing_context.h"
#include "runtime/resource_schema.h"
#include "runtime/scheduling_control.h"
#include "runtime/top_level.h"
#include "document_model/realm.h"
#include "document_model/geometry_source.h"
#include "interaction/realm.h"
#include "web_geometry/realm.h"
#include "jsapi.h"
#include "js/CharacterEncoding.h"
#include "js/Conversions.h"
#include "js/PropertyAndElement.h"
#include "js/StableStringChars.h"
#include <array>
#include <algorithm>
#include <cmath>
#include <string>

namespace ruyijs {
namespace {
using user_input::Init;
struct ClickTrace {
  JSContext* cx;
  SchedulingControl& clock;
  bool enabled = NativeInputTraceEnabled();
  const char* phase = "begin";
  const char* previous = nullptr;
  ClickTrace(JSContext* cx, SchedulingControl& clock) : cx(cx), clock(clock) {
    if (enabled) previous = SetNativeInputTracePhase(phase);
  }
  void Phase(const char* next) {
    phase = next;
    if (enabled) SetNativeInputTracePhase(next);
  }
  void Step(const char* next) {
    Phase(next);
    if (enabled) {
      std::fprintf(stderr, "ruyijs-input-phase phase=%s clock_ms=%.3f\n", phase, clock.ClockMilliseconds());
      std::fflush(stderr);
    }
  }
  ~ClickTrace() {
    if (enabled) {
      std::fprintf(stderr, "ruyijs-input-exit phase=%s pending=%d\n", phase, int(JS_IsExceptionPending(cx)));
      std::fflush(stderr);
      SetNativeInputTracePhase(previous);
    }
  }
};
// The active window's mozInnerScreenX/Y for the current host action: a real
// pointer's screenX/Y is its client position plus this origin (Firefox trace
// 20261021-160155: screenX - clientX = mozInnerScreenX = 30).
thread_local struct { double x = 0, y = 0; } gScreen;
bool Pointer(JSContext* cx, JS::HandleObject target, const char* type, double x, double y,
             int button, int buttons, bool bubbles, SchedulingControl& clock, bool* allowed = nullptr) {
  Init init(cx);
  init.Number("clientX", x).Number("clientY", y).Number("screenX", x + gScreen.x).Number("screenY", y + gScreen.y)
      .Number("button", button).Number("buttons", buttons).Flag("bubbles", bubbles)
      .Flag("cancelable", bubbles).Flag("composed", true).Number("pointerId", 0)
      .Text("pointerType", u"mouse").Flag("isPrimary", true).Number("width", 1).Number("height", 1)
      .Number("pressure", buttons ? 0.5 : 0).Number("detail", std::string(type) == "click" ? 1 : 0);
  return init.Send(target, type, clock, allowed);
}
bool Mouse(JSContext* cx, JS::HandleObject target, const char* type, double x, double y,
           int buttons, int detail, bool bubbles, SchedulingControl& clock, bool* allowed = nullptr) {
  Init init(cx);
  init.Number("clientX", x).Number("clientY", y).Number("screenX", x + gScreen.x).Number("screenY", y + gScreen.y)
      .Number("button", 0).Number("buttons", buttons).Number("detail", detail)
      .Flag("bubbles", bubbles).Flag("cancelable", bubbles).Flag("composed", true);
  return init.Send(target, type, clock, allowed);
}
struct ClickReport {
  bool pointerAllowed = true, mouseDelivered = false, mouseAllowed = true;
  bool focusedBeforeHold = false, focusedAfterHold = false, clickAllowed = true;
  double heldMs = 0;
  bool pressedTargetConnectedAfterHold = true, releaseTargetChanged = false;
  bool releasedOnText = false;
};
bool FocusInPath(JSContext* cx, BrowsingContext& owner, const JS::RootedObjectVector& path,
                 bool* found) {
  JS::RootedObject focused(cx);
  if (!owner.document->FocusedElement(&focused)) return false;
  *found = focused && std::find(path.begin(), path.end(), focused.get()) != path.end();
  return true;
}
bool Click(JSContext* cx, BrowsingContext& active, JS::HandleObject target, double hold,
           SchedulingControl& clock, const std::array<double, 4>* point = nullptr,
           ClickReport* report = nullptr, TopLevel* hitRoot = nullptr,
           double viewportX = 0, double viewportY = 0,
           const std::u16string* releaseText = nullptr) {
  ClickTrace trace(cx, clock);
  trace.Step("enter");
  if (point) { gScreen.x = (*point)[2]; gScreen.y = (*point)[3]; }
  else if (!active.environment->InnerScreenOrigin(&gScreen.x, &gScreen.y)) return false;
  std::array<double, 4> rect{};
  bool present = false;
  if (!point && !active.geometry->MeasureElement(target, &rect, &present, false)) JS_ClearPendingException(cx);
  const double x = point ? (*point)[0] : present ? std::round(rect[0] + rect[2] / 2) : 0;
  const double y = point ? (*point)[1] : present ? std::round(rect[1] + rect[3] / 2) : 0;
  JS::RootedObjectVector path(cx);
  if (!document_model::ElementPath(cx, target, &path)) return false;
  JS::RootedObject node(cx);
  if (!Pointer(cx, target, "pointerover", x, y, -1, 0, true, clock)) return false;
  for (size_t i = 0; i < path.length(); ++i) {
    node = path[i];
    if (!Pointer(cx, node, "pointerenter", x, y, -1, 0, false, clock)) return false;
  }
  if (!Mouse(cx, target, "mouseover", x, y, 0, 0, true, clock)) return false;
  for (size_t i = 0; i < path.length(); ++i) {
    node = path[i];
    if (!Mouse(cx, node, "mouseenter", x, y, 0, 0, false, clock)) return false;
  }
  bool pointerAllowed = true, mouseAllowed = true, clickAllowed = true;
  trace.Step("pointer-down");
  if (!Pointer(cx, target, "pointermove", x, y, -1, 0, true, clock) ||
      !Mouse(cx, target, "mousemove", x, y, 0, 0, true, clock) ||
      !Pointer(cx, target, "pointerdown", x, y, 0, 1, true, clock, &pointerAllowed)) return false;
  trace.Step("mouse-down");
  // A cancelled pointerdown suppresses the compatibility mouse events.
  if (pointerAllowed && !Mouse(cx, target, "mousedown", x, y, 1, 1, true, clock, &mouseAllowed)) return false;
  trace.Step("focus");
  if (pointerAllowed && mouseAllowed && !document_model::PointerFocus(cx, target)) return false;
  const double holdStarted = clock.ClockMilliseconds();
  if (report) {
    report->pointerAllowed = pointerAllowed;
    report->mouseDelivered = pointerAllowed;
    report->mouseAllowed = mouseAllowed;
    if (!FocusInPath(cx, active, path, &report->focusedBeforeHold)) return false;
  }
  trace.Step("hold");
  if (releaseText && !releaseText->empty()) {
    JS::RootedObject textTarget(cx, target), parent(cx);
    for (size_t i = path.length(); i > 0; --i) {
      document_model::GeometryNode node;
      JS::RootedObjectVector children(cx);
      JS::RootedValue value(cx, JS::ObjectValue(*path[i - 1]));
      if (!active.document->ReadGeometryNode(value, &node, &parent, &children)) return false;
      const bool button = node.localName == u"button" ||
          std::any_of(node.attributes.begin(), node.attributes.end(), [](const auto& attr) {
            return attr.name == u"role" && attr.value == u"button";
          });
      if (button) { textTarget = path[i - 1]; break; }
    }
    const double until = holdStarted + hold;
    for (;;) {
      trace.Phase("hold-text-read");
      document_model::DomString text;
      JS::RootedValue value(cx, JS::ObjectValue(*textTarget));
      if (!active.document->ReadNodeText(value, &text, 4096)) return false;
      if (text.find(*releaseText) != std::u16string::npos) {
        if (report) report->releasedOnText = true;
        break;
      }
      const double remaining = until - clock.ClockMilliseconds();
      if (remaining <= 0) break;
      trace.Phase("hold-advance");
      clock.Pass(std::min(100.0, remaining));
    }
  } else clock.Pass(hold);
  trace.Step("hold-diagnostics");
  if (report) {
    report->heldMs = clock.ClockMilliseconds() - holdStarted;
    if (!FocusInPath(cx, active, path, &report->focusedAfterHold)) return false;
    report->pressedTargetConnectedAfterHold = active.document->NodeConnected(target);
  }
  JS::RootedObject released(cx, target), clicked(cx, target);
  double upX = x, upY = y;
  trace.Step("release-hit-test");
  if (hitRoot) {
    BrowsingContext* releaseOwner = nullptr;
    upX = viewportX; upY = viewportY;
    if (!ResolvePointerTarget(cx, hitRoot->Active(), &upX, &upY, &released, &releaseOwner)) return false;
    if (!released) { trace.Step("done-no-release-target"); return true; }
    if (!JS_WrapObject(cx, &released)) return false;
    if (report) report->releaseTargetChanged = released != target;
    // Screen coordinates keep the same physical point even if the receiving
    // frame changes while pressed.
    gScreen.x = (*point)[0] + (*point)[2] - upX;
    gScreen.y = (*point)[1] + (*point)[3] - upY;
  }
  trace.Step("pointer-up");
  if (!Pointer(cx, released, "pointerup", upX, upY, 0, 0, true, clock)) return false;
  trace.Step("mouse-up");
  if (pointerAllowed && !Mouse(cx, released, "mouseup", upX, upY, 0, 1, true, clock)) return false;
  trace.Step("click-target");
  if (hitRoot) {
    // Pointer Events determines click's common ancestor in the current DOM,
    // after the up handlers. Removing either endpoint suppresses click, but
    // never prevents pointerup/mouseup from reaching the exposed live target.
    clicked = nullptr;
    if (active.document->NodeConnected(target) && active.document->NodeConnected(released)) {
      JS::RootedObjectVector downPath(cx), upPath(cx);
      if (!document_model::ElementPath(cx, target, &downPath) ||
          !document_model::ElementPath(cx, released, &upPath)) return false;
      for (size_t i = downPath.length(); i > 0; --i) {
        if (std::find(upPath.begin(), upPath.end(), downPath[i - 1]) != upPath.end()) {
          clicked = downPath[i - 1];
          break;
        }
      }
    }
  }
  if (!clicked) { trace.Step("done-no-click-target"); return true; }
  document_model::ClickActivation activation(cx);
  trace.Step("begin-activation");
  if (!document_model::BeginClickActivation(cx, clicked, activation)) return false;
  trace.Step("click-dispatch");
  if (!Pointer(cx, clicked, "click", upX, upY, 0, 0, true, clock, &clickAllowed)) return false;
  trace.Step("end-activation");
  if (!document_model::EndClickActivation(cx, activation, clickAllowed)) return false;
  if (report) report->clickAllowed = clickAllowed;
  trace.Step("activate");
  if (clickAllowed && !document_model::Activate(cx, clicked)) return false;
  trace.Step("done");
  return true;
}
bool Delay(JSContext* cx, JS::HandleObject request, const char* name, double* value) {
  bool present = false;
  JS::RootedValue v(cx);
  if (!JS_HasProperty(cx, request, name, &present)) return false;
  if (!present) return true;
  const double maximum = std::string(name) == "hold_ms" ? 60000 : 10000;
  if (!JS_GetProperty(cx, request, name, &v)) return false;
  if (!v.isNumber() || !(v.toNumber() >= 0) || v.toNumber() > maximum)
    return resource_wire::Error(cx, maximum == 60000
        ? "Input hold must be a number from 0 to 60000 ms"
        : "Input delay must be a number from 0 to 10000 ms", true);
  *value = v.toNumber();
  return true;
}
}  // namespace

bool UserInputRequest(JSContext* cx, TopLevel& top, JS::HandleObject request,
                      SchedulingControl& scheduling, JS::MutableHandleValue result) {
  std::string action, text, key, expression;
  double hold = 80, interval = 60;
  bool hasTarget = false, hasX = false, hasY = false;
  JS::RootedValue diagnostics(cx), releaseValue(cx);
  std::u16string releaseText;
  if (!resource_wire::Fields(cx, request, {"id", "op", "action", "target", "x", "y", "text", "key", "hold_ms", "interval_ms", "diagnostics", "release_on_text"}) ||
      !resource_wire::Property(cx, request, "action", &action, 16, resource_wire::TextKind::ASCII) ||
      !JS_HasProperty(cx, request, "target", &hasTarget) ||
      !JS_HasProperty(cx, request, "x", &hasX) || !JS_HasProperty(cx, request, "y", &hasY) ||
      !JS_GetProperty(cx, request, "diagnostics", &diagnostics) ||
      !JS_GetProperty(cx, request, "release_on_text", &releaseValue) ||
      (hasTarget && !resource_wire::Property(cx, request, "target", &expression, 65536)) ||
      !Delay(cx, request, "hold_ms", &hold) || !Delay(cx, request, "interval_ms", &interval)) return false;
  if ((hasX || hasY) && (action != "click" || hasTarget || !hasX || !hasY))
    return resource_wire::Error(cx, "Coordinate click needs both x/y and no target expression");
  if ((!diagnostics.isUndefined() && !diagnostics.isBoolean()) ||
      (JS::ToBoolean(diagnostics) && !(action == "click" && hasX && hasY)))
    return resource_wire::Error(cx, "Click diagnostics require coordinates and a boolean flag");
  if (!releaseValue.isUndefined()) {
    if (!releaseValue.isString() || action != "click" || !hasX || !hasY)
      return resource_wire::Error(cx, "Text-conditioned release requires a coordinate click and string");
    JS::RootedString text(cx, releaseValue.toString());
    JS::AutoStableStringChars chars(cx);
    if (!chars.initTwoByte(cx, text)) return false;
    if (chars.length() == 0 || chars.length() > 512)
      return resource_wire::Error(cx, "Release text must contain 1 to 512 UTF-16 units", true);
    releaseText.assign(chars.twoByteChars(), chars.length());
  }
  BrowsingContext& active = top.Active();
  JSAutoRealm realm(cx, active.page);
  JS::RootedObject target(cx);
  if (hasTarget) {
    JS::RootedString text(cx, JS_NewStringCopyUTF8N(cx, JS::UTF8Chars(expression.data(), expression.size())));
    JS::AutoStableStringChars characters(cx);
    JS::RootedValue value(cx);
    if (!text || !characters.initTwoByte(cx, text) ||
        !EvaluateHostExpression(cx, "<user-target>", characters.twoByteChars(), characters.length(), &value))
      return false;
    if (!value.isObject()) return resource_wire::Error(cx, "User input target is not an element");
    target = &value.toObject();
  }
  scheduling.Freeze();
  if (action == "click") {
    if (hasX && hasY) {
      JS::RootedValue xValue(cx), yValue(cx);
      if (!JS_GetProperty(cx, request, "x", &xValue) || !JS_GetProperty(cx, request, "y", &yValue)) return false;
      if (!xValue.isNumber() || !yValue.isNumber() ||
          !std::isfinite(xValue.toNumber()) || !std::isfinite(yValue.toNumber()))
        return resource_wire::Error(cx, "Pointer coordinates must be finite numbers", true);
      double x = xValue.toNumber(), y = yValue.toNumber(), screenX = 0, screenY = 0;
      if (!active.environment->InnerScreenOrigin(&screenX, &screenY)) return false;
      screenX += x; screenY += y;
      BrowsingContext* owner = nullptr;
      if (!ResolvePointerTarget(cx, active, &x, &y, &target, &owner)) return false;
      if (!target) { result.setBoolean(false); return true; }
      JSAutoRealm targetRealm(cx, owner->page);
      const std::array<double, 4> point{x, y, screenX - x, screenY - y};
      ClickReport report;
      const bool diagnostic = JS::ToBoolean(diagnostics);
      if (!Click(cx, *owner, target, hold, scheduling, &point, diagnostic ? &report : nullptr,
                 &top, xValue.toNumber(), yValue.toNumber(), &releaseText)) return false;
      if (diagnostic) {
        JS::RootedObject object(cx, JS_NewPlainObject(cx));
        const auto boolean = [&](const char* name, bool bit) {
          JS::RootedValue value(cx, JS::BooleanValue(bit));
          return JS_DefineProperty(cx, object, name, value, JSPROP_ENUMERATE);
        };
        if (!object ||
            !boolean("delivered", true) ||
            !boolean("pointerDownAllowed", report.pointerAllowed) ||
            !boolean("mouseDownDelivered", report.mouseDelivered) ||
            !boolean("mouseDownAllowed", report.mouseAllowed) ||
            !boolean("focusedBeforeHold", report.focusedBeforeHold) ||
            !boolean("focusedAfterHold", report.focusedAfterHold) ||
            !boolean("pressedTargetConnectedAfterHold", report.pressedTargetConnectedAfterHold) ||
            !boolean("releaseTargetChanged", report.releaseTargetChanged) ||
            !boolean("releasedOnText", report.releasedOnText) ||
            !JS_DefineProperty(cx, object, "heldMs", report.heldMs, JSPROP_ENUMERATE) ||
            !boolean("clickAllowed", report.clickAllowed)) return false;
        result.setObject(*object);
        return true;
      }
      result.setBoolean(true);
      return true;
    }
    if (!target) return resource_wire::Error(cx, "click needs a target");
    if (!Click(cx, active, target, hold, scheduling)) return false;
  } else if (action == "type" || action == "press") {
    if (target && !document_model::FocusElement(cx, target)) return false;
    JS::RootedObject focused(cx);
    if (!active.document->ActiveElement(&focused)) return false;
    if (!focused) return resource_wire::Error(cx, "No element has focus");
    if (action == "press") {
      if (!resource_wire::Property(cx, request, "key", &key, 32, resource_wire::TextKind::ASCII) ||
          !user_input::Press(cx, focused, key, scheduling)) return false;
    } else {
      JS::RootedValue raw(cx);
      if (!JS_GetProperty(cx, request, "text", &raw) || !raw.isString())
        return resource_wire::Error(cx, "type needs text");
      JS::RootedString string(cx, raw.toString());
      std::u16string chars(JS_GetStringLength(string), u'\0');
      if (chars.size() > 4096) return resource_wire::Error(cx, "type text exceeds 4096 characters", true);
      if (!JS_CopyStringChars(cx, mozilla::Range<char16_t>(chars.data(), chars.size()), string)) return false;
      for (size_t i = 0; i < chars.size(); ++i) {
        if (i) scheduling.Pass(interval);
        if (!active.document->ActiveElement(&focused) || !focused) break;
        if (!user_input::Character(cx, focused, chars[i], scheduling)) return false;
      }
    }
  } else {
    return resource_wire::Error(cx, "Unknown user input action");
  }
  result.setBoolean(true);
  return true;
}
}  // namespace ruyijs
