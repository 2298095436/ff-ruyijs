#ifndef RUYIJS_SCHEDULING_TRACE_H
#define RUYIJS_SCHEDULING_TRACE_H
// Optional native task boundaries. No JS properties, timer selection or clock
// updates are involved: a missing end marker identifies a blocked native phase.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "jsapi.h"

namespace ruyijs::execution_scheduling {
class TaskTrace {
 public:
  TaskTrace(JSContext* cx, const char* phase, uint64_t id = 0)
      : cx_(cx), phase_(phase), id_(id) {
    // This is a process-start option. Windows getenv takes the CRT environment
    // lock; doing that at every task/checkpoint costs more than an empty timer.
    static const bool enabled = [] {
      const char* flag = std::getenv("RUYIJS_TASK_TRACE");
      return flag && *flag && std::strcmp(flag, "0") != 0;
    }();
    enabled_ = enabled;
    if (enabled_) {
      started_ = std::chrono::steady_clock::now();
      Write("begin", 0);
    }
  }
  ~TaskTrace() {
    if (enabled_) Write("end", std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - started_).count());
  }
  bool enabled() const { return enabled_; }
 private:
  void Write(const char* boundary, double elapsed) const {
    std::fprintf(stderr, "ruyijs-task phase=%s boundary=%s id=%llu elapsed_ms=%.3f pending=%d\n",
        phase_, boundary, static_cast<unsigned long long>(id_), elapsed,
        int(JS_IsExceptionPending(cx_)));
    std::fflush(stderr);
  }
  JSContext* cx_;
  const char* phase_;
  uint64_t id_;
  bool enabled_ = false;
  std::chrono::steady_clock::time_point started_;
};
}
#endif
