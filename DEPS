# DEPS — single source of truth for pinned revisions (Plan §7.1, P2-T1).
#
# This file pins exactly two things: the Chromium revision and the xr-core
# revision. Everything else in the tree (GN argsets, toolchain pins, patch
# manifest) is *derived* from these two pins and may not re-pin inside the
# pins (Plan §4 P2 "do not re-pin inside pins"). The gclient-synthesized DEPS
# produced by buildsys/sync.py is generated FROM this file, never edited by
# hand. Policy contract: docs/contracts/deps-pin-policy.md.
#
# Field -> task map (each entry is tied to the P2 task that created it):
#   chromium_rev   P2-T1 (research item #2, live-verified 2026-09-07)
#   xr_core_rev    P2-T0/T-final (xr-core HEAD after this phase's commits)
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
xr_core_rev: "6fb5411bab4d95800a3e56848cecb3013f9bd33f"     # xr-core HEAD — re-pinned at T-final
gclient_url_scheme: "https"                                  # pinned https remotes only
chromium_milestone: 152
chromium_version: "152.0.7977.82"
pinned_on: "2026-09-07"
