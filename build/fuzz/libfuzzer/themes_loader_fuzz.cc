// themes_loader_fuzz.cc — CI-side libFuzzer target for the theme loader
// (P9-T8). Feeds arbitrary bytes as tokens.json text, a built-in name, and a
// custom theme doc; the oracle is "no crash, atomic refusal": ImportTheme is
// the hostile-input edge (size-cap + dup-key scan + strict parse + schema +
// contrast audit) and must refuse without corrupting state.
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#include "libfuzzer_common.h"

#define XR_LIBFUZZER_TARGET_NAME "themes_loader_fuzz"

#include "loader.h"

#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  std::string raw(reinterpret_cast<const char*>(data), size);
  xr::themes::LoaderState state =
      xr::themes::LoaderLoad(raw, (size % 3) ? "dark" : "light");
  (void)xr::themes::ApplyBuiltin(&state, raw.substr(0, 16));
  (void)xr::themes::ImportTheme(&state, raw);
}
