// SAST negative fixture — must NOT trigger any rule. This is what compliant
// core code looks like: no unchecked stdlib, no shell-out, no pref reads.
#include <string>

namespace xr::policy {
// std::string (not char*) and no format/exec — the compliant shape.
std::string Canonicalize(const std::string& in) {
  std::string out = in;
  out.shrink_to_fit();
  return out;
}
}  // namespace xr::policy
