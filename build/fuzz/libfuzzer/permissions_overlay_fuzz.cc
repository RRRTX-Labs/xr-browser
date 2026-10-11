// permissions_overlay_fuzz.cc — CI-side libFuzzer target for the permissions
// overlay core (P15-CLOSE C3, fleet row `permissions-overlay`). Feeds arbitrary
// bytes in as a stored overlay document and as op arguments; the oracle is
// "no crash, total, never repaired":
//   * LoadStore either returns the corrupt store or a store whose canonical
//     bytes ARE the input (no repaired store escapes);
//   * corruption persists through a save (SerializeStore of a corrupt store
//     reloads corrupt);
//   * every op on whatever loaded returns a typed outcome, and a refusal leaves
//     the store byte-identical.
// The in-house seeded runner (xr-core/permissions/tests/test_fuzz.cc) is the
// gate lane in this sandbox; this file is built only where clang exists.
//
// Usage (CI): clang++ -std=c++20 -fsanitize=fuzzer,address -DLIBFUZZER_BUILD \
//   -I../xr-core permissions_overlay_fuzz.cc ../xr-core/permissions/core/*.cc \
//   ../xr-core/common/core/json.cc ../xr-core/common/core/json_parse.cc
#define XR_LIBFUZZER_TARGET_NAME "permissions_overlay_fuzz"

#include <cstddef>
#include <cstdint>
#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size);

#include "libfuzzer_common.h"

#include "permissions/core/ops.h"
#include "permissions/core/store.h"

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  const std::string raw(reinterpret_cast<const char*>(data), size);
  using namespace xr::permissions;
  // 1. Hostile stored bytes.
  const Store s = LoadStore(raw);
  if (!s.corrupt && SerializeStore(s) != raw) __builtin_trap();  // repaired store
  if (LoadStore(SerializeStore(s)).corrupt != s.corrupt) __builtin_trap();
  // 2. Ops on whatever loaded, with arguments carved from the same bytes.
  const size_t cut = size / 2;
  const std::string a = raw.substr(0, cut), b = raw.substr(cut);
  const int64_t now = static_cast<int64_t>(size) * kMillisPerDay;
  const std::string before = SerializeStore(s);
  GrantRequest r;
  r.identity = a;
  r.domain = b;
  r.capability = "camera";
  r.scope = (size % 3 == 0) ? "once" : (size % 3 == 1) ? "session" : "7d";
  r.session_id = (size % 3 == 1) ? a : "";
  const OpOutcome outs[] = {
      GrantTemp(s, r, now),          SetDefault(s, a, b, "kAllow", now),
      SetDenied(s, a, true, now),    ConsumeOnce(s, b, now),
      SweepExpired(s, now, a),       RevokeSite(s, a, b, now),
      RevokeAll(s, a, now),
  };
  for (const OpOutcome& o : outs) {
    if (!o.ok && SerializeStore(o.store) != before) __builtin_trap();  // half-applied
    (void)ProjectViewJson(o.store);
  }
}
