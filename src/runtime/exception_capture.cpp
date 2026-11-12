#include "runtime/exception_capture.h"
#include "js/Exception.h"
#include "js/Realm.h"
#include "interaction/realm.h"
#include "js/ValueArray.h"

namespace ruyijs {
static thread_local ExceptionCapture* activeCapture = nullptr;

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
  JS::RootedObjectVector pending(cx_);
  for (size_t index = 0; index < rejectionCount_; ++index) {
    if (!pending.append(rejections_[index])) return false;
    rejections_[index] = nullptr;
  }
  rejectionCount_ = 0;
  for (size_t index = 0; index < pending.length(); ++index) {
    JS::RootedObject promise(cx_, pending[index]);
    JSAutoRealm realm(cx_, promise);
    if (JS::GetPromiseState(promise) == JS::PromiseState::Rejected &&
        !JS::GetPromiseIsHandled(promise)) {
      JS::RootedValue reason(cx_, JS::GetPromiseResult(promise));
      JS::RootedObject stack(cx_, JS::GetPromiseResolutionSite(promise));
      bool allowed = true;
      const bool dispatched = interaction::DispatchPromiseRejection(cx_, promise, reason, &allowed);
      if (JS_IsExceptionPending(cx_)) CapturePending();
      if (!dispatched || allowed) Record(reason, stack);
    }
  }
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
