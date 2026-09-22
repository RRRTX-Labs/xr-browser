// cosmetic_core_fuzz.cc — CI-side libFuzzer target for the cosmetic core
// (P12-T2). Feeds arbitrary bytes into the parser surface the renderer will
// host at document-start: selector parse, key-set compile, strict blob parse
// (digest-verified), scope-key derivation, an ABPF filter line, a style
// declaration, and the degrade truth table. The oracle is "no crash, total":
// every parser must return a typed result, and the degrade lookup must
// resolve every condition to a row.
//
// Built only by the CI lane (clang + libFuzzer); see libfuzzer_common.h.
#include "libfuzzer_common.h"

#define XR_LIBFUZZER_TARGET_NAME "cosmetic_core_fuzz"

#include "renderer/cosmetic/abpf/abpf.h"
#include "renderer/cosmetic/core/blob.h"
#include "renderer/cosmetic/core/degrade.h"
#include "renderer/cosmetic/core/keyset.h"
#include "renderer/cosmetic/core/scope_key.h"
#include "renderer/cosmetic/core/selector.h"
#include "renderer/cosmetic/core/style.h"

#include <string>

namespace xrc = xr::cosmetic;

static void XrFuzzOneInput(const uint8_t* data, size_t size) {
  std::string raw(reinterpret_cast<const char*>(data), size);

  // Every parser returns a typed result and never throws (total functions).
  xrc::Selector sel;
  (void)xrc::ParseSelector(raw, &sel);
  (void)xrc::IsTrivialSelector(raw);

  xrc::StyleError se = xrc::ValidateDeclaration(raw, raw.substr(0, 32));
  (void)xrc::StyleErrorName(se);

  xrc::AbpfFilter abpf;
  (void)xrc::ParseAbpfFilter(raw, /*strict=*/true, &abpf);

  // A blob parse must never be followed by a use of a partial blob: refusal
  // leaves `valid == false`, which this oracle relies on.
  xrc::BlobResult blob_out;
  (void)xrc::ParseBlob(raw, nullptr, &blob_out);
  if (blob_out.valid) {
    (void)xrc::BlobDigest(blob_out.blob);
  }

  // Scope-key derivation: the embedder site is REFUSED (never a key).
  xrc::ScopeInput in;
  in.frame_site = raw.substr(0, 24);
  in.frame_identity = raw.substr(24, 16);
  in.document_url_class = raw.substr(40, 8);
  xrc::ScopeKey key;
  (void)xrc::DeriveScopeKey(in, /*embedder_site=*/raw.substr(48, 8), &key);

  // The degrade table answers every condition (data, never code paths).
  for (int c = 0; c <= static_cast<int>(xrc::DegradeCondition::kGenericSetOnly);
       ++c) {
    const xrc::DegradeRow& row =
        xrc::LookupDegrade(static_cast<xrc::DegradeCondition>(c));
    (void)row;
  }
}
