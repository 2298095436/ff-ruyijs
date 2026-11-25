#include "runtime/exception_capture.h"
#include "runtime/runtime.h"
#include "jsapi.h"
#include "js/String.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "js/Exception.h"
#include "js/Realm.h"

namespace ruyijs {
static thread_local ExceptionCapture* activeCapture = nullptr;
static thread_local const char* inputTracePhase = "outside-input";
bool NativeInputTraceEnabled() {
  const char* flag = std::getenv("RUYIJS_INPUT_TRACE");
  return flag && *flag && std::strcmp(flag, "0") != 0;
}
const char* SetNativeInputTracePhase(const char* phase) {
  const char* previous = inputTracePhase;
  inputTracePhase = phase ? phase : "outside-input";
  return previous;
}
void TraceNativeFailure(JSContext* cx, const char* file, int line, JS::HandleValue callback) {
  if (!NativeInputTraceEnabled()) return;
  const bool pending = JS_IsExceptionPending(cx);
  std::string name;
  {
    // Resolving a built-in function identifier may allocate, but does not read
    // Function.name or run script. Preserve the original exception state.
    JS::AutoSaveExceptionState saved(cx);
    if (callback.isObject() && !std::strcmp(JS::GetClass(&callback.toObject())->name, "Function")) {
      JS::RootedFunction fn(cx, JS_GetObjectFunction(&callback.toObject()));
      JS::RootedString id(cx);
      if (fn && JS_GetFunctionId(cx, fn, &id) && id && JS_GetStringLength(id) <= 256)
        ToUTF8(cx, id, &name);
    }
    JS_ClearPendingException(cx);
  }
  std::fprintf(stderr, "ruyijs-native-failure file=%s line=%d input_phase=%s pending=%d callback=%s\n",
      file, line, inputTracePhase, int(pending), name.c_str());
  std::fflush(stderr);
}

bool ReadNativeException(JSContext* cx, JS::HandleObject object,
                         JS::MutableHandleString name, JS::MutableHandleString message) {
  if (!activeCapture || activeCapture->context() != cx || !activeCapture->nativeReader())
    return false;
  return activeCapture->nativeReader()(object, name, message);
}

ExceptionCapture::ExceptionCapture(JSContext* cx)
    : cx_(cx), previous_(activeCapture) {
  for (auto& promise : rejections_) promise.init(cx, nullptr);
  activeCapture = this;
}

ExceptionCapture::~ExceptionCapture() { activeCapture = previous_; }

void ExceptionCapture::BeginRequest() {
  failed_ = false;
  exceptionCount_ = 0;
  report_ = ExceptionReport();
}

void ExceptionCapture::Overflow(const char* message) {
  failed_ = true;
  report_ = {"RangeError", message, ""};
}

void ExceptionCapture::Record(JS::HandleValue value, JS::HandleObject stack, bool notify) {
  if (exceptionCount_ == kLimit) {
    Overflow("Request exceeds the 64 exception capture limit");
    return;
  }
  ++exceptionCount_;
  if (notify && sink_ && sink_(sinkContext_, cx_, value, stack)) return;
  if (!failed_) {
    failed_ = true;
    report_ = DescribeException(cx_, value, stack);
  }
}

void ExceptionCapture::CapturePending() {
  if (!JS_IsExceptionPending(cx_)) {
    if (!failed_) {
      failed_ = true;
      report_ = {"ExecutionTerminated", "JavaScript execution terminated", ""};
    }
    return;
  }
  JS::ExceptionStack exception(cx_);
  if (JS::StealPendingExceptionStack(cx_, &exception)) {
    Record(exception.exception(), exception.stack(), true);
  } else {
    failed_ = true;
    report_ = {"InternalError", "Exception capture allocation failed", ""};
  }
  JS_ClearPendingException(cx_);
}

void ExceptionCapture::TrackRejection(
    JS::HandleObject promise, JS::PromiseRejectionHandlingState state) {
  size_t index = 0;
  while (index < rejectionCount_ && rejections_[index].get() != promise.get())
    ++index;
  if (state == JS::PromiseRejectionHandlingState::Handled) {
    if (index < rejectionCount_) {
      for (size_t next = index + 1; next < rejectionCount_; ++next)
        rejections_[next - 1] = rejections_[next].get();
      rejections_[--rejectionCount_] = nullptr;
    }
    return;
  }
  if (index < rejectionCount_) return;
  if (rejectionCount_ == kLimit) {
    Overflow("Request exceeds the 64 pending promise rejection limit");
    return;
  }
  rejections_[rejectionCount_++] = promise;
}

bool ExceptionCapture::Finish(JS::MutableHandleValue value, bool* success) {
  if (JS_IsExceptionPending(cx_)) CapturePending();
  for (size_t index = 0; index < rejectionCount_; ++index) {
    JS::RootedObject promise(cx_, rejections_[index]);
    JSAutoRealm realm(cx_, promise);
    if (JS::GetPromiseState(promise) == JS::PromiseState::Rejected &&
        !JS::GetPromiseIsHandled(promise)) {
      JS::RootedValue reason(cx_, JS::GetPromiseResult(promise));
      JS::RootedObject stack(cx_, JS::GetPromiseResolutionSite(promise));
      Record(reason, stack);
    }
    rejections_[index] = nullptr;
  }
  rejectionCount_ = 0;
  if (!failed_) return true;
  *success = false;
  return CreateExceptionValue(cx_, report_, value);
}

bool CaptureOperationFailure(JSContext* cx) {
  if (!activeCapture || activeCapture->context() != cx) return false;
  activeCapture->CapturePending();
  return true;
}

bool FormatOperationFailure(JSContext* cx, JS::MutableHandleValue value) {
  TraceNativeFailure(cx, __FILE__, __LINE__);
  ExceptionReport report = {
      "ExecutionTerminated", "JavaScript execution terminated", ""};
  if (JS_IsExceptionPending(cx)) {
    JS::ExceptionStack exception(cx);
    if (!JS::StealPendingExceptionStack(cx, &exception)) return false;
    report = DescribeException(cx, exception.exception(), exception.stack());
  }
  return CreateExceptionValue(cx, report, value);
}

bool CaptureShellException(JSContext* cx) {
  return JS_IsExceptionPending(cx) && CaptureOperationFailure(cx);
}

bool CapturePromiseRejection(JSContext* cx, JS::HandleObject promise,
                             JS::PromiseRejectionHandlingState state) {
  if (!activeCapture || activeCapture->context() != cx) return false;
  activeCapture->TrackRejection(promise, state);
  return true;
}
}
