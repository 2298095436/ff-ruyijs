#ifndef RUYIJS_WEB_WORKERS_SCRIPT_POLICY_H
#define RUYIJS_WEB_WORKERS_SCRIPT_POLICY_H
#include <string>

namespace ruyijs::web_workers {
// Resolved URL, after canonical scheme parsing. Content Worker constructors
// cannot create Gecko's privileged chrome/resource channels. Channel creation
// fails synchronously; ordinary refused script loads keep their error task.
inline bool PrivilegedScriptURL(const std::string& url) {
  return url.rfind("chrome:", 0) == 0 || url.rfind("resource:", 0) == 0;
}
}
#endif
