#pragma once
#include "document_model/model.h"
#include "js/RootingAPI.h"
namespace ruyijs::document_model {
class Realm;
struct FormField { DomString name, value; bool emptyFile = false; };
struct FormSubmission { DomString action, method, encoding, target; uint64_t version = 0; };
using FormDataPort = bool (*)(void*, Realm&, const std::vector<FormField>&, JS::MutableHandleObject);
using FormNavigatePort = bool (*)(void*, Realm&, JS::HandleObject form,
                                  JS::HandleObject data, const FormSubmission&);
struct Wrapper;
// Root every affected control across click listeners, which may remove nodes
// or collect wrappers. The domain checked state remains the only value store.
struct ClickActivation {
  JS::RootedObjectVector controls;
  std::vector<bool> checked;
  bool active = false, original = false, indeterminate = false;
  explicit ClickActivation(JSContext* cx) : controls(cx) {}
};
bool BeginClickActivation(JSContext*, JS::HandleObject target, ClickActivation&);
bool EndClickActivation(JSContext*, ClickActivation&, bool allowed);
bool SubmitForm(Wrapper&, JS::HandleValue submitter, bool request);
bool ActivateFormControl(Wrapper&);
bool ResetForm(Wrapper&);
bool ControlForm(Wrapper&, JS::MutableHandleValue);
bool ValidateForm(Wrapper&, bool* valid);
}
