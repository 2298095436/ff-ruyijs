#pragma once
#include "resource_network/page_http.h"
namespace ruyijs::resource_network {
// Optional local diagnostics, disabled unless RUYIJS_HTTP_ERROR_DIR names an
// existing directory. No request is sent and no response field is modified.
void CaptureHttpError(const std::string& method, const std::string& url,
                      const HttpResult&) noexcept;
}
