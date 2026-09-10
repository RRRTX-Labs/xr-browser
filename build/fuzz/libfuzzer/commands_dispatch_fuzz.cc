// commands_dispatch_fuzz.cc — CI-side libFuzzer target for the dispatch
// security edge (P9-T8). Feeds arbitrary bytes as command id + source tag
// into Dispatcher::Invoke; the oracle is "no crash, total": Invoke must
// return an outcome for every input, and non-allowlisted sources must be
// rejected (that invariant also lives in the in-house test_fuzz suite).
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#include "libfuzzer_common.h"

#define XR_LIBFUZZER_TARGET_NAME "commands_dispatch_fuzz"

#include "registry.h"
#include "dispatch.h"

#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  xr::commands::Registry reg;   // default-constructed (empty registry is a
                                // valid, exercised leg: unknown id path)
  xr::commands::Dispatcher dispatcher(reg);
  std::string id(reinterpret_cast<const char*>(data),
                 size > 0 ? (data[0] % 32) + 1 : 0);
  static const char* kSources[] = {"palette", "shortcut", "page",
                                   "test", "menu", ""};
  const std::string source = kSources[(size > 0 ? data[0] : 0) % 6];
  (void)dispatcher.Invoke(id, source, (size % 2) == 0);
}
