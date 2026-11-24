#pragma once
#include "document_model/html_control.h"

namespace ruyijs::document_model {
bool InstallInputMethods(State&);
bool UpdateInputSelection(Wrapper&, uint32_t start, uint32_t end, DomStringView direction, int field);
bool QueueInputSelect(Wrapper&);
}
