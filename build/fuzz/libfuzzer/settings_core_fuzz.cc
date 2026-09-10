// settings_core_fuzz.cc — CI-side libFuzzer target for the settings core
// (P9-T8). Feeds arbitrary bytes into schema Load, state Load, and
// Router::Resolve; the oracle is "no crash, total": every parser must return
// a typed result and the router must resolve every anchor string.
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#include "libfuzzer_common.h"

#define XR_LIBFUZZER_TARGET_NAME "settings_core_fuzz"

#include "settings_schema.h"
#include "sections.h"
#include "router.h"

#include <string>

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  std::string raw(reinterpret_cast<const char*>(data), size);
  xr::settings::SettingsSchema schema;
  (void)schema.Load(raw);
  xr::settings::Router router(schema);
  (void)router.Resolve(raw);
  (void)router.SectionOf(raw);
  (void)router.SettingAnchor(raw);
}
