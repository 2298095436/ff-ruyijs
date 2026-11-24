#ifndef RUYIJS_INPUT_CONTROL_H
#define RUYIJS_INPUT_CONTROL_H
#include "runtime/runtime.h"
namespace ruyijs {
class SchedulingControl;
class TopLevel;
struct BrowsingContext;
bool ResolvePointerTarget(JSContext*, BrowsingContext&, double* x, double* y,
                          JS::MutableHandleObject target, BrowsingContext** owner);
bool InputRequest(JSContext*, TopLevel&, JS::HandleObject request,
                  SchedulingControl&, JS::MutableHandleValue result);
}
#endif
