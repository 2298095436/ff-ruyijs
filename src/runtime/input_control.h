#ifndef RUYIJS_INPUT_CONTROL_H
#define RUYIJS_INPUT_CONTROL_H
#include "runtime/runtime.h"
namespace ruyijs {
class SchedulingControl;
class TopLevel;
bool InputRequest(JSContext*, TopLevel&, JS::HandleObject request,
                  SchedulingControl&, JS::MutableHandleValue result);
}
#endif
