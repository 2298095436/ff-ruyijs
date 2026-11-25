// Document focus derives from the original live frame tree and each Model's
// stored focused node. Inactive documents retain their local active element,
// while Document.hasFocus follows only the selected ancestor iframe chain.
#include "runtime/browsing_context.h"
#include "jsapi.h"

namespace ruyijs {
bool Frames::ContainsFocus(BrowsingContext& source, bool* result) const {
  *result = false;
  if (FindCurrentDocument(*source.document) != &source) return true;
  for (auto* child = &source; child->parent; child = child->parent) {
    document_model::NodeKey focused;
    if (!child->parent->document->FocusedElementKey(&focused)) return false;
    if (focused.document != child->frame_element.document ||
        focused.node != child->frame_element.node) return true;
  }
  // This runtime's active top-level traversable has system focus.
  *result = true;
  return true;
}
bool Frames::RequestFocus(BrowsingContext& source, document_model::NodeKey next) {
  if (FindCurrentDocument(*source.document) != &source) return true;
  BrowsingContext* chain[kLimit + 1];
  size_t count = 0;
  for (auto* at = &source; at; at = at->parent) {
    if (count == kLimit + 1) {
      JS_ReportErrorASCII(source.cx, "Focus frame nesting limit exceeded");
      return false;
    }
    chain[count++] = at;
  }
  // Outer documents select their iframe before focus reaches the inner node.
  // ApplyFocus stays in the document owner and uses the same local events and
  // style invalidation as ordinary element focus, without re-entering this port.
  for (size_t i = count; i > 1; --i) {
    if (FindCurrentDocument(*source.document) != &source) return true;
    if (!chain[i - 1]->document->ApplyFocus(chain[i - 2]->frame_element)) return false;
  }
  if (FindCurrentDocument(*source.document) != &source) return true;
  return source.document->ApplyFocus(next);
}
}
