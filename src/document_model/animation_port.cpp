// Web Animations ports (docs/owners/WEB_ANIMATION.md): node kind, a node's
// document and the getAnimations() scope, read from the unique tree through the
// node's own owning State. No page method runs and nothing is cached.
#include "document_model/state.h"
#include "js/Object.h"
#include "js/Realm.h"
#include "js/Wrapper.h"

namespace ruyijs::document_model {
namespace {
Wrapper* Live(JSObject* object) {
  JSObject* node = object ? js::CheckedUnwrapStatic(object) : nullptr;
  if (!node || JS::GetClass(node) != &kNodeClass) return nullptr;
  auto* wrapper = static_cast<Wrapper*>(JS::GetReservedSlot(node, 0).toPrivate());
  return wrapper && wrapper->owner && !wrapper->dead ? wrapper : nullptr;
}
}  // namespace

JSObject* Realm::animationDocumentPrototype() {
  Interface* iface = state_->Find("Document");
  return iface ? iface->prototype.get() : nullptr;
}
int Realm::AnimationNodeKind(JS::HandleValue value) {
  Wrapper* w = Live(value.isObject() ? &value.toObject() : nullptr);
  NodeSnapshot node;
  if (!w || w->owner->model.Inspect(w->key, &node).code != ErrorCode::None) return 0;
  return node.kind == NodeKind::Element ? 1 : node.kind == NodeKind::Document ? 2 : 0;
}
bool Realm::AnimationNodeDocument(JS::HandleObject object, JS::MutableHandleObject document) {
  Wrapper* w = Live(object);
  NodeSnapshot node;
  if (!w) return false;
  State& owner = *w->owner;
  if (!owner.Check(owner.model.Inspect(w->key, &node))) return false;
  JSAutoRealm realm(owner.cx, owner.page);
  JS::RootedValue value(owner.cx);
  if (!owner.Wrap(node.kind == NodeKind::Document ? w->key : node.owner_document, &value)) return false;
  if (!JS_WrapValue(state_->cx, &value)) return false;
  document.set(&value.toObject());
  return true;
}
bool Realm::AnimationInScope(JS::HandleObject root, JS::HandleObject object, bool subtree, bool* result) {
  *result = false;
  Wrapper* r = Live(root);
  Wrapper* n = Live(object);
  if (!r || !n || r->owner != n->owner) return true;
  State& owner = *r->owner;
  NodeSnapshot scope, node;
  if (!owner.Check(owner.model.Inspect(r->key, &scope)) || !owner.Check(owner.model.Inspect(n->key, &node)))
    return false;
  if (scope.kind == NodeKind::Document) {
    *result = node.is_connected && Same(node.root, r->key);
    return true;
  }
  if (!subtree) { *result = Same(r->key, n->key); return true; }
  return owner.Check(owner.model.Contains(r->key, n->key, result));
}
uint64_t Realm::AnimationRevision(bool styleAttributeDependency) {
  return styleAttributeDependency ? state_->model.ConnectedRevision() : state_->model.AnimationRevision();
}
bool Realm::AnimationElements(JS::MutableHandleObjectVector out) {
  State& state = *state_;
  std::vector<NodeKey> nodes;
  if (!state.Check(state.model.Subtree(state.main, &nodes))) return false;
  out.clear();
  for (NodeKey key : nodes) {
    NodeSnapshot node;
    if (!state.Check(state.model.Inspect(key, &node))) return false;
    if (node.kind != NodeKind::Element) continue;
    JS::RootedObject object(state.cx);
    if (!WrapNode(key, &object) || !out.append(object)) return false;
  }
  return true;
}
}  // namespace ruyijs::document_model
