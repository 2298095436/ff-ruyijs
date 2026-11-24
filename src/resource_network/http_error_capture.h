#pragma once
#include "resource_network/page_http.h"
namespace ruyijs::resource_network {
// Optional local diagnostics. HTTP_ERROR_DIR captures errors; HTTP_CAPTURE_DIR
// with a nonempty HTTP_CAPTURE_URL substring also selects successful replies.
// All names have the RUYIJS_ prefix. No request or response field is modified.
void CaptureHttpResponse(const std::string& method, const std::string& url,
                      const HttpResult&) noexcept;
}
