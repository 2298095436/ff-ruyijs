#include "execution_scheduling/state.h"
#include "execution_scheduling/idle.h"
#include "execution_scheduling/scheduler.h"
#include "execution_scheduling/trace.h"
#include "runtime/exception_capture.h"
#include "jsfriendapi.h"
#include "js/CallAndConstruct.h"
#include "js/CompilationAndEvaluation.h"
#include "js/Exception.h"
#include "js/Object.h"
#include "js/Realm.h"
#include "js/SourceText.h"
#include "js/StableStringChars.h"

namespace ruyijs::execution_scheduling {
namespace {
const char* KindName(Kind kind) {
  switch (kind) {
    case Kind::Timeout: return "timeout";
    case Kind::Interval: return "interval";
    case Kind::Frame: return "frame";
    case Kind::Message: return "message";
    case Kind::Idle: return "idle";
    case Kind::WebTask: return "web-task";
  }
  return "unknown";
}
void TraceHandler(JSContext* cx, const TaskSnapshot& task, uint32_t handle,
                  JS::HandleValue handler) {
  std::string name, file;
  unsigned line = 0;
  const char* type = handler.isString() ? "string" : "other";
  {
    // Read native function metadata without Function.name/toString or page
    // getters. Delazification may allocate; diagnostics preserve exceptions.
    JS::AutoSaveExceptionState saved(cx);
    if (handler.isObject() && !std::strcmp(JS::GetClass(&handler.toObject())->name, "Function")) {
      type = "function";
      JS::RootedFunction fn(cx, JS_GetObjectFunction(&handler.toObject()));
      JS::RootedString id(cx);
      if (fn && JS_GetFunctionId(cx, fn, &id) && id && JS_GetStringLength(id) <= 256)
        ToUTF8(cx, id, &name);
      JS::RootedScript script(cx, fn ? JS_GetFunctionScript(cx, fn) : nullptr);
      if (script) {
        if (const char* filename = JS_GetScriptFilename(script)) file = filename;
        line = JS_GetScriptBaseLineNumber(cx, script);
      }
    }
    JS_ClearPendingException(cx);
  }
  // Keep one bounded record per task. URLs need no query or fragment here.
  if (const auto query = file.find_first_of("?#"); query != std::string::npos) file.resize(query);
  for (auto* text : {&name, &file}) {
    if (text->size() > 512) text->resize(512);
    for (char& c : *text) if (static_cast<unsigned char>(c) < 32 || c == '"') c = '_';
  }
  std::fprintf(stderr, "ruyijs-task-callback id=%llu kind=%s handle=%u type=%s name=\"%s\" file=\"%s\" line=%u\n",
      static_cast<unsigned long long>(task.id), KindName(task.kind), handle, type,
      name.c_str(), file.c_str(), line);
  std::fflush(stderr);
}
}  // namespace
void State::CheckpointJobs() {
  TaskTrace trace(cx, "checkpoint");
  checkpoint(cx);
  if (!JS_IsExceptionPending(cx) && render && !rendering) {
    rendering = true;
    TaskTrace renderingTrace(cx, "render");
    if (!render(renderContext)) TraceNativeFailure(cx, __FILE__, __LINE__);
    rendering = false;
  }
  if (JS_IsExceptionPending(cx)) {
    TraceNativeFailure(cx, __FILE__, __LINE__);
    CaptureOperationFailure(cx);
    JS_ClearPendingException(cx);
  }
}
static bool EvaluateHandler(JSContext* cx, JS::HandleString code, JS::MutableHandleValue result) {
  JS::AutoStableStringChars characters(cx);
  if (!characters.initTwoByte(cx, code)) return false;
  JS::CompileOptions options(cx);
  options.setFileAndLine("ruyijs:timer", 1);
  JS::SourceText<char16_t> source;
  return source.init(cx, characters.twoByteChars(), characters.length(), JS::SourceOwnership::Borrowed) &&
         JS::Evaluate(cx, options, source, result);
}
void State::Invoke(const TaskSnapshot& task) {
  TaskTrace trace(cx, "callback", task.id);
  Callback* callback = Find(task.id);
  if (!callback) { model.Complete(task.id); return; }
  if (callback->global && Retired(callback->global)) {
    model.Complete(task.id);
    if (model.Exists(task.id)) Drop(task.id, task.kind);
    else Remove(task.id);
    return;
  }
  callback->running = true;
  if (timerReplay && callback->publicHandle &&
      (callback->kind == Kind::Timeout || callback->kind == Kind::Interval)) ++callback->replayFirings;
  uint64_t previousWebTask=runningWebTask;
  runningWebTask=task.kind==Kind::WebTask?task.id:0;
  {
    // A callback runs in the realm it belongs to: a string handler compiles
    // there and a timer's `this` is that Window, as in Firefox. A keepalive
    // task has no document and runs in the scheduling owner's own realm.
    JS::RootedObject home(cx, callback->global ? callback->global : page.get());
    JSAutoRealm realm(cx, home);
    JS::RootedValue handler(cx, callback->handler), result(cx);
    if (trace.enabled()) TraceHandler(cx, task, callback->publicHandle, handler);
    bool ok;
    if (handler.isString()) {
      JS::RootedString code(cx, handler.toString());
      ok = EvaluateHandler(cx, code, &result);
    } else if (task.kind == Kind::WebTask) {
      ok = InvokeWebTask(*this,*callback,&result);
    } else if (task.kind == Kind::Idle) {
      ok = InvokeIdle(*this,*callback,task,&result);
    } else if (task.kind == Kind::Frame) {
      JS::RootedValue stamp(cx, JS::DoubleValue(task.timestamp));
      ok = JS::Call(cx, JS::UndefinedHandleValue, handler, JS::HandleValueArray(stamp), &result);
    } else {
      JS::RootedValue receiver(cx, JS::ObjectValue(*home));
      auto arguments = JS::HandleValueArray::fromMarkedLocation(
          callback->arguments.length(), callback->arguments.begin());
      ok = JS::Call(cx, receiver, handler, arguments, &result);
    }
    if (!ok) {
      TraceNativeFailure(cx, __FILE__, __LINE__, handler);
      CaptureOperationFailure(cx); JS_ClearPendingException(cx);
    }
    CheckpointJobs();
  }
  callback->running = false;
  runningWebTask=previousWebTask;
  SyncClock();
  model.Complete(task.id);
  if (!model.Exists(task.id)) Remove(task.id);
}
}
