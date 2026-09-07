"""seam_spec.py — what the 0042-seam-hook candidate patch changes, declaratively.

Kept separate from genpatch.py so the *policy* (which files may be touched,
where the payloads come from) is reviewable on its own, and so genpatch stays
under the 400-LOC house limit.

Nothing here is applied to a real checkout by anything except genpatch, and
nothing here is entered into patches/manifest.yaml: this is a CANDIDATE patch
(patchinfo.md header `manifest-entry: NOT-YET`).
"""
from __future__ import annotations

from pathlib import Path

# Where the hook sources live in xr-core (the product repo). genpatch reads
# them from disk — it never carries a remembered copy of the payload.
SPIKE_REL = Path("spike/identity_seam")

# The candidate patch's Chromium-side destinations (all under chrome/browser/).
HOOK_HEADER = "chrome/browser/xr/xr_identity.h"
HOOK_SOURCE = "chrome/browser/xr/xr_identity.cc"
OVERRIDE_HEADER = "chrome/browser/xr/xr_seam_override.h"
OVERRIDE_SOURCE = "chrome/browser/xr/xr_seam_override.cc"
NAVIGATOR = "chrome/browser/ui/navigator/browser_navigator.cc"
NAVIGATOR_BUILD = "chrome/browser/ui/navigator/BUILD.gn"

# §12.7 never-list, enforced in tooling: a spike patch may only land in the
# embedder layer. Anything under these prefixes is refused outright.
FORBIDDEN_PREFIXES = (
    "content/",
    "third_party/",
    "v8/",
    "net/",
    "services/",
    "base/",
    "components/",
    "ipc/",
    "mojo/",
    "ui/",
    "gpu/",
    "cc/",
    "skia/",
)

# ...and everything must be inside the embedder layer we do own.
ALLOWED_PREFIXES = ("chrome/browser/",)

INCLUDE_ANCHOR = ('#include "chrome/browser/ui/tabs/'
                  'tab_strip_user_gesture_details.h"')
INCLUDE_NEW = "#include \"chrome/browser/xr/xr_identity.h\"\n" \
              "#include \"chrome/browser/xr/xr_seam_override.h\""

SITEINSTANCE_OLD = """  scoped_refptr<content::SiteInstance> initial_site_instance_for_new_contents =
      params.opener ? params.opener->GetSiteInstance()
                    : tab_util::GetSiteInstanceForNewTab(
                          params.browser->GetProfile(), url);
"""

SITEINSTANCE_NEW = """  scoped_refptr<content::SiteInstance> initial_site_instance_for_new_contents =
      params.opener ? params.opener->GetSiteInstance()
                    : tab_util::GetSiteInstanceForNewTab(
                          params.browser->GetProfile(), url);

#if BUILDFLAG(ENABLE_XR_SPIKE)
  // XR identity seam (P4 spike). When this navigation requests an identity,
  // replace the initial SiteInstance with one pinned to that identity's
  // StoragePartition — BEFORE the WebContents exists, which is the only
  // ordering the seam allows:
  //   * browsing_instance.cc:178-183 pins the partition on the first
  //     registered SiteInstance and CHECK_EQ()s every later one;
  //   * browsing_instance.cc:264-267 propagates it to SiteInstances created
  //     by subsequent navigations (including cross-site OOPIFs).
  // A WebContentsUserData consulted during partition selection would race the
  // first navigation; this hook is why the spike does not need one.
  if (!params.opener) {
    std::optional<xr::Identity> xr_identity =
        xr::IdentityForNewTab(params.browser->GetProfile(), url);
    if (xr_identity.has_value()) {
      scoped_refptr<content::SiteInstance> xr_site_instance =
          xr::SiteInstanceForIdentity(params.browser->GetProfile(), url,
                                      *xr_identity);
      if (xr_site_instance) {
        initial_site_instance_for_new_contents = std::move(xr_site_instance);
      } else {
        // SPIKE-ONLY fail-open. Production must fail closed (Plan §8.3):
        // an identity that cannot be bound to its partition must not open a
        // tab in the default partition. Recorded in ADR-0042.
        LOG(ERROR) << "xr: identity " << xr_identity->partition_domain()
                   << " could not be bound to a StoragePartition; opening the "
                   << "tab in the profile default (SPIKE-ONLY fail-open)";
      }
    }
  }
#endif  // BUILDFLAG(ENABLE_XR_SPIKE)
"""

BUILD_ANCHOR = """  if (!is_android) {
    sources += [
      "browser_navigator.cc",
      "browser_navigator_tab_modal.cc",
    ]
"""
BUILD_NEW = """  if (!is_android) {
    sources += [
      "browser_navigator.cc",
      "browser_navigator_tab_modal.cc",
    ]

    if (enable_xr_spike) {
      sources += [
        "../../xr/xr_identity.cc",
        "../../xr/xr_identity.h",
        "../../xr/xr_seam_override.cc",
        "../../xr/xr_seam_override.h",
      ]
      deps += [ "//chrome/browser/xr:identity_seam" ]
    }
"""


class SpecError(Exception):
    """Raised when the spec or the payloads are unusable (fail-closed)."""


def check_paths(paths: list[str]) -> list[str]:
    """Never-list enforcement. Returns refusals (empty list == allowed)."""
    refusals: list[str] = []
    for p in paths:
        if p.startswith(FORBIDDEN_PREFIXES):
            refusals.append(
                f"{p}: forbidden by the §12.7 never-list (spike patches touch "
                f"chrome/browser/** only)")
        elif not p.startswith(ALLOWED_PREFIXES):
            refusals.append(
                f"{p}: outside the embedder layer ({', '.join(ALLOWED_PREFIXES)})")
    return refusals


def payloads(xr_core: Path) -> dict[str, Path]:
    """Map Chromium destination -> source file in the xr-core spike kit.

    Fails closed if the payload is missing: genpatch must never fall back to a
    remembered copy of a spike source.
    """
    base = xr_core / SPIKE_REL
    want = {
        HOOK_HEADER: base / "xr_identity.h",
        HOOK_SOURCE: base / "xr_identity.cc",
        OVERRIDE_HEADER: base / "xr_seam_override.h",
        OVERRIDE_SOURCE: base / "xr_seam_override.cc",
    }
    missing = [str(v) for v in want.values() if not v.is_file()]
    if missing:
        raise SpecError(
            "spike payload(s) missing under "
            f"{xr_core}/spike/identity_seam: {', '.join(missing)} — mount "
            "xr-core (docs/process/cross-repo-pin.md) or pass --xr-core")
    return want


def targets() -> list[dict]:
    """Ordered transforms: downloaded files first, then payloads."""
    return [
        {"path": NAVIGATOR, "fetch": True, "ops": [
            {"kind": "insert_after", "anchor": INCLUDE_ANCHOR, "text": INCLUDE_NEW},
            {"kind": "replace", "old": SITEINSTANCE_OLD, "new": SITEINSTANCE_NEW},
        ]},
        {"path": NAVIGATOR_BUILD, "fetch": True, "ops": [
            {"kind": "replace", "old": BUILD_ANCHOR, "new": BUILD_NEW},
        ]},
        {"path": HOOK_HEADER, "fetch": False, "ops": [{"kind": "create"}]},
        {"path": HOOK_SOURCE, "fetch": False, "ops": [{"kind": "create"}]},
        {"path": OVERRIDE_HEADER, "fetch": False, "ops": [{"kind": "create"}]},
        {"path": OVERRIDE_SOURCE, "fetch": False, "ops": [{"kind": "create"}]},
    ]
