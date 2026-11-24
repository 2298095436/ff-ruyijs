// Cascade snapshots enter the original Web Animations owner through native
// ports. No site script, patched API or fabricated UI callback is evaluated.
#include "runtime/css_animation_ports.h"
#include "runtime/browsing_context.h"
#include "document_model/layout_source.h"
#include "web_styling/computed_source.h"
#include "domain/styling/css_components.h"
#include "domain/styling/css_keyframes.h"
#include "js/Realm.h"
#include <algorithm>
#include <cstdlib>
#include <limits>
#include <map>
#include <string>
#include <vector>

namespace ruyijs {
namespace {
namespace css = domain::styling;
namespace animation = domain::animation;
std::vector<std::string> Tokens(const std::string& text) {
  std::vector<std::string> out;
  size_t start = 0;
  unsigned depth = 0;
  char quote = 0;
  for (size_t i = 0; i <= text.size(); ++i) {
    const char c = i < text.size() ? text[i] : ' ';
    if (quote) {
      if (c == '\\') { ++i; continue; }
      if (c == quote) quote = 0;
    } else if (c == '\'' || c == '"') quote = c;
    else if (c == '(') ++depth;
    else if (c == ')' && depth) --depth;
    if (!quote && !depth && css::CssSpace(c)) {
      if (i > start) out.push_back(text.substr(start, i - start));
      start = i + 1;
    }
  }
  return out;
}
bool Time(const std::string& value, double* out) {
  char* end = nullptr;
  const double number = std::strtod(value.c_str(), &end);
  if (end == value.c_str() || !std::isfinite(number)) return false;
  const std::string unit(end);
  if (unit != "s" && unit != "ms") return false;
  *out = number * (unit == "s" ? 1000 : 1);
  return true;
}
void Field(web_animation::CssAnimationInput& input, const std::string& name, const std::string& value) {
  auto& t = input.timing;
  if (name == "name") { std::string text; input.name = css::CssKeyframesName(value, &text) ? text : "none"; }
  else if (name == "duration") { double v; if (Time(value, &v) && v >= 0) t.duration = v; }
  else if (name == "delay") { double v; if (Time(value, &v)) t.delay = v; }
  else if (name == "iteration-count") {
    if (value == "infinite") t.iterations = std::numeric_limits<double>::infinity();
    else { char* end; const double v = std::strtod(value.c_str(), &end);
      if (end != value.c_str() && !*end && std::isfinite(v) && v >= 0) t.iterations = v; }
  } else if (name == "fill-mode") {
    for (int i = 0; i < 4; ++i) if (value == animation::kFillNames[i]) t.fill = animation::Fill(i);
  } else if (name == "direction") {
    for (int i = 0; i < 4; ++i) if (value == animation::kDirectionNames[i]) t.direction = animation::Direction(i);
  } else if (name == "timing-function") animation::ParseEasing(value, &t.easing);
  else if (name == "play-state") input.paused = value == "paused";
}
std::vector<web_animation::CssAnimationInput> Parse(const web_styling::ComputedStyle& style) {
  std::vector<web_animation::CssAnimationInput> out;
  std::string shorthand = style.Get("animation");
  if (shorthand.empty()) shorthand = style.Get("-webkit-animation");
  for (const auto& group : css::CssSplit(shorthand, ',')) {
    web_animation::CssAnimationInput input;
    input.name = "none"; input.timing.durationAuto = false;
    input.timing.fill = animation::Fill::None;
    animation::ParseEasing("ease", &input.timing.easing);
    unsigned times = 0;
    for (const auto& token : Tokens(group)) {
      const std::string lower = css::CssLower(token);
      double time;
      animation::Easing easing;
      if (Time(lower, &time)) Field(input, times++ ? "delay" : "duration", lower);
      else if (animation::ParseEasing(lower, &easing)) input.timing.easing = easing;
      else if (lower == "infinite" || (!lower.empty() && (lower[0] >= '0' && lower[0] <= '9' || lower[0] == '.')))
        Field(input, "iteration-count", lower);
      else if (lower == "normal" || lower == "reverse" || lower == "alternate" || lower == "alternate-reverse")
        Field(input, "direction", lower);
      else if (lower == "forwards" || lower == "backwards" || lower == "both") Field(input, "fill-mode", lower);
      else if (lower == "paused" || lower == "running") Field(input, "play-state", lower);
      else Field(input, "name", token);
    }
    out.push_back(std::move(input));
  }
  const std::string names = style.Get("animation-name");
  if (!names.empty()) {
    const auto list = css::CssSplit(names, ',');
    out.resize(list.size());
    for (size_t i = 0; i < list.size(); ++i) {
      out[i].timing.durationAuto = false;
      Field(out[i], "name", list[i]);
    }
  }
  for (const char* field : {"duration", "delay", "iteration-count", "direction", "fill-mode", "timing-function", "play-state"}) {
    const auto raw = style.Get((std::string("animation-") + field).c_str());
    if (raw.empty()) continue;
    const auto list = css::CssSplit(raw, ',');
    for (size_t i = 0; !list.empty() && i < out.size(); ++i) Field(out[i], field, list[i % list.size()]);
  }
  return out;
}
}
void BindCssAnimationPorts(BrowsingContext& owner) {
  web_animation::Realm::CssPorts ports;
  ports.context = &owner;
  ports.revision = [](void* raw) {
    auto& c = *static_cast<BrowsingContext*>(raw);
    return (c.document->AnimationRevision() * 1099511628211ull) ^ (c.styling->AnimationRevision() + 1);
  };
  ports.read = [](void* raw, JS::MutableHandleObjectVector targets, std::vector<web_animation::CssAnimationInput>* out) {
    auto& c = *static_cast<BrowsingContext*>(raw);
    JSAutoRealm realm(c.cx, c.page);
    if (!c.document->AnimationElements(targets)) return false;
    if (targets.length() > 20000) { JS_ReportErrorASCII(c.cx, "CSS animation element budget exceeded"); return false; }
    auto reader = c.styling->BeginComputedRead();
    std::map<std::pair<uint64_t, uint64_t>, bool> hidden;
    for (size_t i = 0; i < targets.length(); ++i) {
      JS::RootedObject node(c.cx, targets[i]), parent(c.cx);
      JS::RootedObjectVector children(c.cx);
      JS::RootedValue value(c.cx, JS::ObjectValue(*node));
      document_model::LayoutNodeSource source;
      if (!c.document->ReadLayoutNode(value, &source, &parent, &children)) return false;
      bool parentHidden = false;
      if (parent) {
        document_model::NodeKey key;
        JS::RootedValue parentValue(c.cx, JS::ObjectValue(*parent));
        if (!c.document->NodeIdentity(parentValue, &key)) return false;
        parentHidden = hidden[{key.document, key.node}];
      }
      web_styling::ComputedStyle style;
      if (!parentHidden && !reader->Read(node, &style)) return false;
      const bool invisible = parentHidden || style.Get("display") == "none";
      hidden[{source.key.document, source.key.node}] = invisible;
      if (invisible) continue;
      auto inputs = Parse(style);
      inputs.erase(std::remove_if(inputs.begin(), inputs.end(), [](const auto& v) { return v.name.empty() || v.name == "none"; }), inputs.end());
      if (inputs.empty()) continue;
      std::vector<std::string> names;
      if (!c.styling->CssKeyframeNames(node, &names)) return false;
      for (auto& input : inputs) {
        if (std::find(names.begin(), names.end(), input.name) == names.end()) continue;
        input.target = i; out->push_back(std::move(input));
        if (out->size() >= 4096) { JS_ReportErrorASCII(c.cx, "CSS animation budget exceeded"); return false; }
      }
    }
    return true;
  };
  owner.animation->SetCssPorts(ports);
}
}
