# DEPS — single source of truth for pinned revisions (Plan §7.1, P2-T1).
#
# This file pins exactly two things: the Chromium revision and the xr-core
# revision. Everything else in the tree (GN argsets, toolchain pins, patch
# manifest) is *derived* from these two pins and may not re-pin inside the
# pins (Plan §4 P2 "do not re-pin inside pins"). The gclient-synthesized DEPS
# produced by build/sync.py is generated FROM this file, never edited by
# hand. Policy contract: docs/contracts/deps-pin-policy.md.
#
# Field -> task map (each entry is tied to the P2 task that created it):
#   chromium_rev   P2-T1 (research item #2, live-verified 2026-09-07)
#   xr_core_rev    lineage: P2-T3 created the pin; P4 advanced it to the
#                  identity-seam spike kit (1ee5f4c); P5 advanced it to the
#                  contract-freeze commit (ef24bcf); P6 advanced it to the
#                  policy-resolver commits (policy/, + CI-parity fortify fix);
#                  P7 advances it to the command-registry + four-views +
#                  window-chrome-skeleton commit (379c00e), then to the
#                  commands/tests Makefile default-goal CI fix (7e2cff2);
#                  P8-T1 advances it to the settings tree (65639bf);
#                  P8-T2 advances it to the token pipeline (de28f80),
#                  pair-bumped same-day per docs/process/cross-repo-pin.md;
#                  P9-T0-a advances it to the themes refusal-text
#                  canonicalization (e1fc22e);
#                  P9-T1..T4/T7 advance it through the browser-test fixtures
#                  (5fcc5a1), isolation matrix (30ed5ee), compat corpus
#                  (730584a), and the axe-core toolchain + npm allowlist
#                  (89bd2ed).
#   gclient_url_scheme  P2-T1 (pinned https remotes only; no ssh, no file://)
#
# Chromium pin provenance (see docs/state/research-log-P2.md R1):
#   milestone 152, stable version 152.0.7977.82, branch position 1669021
#   git SHA cross-checked tag 152.0.7977.82 -> commit via
#   chromium.googlesource.com (committer Chromium LUCI CQ, 2026-09-02).
#   Sub-revs (v8/skia/webrtc/angle/dawn/pdfium/devtools) are pinned by the
#   chosen Chromium DEPS at this SHA and are listed ONLY in the research log
#   as informational — never re-pinned here.

schema_version: 1
chromium_rev: "d04cdb24d67b081f6cf80200ffc5233f44b61109"   # Chromium 152.0.7977.82 (stable)
xr_core_rev: "e2566bb914853751cc0328e0f879ef0a4e5c946a"     # xr-core P10-T1: update verifier core + host + 9 green suites + BUILD.gn
gclient_url_scheme: "https"                                  # pinned https remotes only
chromium_milestone: 152
chromium_version: "152.0.7977.82"
pinned_on: "2026-09-07"
