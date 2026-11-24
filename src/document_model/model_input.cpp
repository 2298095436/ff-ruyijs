#include "document_model/model_internal.h"
#include "domain/document_model/input_validity.h"
#include "domain/document_model/input_radio_group.h"
#include "domain/document_model/textarea_values.h"
#include <charconv>
#include <cmath>

namespace ruyijs::document_model {
Status Model::InputText(NodeKey key, DomStringView name, DomString* out) const noexcept {
  return Protect([&] { *out = domain::input_text(State().element(key), name); });
}
Status Model::InputNumber(NodeKey key, DomStringView name, double* out) const noexcept {
  return Protect([&] {
    const auto& e = State().element(key);
    if (name == u"valueAsNumber") {
      *out = domain::input_numeric(domain::input_type(e)) ? domain::input_decimal(domain::input_value(e))
          : std::numeric_limits<double>::quiet_NaN();
    } else *out = domain::input_integer(name, e.get_attribute16(name).value_or(u""));
  });
}
Status Model::InputTypeValue(DomStringView value, DomString* out) const noexcept {
  return Protect([&] { *out = domain::input_type(value); });
}
Status Model::InputWillValidate(NodeKey key, bool* out) const noexcept {
  return Protect([&] { *out = domain::input_will_validate(State().element(key)); });
}
Status Model::ControlValidation(NodeKey key, uint32_t* flags, DomString* message) const noexcept {
  return Protect([&] {
    const auto& e = State().element(key);
    if (e.tag_name().html() && e.tag_name().local16() == u"input")
      *flags = domain::input_validity(e, message, domain::form_radio(e) &&
          domain::input_group_missing(State().owner(key), key.node));
    else if (e.tag_name().html() && e.tag_name().local16() == u"textarea")
      *flags = domain::textarea_validity(State().owner(key), e, message);
    else {
      *flags = e.custom_validity().empty() ? 0 : 1u << 9;
      if (message) *message = e.custom_validity();
    }
  });
}
Status Model::SetInputNumber(NodeKey key, double value, bool step) noexcept {
  DomString text; bool apply = false;
  auto status = Protect([&] {
    const auto& e = State().element(key);
    apply = domain::input_numeric(domain::input_type(e));
    if (!apply) return;
    if (step) {
      const double old = domain::input_decimal(domain::input_value(e));
      value += std::isnan(old) ? 0 : old;
    }
    if (std::isfinite(value)) {
      char buffer[64];
      const auto converted = std::to_chars(buffer, buffer + sizeof(buffer), value);
      if (converted.ec == std::errc{}) text = domain::from_utf8(std::string(buffer, converted.ptr));
    }
  });
  return status.code == ErrorCode::None && apply ? SetInputValue(key, text) : status;
}
Status Model::InputSelection(NodeKey key, uint32_t* start, uint32_t* end,
                             DomString* direction, bool* applies) const noexcept {
  return Protect([&] {
    const auto& e = State().element(key);
    const auto length = uint32_t(domain::input_value(e).size());
    const auto& selection = e.input_selection();
    if (start) *start = std::min(selection.start, length);
    if (end) *end = std::min(selection.end, length);
    if (direction) *direction = selection.direction_name();
    if (applies) *applies = domain::input_selection_applies(domain::input_type(e));
  });
}
Status Model::SetInputSelection(NodeKey key, uint32_t start, uint32_t end,
                                DomStringView direction, int field) noexcept {
  return Protect([&] {
    auto& e = State().element(key);
    if (field == 4 && !domain::input_textual(domain::input_type(e))) return;
    if (field != 4 && !domain::input_selection_applies(domain::input_type(e)))
      throw domain::DomError(domain::DomErrorCode::InvalidState, "Input type has no selection API");
    auto& selection = e.input_selection();
    const auto length = uint32_t(domain::input_value(e).size());
    selection.start = std::min(selection.start, length);
    selection.end = std::min(selection.end, length);
    // 0=start, 1=end, 2=direction, 3=range, 4=select all.
    if (field == 0) {
      selection.start = std::min(start, length);
      selection.end = std::max(selection.start, selection.end);
    } else if (field == 1) {
      selection.end = std::min(end, length);
      selection.start = std::min(selection.start, selection.end);
    } else if (field == 3 || field == 4) {
      selection.end = field == 4 ? length : std::min(end, length);
      selection.start = field == 4 ? 0 : std::min(start, selection.end);
    }
    if (field >= 2) selection.direction = domain::TextControlSelection::parse_direction(direction);
  });
}
Status Model::InputRange(NodeKey key, DomStringView replacement, uint32_t start, uint32_t end,
                         bool explicit_range, DomStringView mode, bool user_edit) noexcept {
  DomString text;
  uint32_t selection_start = 0, selection_end = 0;
  bool apply = false;
  auto status = Protect([&] {
    const auto& e = State().element(key);
    const auto type = domain::input_type(e);
    if (!user_edit && !domain::input_selection_applies(type))
      throw domain::DomError(domain::DomErrorCode::InvalidState, "Input type has no range replacement API");
    apply = domain::input_textual(type);
    if (!apply) return;
    text = domain::input_value(e);
    const auto& selection = e.input_selection();
    selection_start = std::min(selection.start, uint32_t(text.size()));
    selection_end = std::min(selection.end, uint32_t(text.size()));
    if (!explicit_range) { start = selection_start; end = selection_end; }
    if (start > end)
      throw domain::DomError(domain::DomErrorCode::IndexSize, "Input range start exceeds end");
    const size_t first = std::min(size_t(start), text.size());
    const size_t last = std::min(size_t(end), text.size());
    text.replace(first, last - first, replacement);
    const auto after = uint32_t(first + replacement.size());
    if (mode == u"select") { selection_start = uint32_t(first); selection_end = after; }
    else if (mode == u"start") selection_start = selection_end = uint32_t(first);
    else if (mode == u"end") selection_start = selection_end = after;
    else {
      const int64_t delta = int64_t(replacement.size()) - int64_t(last - first);
      if (selection_start > last) selection_start = uint32_t(int64_t(selection_start) + delta);
      else if (selection_start > first) selection_start = uint32_t(first);
      if (selection_end > last) selection_end = uint32_t(int64_t(selection_end) + delta);
      else if (selection_end > first) selection_end = after;
    }
  });
  if (status.code != ErrorCode::None || !apply) return status;
  status = SetInputValue(key, text);
  if (status.code != ErrorCode::None) return status;
  return Protect([&] {
    auto& selection = State().element(key).input_selection();
    const auto length = uint32_t(domain::input_value(State().element(key)).size());
    selection.end = std::min(selection_end, length);
    selection.start = std::min(selection_start, selection.end);
    selection.direction = domain::TextControlSelection::None;
  });
}
}
