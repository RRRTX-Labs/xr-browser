// identity_core_fuzz.cc — CI-side libFuzzer target for the identity core
// (P14-T1). Feeds arbitrary bytes in as a {method,args} request against the
// FROZEN mojom surface and as hostile mint entropy; the oracle is
// "no crash, total": every path returns a typed result, the mint either
// refuses or produces an opaque domain, and the store never accepts a
// name-derived key.
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#define XR_LIBFUZZER_TARGET_NAME "identity_core_fuzz"

#include "libfuzzer_common.h"

#include "binding.h"
#include "hibernate.h"
#include "identity.h"
#include "mint.h"
// (binding.h pulls core/identity.h; compile with -I../xr-core/identity/core
// AND -I../xr-core/identity, the sibling targets' dual-include shape.)

#include <map>
#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  const std::string raw(reinterpret_cast<const char*>(data), size);
  // 1. Hostile entropy: refuse or mint opaque — never a name-derived domain.
  std::string domain;
  if (xr::identity::MintDomain(raw, &domain)) {
    (void)xr::identity::LooksOpaque(domain, raw);  // shape+probe law
  }
  // 2. The store boundary: name-keyed and name-embedding inserts refuse.
  xr::identity::IdentityStore store;
  xr::identity::IdentityRecord rec;
  rec.domain = raw;  // arbitrary bytes as a candidate key
  rec.display_name = raw.substr(0, 32);
  std::string err;
  (void)store.Insert(rec, &err);
  // 3. Lifecycle on whatever the fuzz produced: typed results only.
  xr::identity::Manager m(&store);
  (void)m.Activate(rec.domain);
  (void)m.Hibernate(rec.domain);
  bool verified = false;
  (void)m.Destroy(rec.domain, &verified);
  // 4. The binding audit trail can never gain a suggestion-caused change.
  xr::identity::BindingModel b;
  (void)b.SetWindowDefault("w", rec.domain);
  (void)b.OpenTab("w", 1, "");
  (void)b.RecordSuggestion(raw, rec.domain);
  (void)b.TestPlantedAutoSwitch(1, rec.domain);
  for (const auto& ch : b.changes()) {
    (void)(ch.cause == xr::identity::ChangeCause::kSuggestion);
  }
}
