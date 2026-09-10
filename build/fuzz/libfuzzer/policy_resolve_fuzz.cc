// policy_resolve_fuzz.cc — CI-side libFuzzer target for the policy resolver
// (P9-T8). Feeds arbitrary bytes into the structured ResolveRequest fields
// (identity / domain / class / trust / now_ms / session_id); the oracle is
// "no crash, no OOM, deterministic": Resolve is pure and total by
// construction (resolve.h).
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#include "libfuzzer_common.h"

#define XR_LIBFUZZER_TARGET_NAME "policy_resolve_fuzz"

#include "resolve.h"   // xr::policy::Resolve / ResolveRequest

#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  xr::policy::ResolveRequest req;
  req.has_request = true;
  req.core_valid = (size % 2) == 0;   // force the valid/invalid legs both
  if (size > 0) {
    req.identity.assign(reinterpret_cast<const char*>(data),
                        (data[0] % 64) + 1);
    req.now_ms = static_cast<int64_t>(data[0]) * 1'000'000;
  }
  if (size > 4) {
    req.registrable_domain.assign(
        reinterpret_cast<const char*>(data + 4), (data[1] % 64) + 1);
  }
  static const char* kClasses[] = {"kNavigation", "kScript", "kPermission",
                                   "kSubresource", "kStorage", "kNetwork"};
  req.request_class = kClasses[(size > 0 ? data[0] : 0) % 6];
  req.has_trust = (size % 3) != 0;
  req.trust = (size % 5) ? "kStandard" : "kFortress";
  req.session_id = "fuzz";
  (void)xr::policy::Resolve(req);
}
