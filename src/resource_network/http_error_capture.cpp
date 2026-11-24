#include "resource_network/http_error_capture.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace ruyijs::resource_network {
namespace {
std::string Json(const std::string& text) {
  std::string out = "\"";
  constexpr char hex[] = "0123456789abcdef";
  for (const unsigned char c : text) {
    if (c == '\\' || c == '"') { out += '\\'; out += char(c); }
    else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
    else out += char(c);
  }
  return out + '"';
}
}
void CaptureHttpResponse(const std::string& method, const std::string& url,
                      const HttpResult& response) noexcept {
  if (response.status < 100 || response.status >= 600) return;
  const char* configured = nullptr;
  const char* capture = std::getenv("RUYIJS_HTTP_CAPTURE_DIR");
  const char* filter = std::getenv("RUYIJS_HTTP_CAPTURE_URL");
  if (capture && *capture && filter && *filter && url.find(filter) != std::string::npos)
    configured = capture;
  else if (response.status >= 400)
    configured = std::getenv("RUYIJS_HTTP_ERROR_DIR");
  if (!configured || !*configured) return;
  try {
    const auto directory = std::filesystem::u8path(configured);
    if (!std::filesystem::is_directory(directory)) return;
    static std::atomic<unsigned> sequence{0};
    const unsigned index = sequence.fetch_add(1);
    if (index >= 64) return;  // At most 8 MiB of bodies per process.
    const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto prefix = directory / ("response-" + std::to_string(index) + "-" + std::to_string(tick));
    const size_t captured = std::min<size_t>(response.body.size(), 128 * 1024);
    auto bodyPath = prefix; bodyPath += ".body";
    std::ofstream body(bodyPath, std::ios::binary | std::ios::trunc);
    if (!body) return;
    body.write(response.body.data(), std::streamsize(captured));
    body.close();
    auto metadataPath = prefix; metadataPath += ".json";
    std::ofstream metadata(metadataPath, std::ios::binary | std::ios::trunc);
    if (!metadata) return;
    metadata << "{\"status\":" << response.status << ",\"method\":" << Json(method)
             << ",\"url\":" << Json(url) << ",\"bodyBytes\":" << response.body.size()
             << ",\"capturedBytes\":" << captured << ",\"headers\":[";
    bool first = true;
    for (const auto& [name, value] : response.headers) {
      std::string lower = name;
      std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char c) { return char(std::tolower(c)); });
      if (lower == "set-cookie" || lower == "authorization" || lower == "proxy-authorization") continue;
      if (!first) metadata << ',';
      first = false;
      metadata << '[' << Json(name) << ',' << Json(value) << ']';
    }
    metadata << "]}";
  } catch (...) {
    // Observability must never change the original transport result.
  }
}
}
