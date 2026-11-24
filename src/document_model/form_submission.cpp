#include "document_model/form_submission.h"
#include "document_model/html_control.h"
#include "interaction/realm.h"
#include "js/Realm.h"

namespace ruyijs::document_model {
namespace {
struct Flag {
  bool& value;
  explicit Flag(bool& value) : value(value) { value = true; }
  ~Flag() { value = false; }
};
bool Connected(Wrapper& form, State& state) {
  NodeSnapshot node;
  return form.owner == &state && state.Check(state.model.Inspect(form.key, &node)) && node.is_connected;
}
bool SubmissionAttribute(State& s, NodeKey form, NodeKey submitter, DomStringView name,
                          DomStringView overrideName, DomString* out) {
  if (submitter.node) {
    std::optional<DomString> value;
    if (!s.Check(s.model.GetAttribute(submitter, overrideName, &value))) return false;
    if (value) { *out = *value; return true; }
  }
  return s.Check(s.model.FormAttribute(form, name, out));
}
}
bool BeginClickActivation(JSContext* cx, JS::HandleObject target, ClickActivation& activation) {
  JS::RootedValue value(cx, JS::ObjectValue(*target));
  Wrapper* entry = ElementReceiver(cx, value);
  if (!entry) return false;
  auto& s = *entry->owner;
  JSAutoRealm realm(cx, s.page);
  NodeSnapshot node;
  if (!s.Check(s.model.Inspect(entry->key, &node))) return false;
  if (!node.is_html_element || node.local_name != u"input") return true;
  bool disabled = false, submit = false;
  DomString type;
  std::optional<DomString> attribute;
  if (!s.Check(s.model.FormControlInfo(entry->key, &disabled, &submit)) ||
      !s.Check(s.model.GetAttribute(entry->key, u"type", &attribute)) ||
      !s.Check(s.model.InputTypeValue(attribute.value_or(u""), &type))) return false;
  if (disabled || (type != u"radio" && type != u"checkbox")) return true;
  if (!s.Check(s.model.InputChecked(entry->key, &activation.original)) ||
      !s.Check(s.model.InputChecked(entry->key, &activation.indeterminate, true))) return false;
  JS::RootedObject object(cx, entry->object);
  if (!activation.controls.append(object)) return false;
  activation.checked.push_back(activation.original);
  if (type == u"radio") {
    std::vector<NodeKey> peers;
    if (!s.Check(s.model.InputRadioGroup(entry->key, &peers))) return false;
    for (auto key : peers) {
      if (Same(key, entry->key)) continue;
      bool checked = false;
      JS::RootedValue peer(cx);
      if (!s.Check(s.model.InputChecked(key, &checked)) || !s.Wrap(key, &peer) ||
          !activation.controls.append(&peer.toObject())) return false;
      activation.checked.push_back(checked);
    }
  }
  activation.active = true;
  return s.Check(s.model.SetInputChecked(entry->key, type == u"radio" || !activation.original)) &&
      (type != u"checkbox" || s.Check(s.model.SetInputChecked(entry->key, false, true)));
}
bool EndClickActivation(JSContext* cx, ClickActivation& activation, bool allowed) {
  if (!activation.active) return true;
  JS::RootedValue target(cx, JS::ObjectValue(*activation.controls[0]));
  Wrapper* entry = ElementReceiver(cx, target);
  if (!entry) return false;
  auto& s = *entry->owner;
  JSAutoRealm realm(cx, s.page);
  if (!allowed) {
    for (size_t index = 0; index < activation.controls.length(); ++index) {
      JS::RootedValue control(cx, JS::ObjectValue(*activation.controls[index]));
      Wrapper* peer = ElementReceiver(cx, control);
      if (!peer || !peer->owner->Check(peer->owner->model.SetInputChecked(peer->key, activation.checked[index]))) return false;
    }
    return s.Check(s.model.SetInputChecked(entry->key, activation.indeterminate, true));
  }
  bool checked = false;
  NodeSnapshot node;
  if (!s.Check(s.model.InputChecked(entry->key, &checked)) || !s.Check(s.model.Inspect(entry->key, &node))) return false;
  if (checked == activation.original || !node.is_connected) return true;
  JS::RootedObject object(cx, entry->object);
  return s.interaction.Fire(object, "input", true, false) && s.interaction.Fire(object, "change", true, false);
}
bool SubmitForm(Wrapper& form, JS::HandleValue argument, bool request) {
  State& s = *form.owner;
  // Argument conversion and ownership errors use the method's current realm.
  Wrapper* submitter = nullptr;
  if (request && !argument.isNullOrUndefined()) {
    submitter = ControlReceiver(s.cx, argument, nullptr);
    if (!submitter) return false;
    bool disabled, button;
    if (!submitter->owner->Check(submitter->owner->model.FormControlInfo(submitter->key, &disabled, &button))) return false;
    if (!button) return TypeError(s.cx, "requestSubmit requires a submit button");
    NodeKey owner;
    if (!submitter->owner->Check(submitter->owner->model.FormOwner(submitter->key, &owner))) return false;
    if (submitter->owner != &s || !Same(owner, form.key))
      return ThrowDOM(*form.factory, "NotFoundError", "The submitter does not belong to this form");
  }
  JSAutoRealm realm(s.cx, s.page);
  JS::RootedObject target(s.cx, form.object), button(s.cx, submitter ? submitter->object : nullptr);
  if (form.formConstructing || (request && form.formSubmitting) || !Connected(form, s)) return true;
  const uint64_t generation = s.scriptGeneration;
  if (request) {
    Flag submitting(form.formSubmitting);
    std::optional<DomString> skip;
    if (!s.Check(s.model.GetAttribute(form.key, u"novalidate", &skip))) return false;
    if (!skip && submitter && !s.Check(s.model.GetAttribute(submitter->key, u"formnovalidate", &skip))) return false;
    bool valid = true;
    if (!skip && !ValidateForm(form, &valid)) return false;
    if (!valid) return true;
    bool allowed;
    if (!s.interaction.FireSubmission(target, button, nullptr, &allowed)) return false;
    if (!allowed) return true;
  }
  if (generation != s.scriptGeneration || !Connected(form, s)) return true;
  if (!s.formDataPort || !s.formNavigatePort) return TypeError(s.cx, "Form ports are not installed");
  JS::RootedObject data(s.cx);
  NodeKey buttonKey = submitter && submitter->owner == &s ? submitter->key : NodeKey{};
  {
    Flag constructing(form.formConstructing);
    std::vector<FormField> fields;
    if (!s.Check(s.model.FormFields(form.key, buttonKey, &fields)) ||
        !s.formDataPort(s.formContext, *s.sourceRealm, fields, &data) ||
        !s.interaction.FireSubmission(target, nullptr, data, nullptr)) return false;
  }
  if (generation != s.scriptGeneration || !Connected(form, s)) return true;
  FormSubmission submission;
  if (!SubmissionAttribute(s, form.key, buttonKey, u"action", u"formaction", &submission.action) ||
      !SubmissionAttribute(s, form.key, buttonKey, u"method", u"formmethod", &submission.method) ||
      !SubmissionAttribute(s, form.key, buttonKey, u"enctype", u"formenctype", &submission.encoding) ||
      !SubmissionAttribute(s, form.key, buttonKey, u"target", u"formtarget", &submission.target)) return false;
  submission.version = ++form.formNavigationVersion;
  return s.formNavigatePort(s.formContext, *s.sourceRealm, target, data, submission);
}
bool ActivateFormControl(Wrapper& control) {
  auto& s = *control.owner;
  bool disabled, submit;
  if (!s.Check(s.model.FormControlInfo(control.key, &disabled, &submit))) return false;
  if (disabled) return true;
  DomString type;
  std::optional<DomString> attr;
  if (!s.Check(s.model.GetAttribute(control.key, u"type", &attr))) return false;
  if (!s.Check(s.model.InputTypeValue(attr.value_or(u""), &type))) return false;
  const bool reset = type == u"reset";
  if (!submit && !reset) return true;
  JS::RootedValue value(s.cx);
  if (!ControlForm(control, &value)) return false;
  if (!value.isObject()) return true;
  auto* form = s.Find(&value.toObject());
  if (reset) return form && ResetForm(*form);
  JS::RootedValue button(s.cx, JS::ObjectValue(*control.object));
  return form && SubmitForm(*form, button, true);
}
}
