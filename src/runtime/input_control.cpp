// Shared C/Python host entry. The Interaction owner creates and dispatches input.
#include "runtime/input_control.h"
#include "runtime/runtime.h"
#include "runtime/scheduling_control.h"
#include "runtime/resource_schema.h"
#include "runtime/top_level.h"
#include "interaction/realm.h"
#include "document_model/realm.h"
#include "document_model/layout_source.h"
#include "web_geometry/realm.h"
#include "jsapi.h"
#include "js/PropertyAndElement.h"
#include "js/Realm.h"
#include "js/StableStringChars.h"
#include <array>
#include <cmath>
#include <vector>

namespace ruyijs {
namespace {
bool Coordinate(JSContext* cx, JS::HandleObject request, const char* name, double* out) {
  JS::RootedValue value(cx);
  if (!JS_GetProperty(cx, request, name, &value)) return false;
  if (!value.isNumber() || !std::isfinite(value.toNumber()))
    return resource_wire::Error(cx, "Pointer coordinates must be finite numbers", true);
  *out = value.toNumber();
  return true;
}
// The geometry owner supplies the unretargeted painted hit. Follow the live
// browsing-context tree through an iframe's content box; page script getters
// cannot redirect host pointer input. Public elementFromPoint keeps its normal
// shadow retargeting and cross-origin boundaries.
bool PointTarget(JSContext* cx, BrowsingContext& top, double* x, double* y,
                 JS::MutableHandleObject result) {
  result.set(nullptr);
  BrowsingContext* current = &top;
  for (size_t depth = 0; depth < 64; ++depth) {
    JSAutoRealm realm(cx, current->page);
    JS::RootedObject document(cx, current->document->document()), root(cx), hit(cx);
    if (!document) return false;
    JS::RootedValue value(cx, JS::ObjectValue(*document));
    if (!current->document->SvgLengthRoot(value, &root)) return false;
    if (!root) return true;
    std::vector<document_model::NodeKey> hits;
    if (!current->geometry->HitTestPoint(root, *x, *y, false, &hits)) return false;
    if (hits.empty()) return true;
    if (!current->document->WrapNode(hits.front(), &hit)) return false;
    if (!hit) return true;
    BrowsingContext* child = current->frames ? current->frames->FindChild(*current, hits.front()) : nullptr;
    if (!child) { result.set(hit); return true; }
    std::array<double, 4> rect{};
    document_model::OffsetGeometry box{};
    bool present = false;
    if (!current->geometry->MeasureElement(hit, &rect, &present, false) ||
        !current->geometry->MeasureOffset(hit, &box)) return false;
    if (!present) return true;
    // Borders and a scrollbar belong to the embedding element. Enter only
    // the viewport's client area and translate to that document's coordinates.
    const double localX = *x - rect[0] - box.client_left;
    const double localY = *y - rect[1] - box.client_top;
    if (localX < 0 || localY < 0 || localX >= box.client_width || localY >= box.client_height) {
      result.set(hit); return true;
    }
    *x = localX; *y = localY;
    current = child;
  }
  return resource_wire::Error(cx, "Pointer frame nesting limit exceeded", true);
}
}
bool InputRequest(JSContext* cx, TopLevel& top, JS::HandleObject request,
                  SchedulingControl& scheduling, JS::MutableHandleValue result) {
  std::string type;
  JS::RootedValue expression(cx), options(cx);
  bool hasTarget = false, hasX = false, hasY = false;
  if (!resource_wire::Fields(cx, request, {"id", "op", "type", "target", "x", "y", "init"}) ||
      !resource_wire::Property(cx, request, "type", &type, 64, resource_wire::TextKind::ASCII) ||
      !JS_HasProperty(cx, request, "target", &hasTarget) ||
      !JS_HasProperty(cx, request, "x", &hasX) || !JS_HasProperty(cx, request, "y", &hasY) ||
      !JS_GetProperty(cx, request, "init", &options)) return false;
  if (!options.isObject()) return resource_wire::Error(cx, "Input needs an init dictionary");
  if ((hasTarget && (hasX || hasY)) || (!hasTarget && !(hasX && hasY)))
    return resource_wire::Error(cx, "Input needs a target expression or both pointer coordinates");
  JSAutoRealm realm(cx, top.Page());
  JS::RootedObject target(cx), init(cx, &options.toObject());
  if (hasTarget) {
    if (!JS_GetProperty(cx, request, "target", &expression)) return false;
    if (!expression.isString()) return resource_wire::Error(cx, "Input target must be an expression");
    JS::RootedString text(cx, expression.toString());
    JS::AutoStableStringChars characters(cx);
    if (!characters.initTwoByte(cx, text)) return false;
    if (characters.length() > 65536)
      return resource_wire::Error(cx, "Input target expression exceeds 64 KiB", true);
    JS::RootedValue value(cx);
    if (!EvaluateHostExpression(cx, "<input-target>", characters.twoByteChars(), characters.length(), &value))
      return false;
    if (!value.isObject()) return resource_wire::Error(cx, "Input target is not an object");
    target = &value.toObject();
  } else {
    double x = 0, y = 0, screenX = 0, screenY = 0;
    if (!Coordinate(cx, request, "x", &x) || !Coordinate(cx, request, "y", &y) ||
        !top.Active().environment->InnerScreenOrigin(&screenX, &screenY)) return false;
    screenX += x; screenY += y;
    if (!PointTarget(cx, top.Active(), &x, &y, &target)) return false;
    if (!target) { result.setBoolean(false); return true; }
    if (!JS_WrapObject(cx, &target)) return false;
    if (!JS_DefineProperty(cx, init, "clientX", x, JSPROP_ENUMERATE) ||
        !JS_DefineProperty(cx, init, "clientY", y, JSPROP_ENUMERATE) ||
        !JS_DefineProperty(cx, init, "screenX", screenX, JSPROP_ENUMERATE) ||
        !JS_DefineProperty(cx, init, "screenY", screenY, JSPROP_ENUMERATE)) return false;
  }
  if (!interaction::DispatchInput(cx, target, type.c_str(), init,
                                 scheduling.ClockMilliseconds())) return false;
  result.setBoolean(true);
  return true;
}
}
