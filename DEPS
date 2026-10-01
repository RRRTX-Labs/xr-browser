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
#                  (89bd2ed); P10-T1 to the update verifier core (e2566bb);
#                  P11-T0-a/b to the published update host_protocol.md
#                  (c5034ec) and the single shared common/core primitives
#                  move (895ae6f), pair-bumped same-day per
#                  docs/process/cross-repo-pin.md; P11-T0-c to the
#                  reject-tested required-int-field battery (85289cd) —
#                  T0-b's resample surfaced a surviving deny-guard mutant
#                  in policy store.cc and the test debt was paid at once.
#                  P12 advances it to the pin P12 closed on (1850241), the base
#                  of P13's work; P13 advances it through the panel frame
#                  (focus-trap.ts, tab-registry.ts, tabs.json, tab-strip.ts and
#                  the site/observatory/update/sent/breakage tabs with their node
#                  suites) to the C-5 follow-on at 4353d36 — the revision P13's
#                  ci-run rows cite, recorded in evidence/P13/evidence.json. The
#                  lineage lines for P12/P13 are added here at P13's freeze
#                  commit: the pin was pair-bumped with each commit, but this
#                  block still ended at P11 (found closing the phase).
#                  P14 advances it to the identity core (420d854): the
#                  opaque mint + lifecycle with purge-and-verify + cap/
#                  hibernation (85e4a2a), templates (23e3acb), binding
#                  (2b5a576), attribution (70a793e), the identity host +
#                  protocol doc (e52bea2), and the fleet-timebox fuzz
#                  oracle (420d854) and the host typed-error exit fix
#                  (a5aef55), the session store (P14-T8, 3973ff3), the isolation-matrix identity cells (P14-T6/sec-req-2, 05b83eb), the out-of-tree test build fix (1572031), and the identity hygiene set (sha256 shim + gitignore, 7d70013) —
#                  pair-bumped same-day per docs/process/cross-repo-pin.md.
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
xr_core_rev: "7d70013dd3158608879255223738dbc733d7a6ba"     # xr-core 0dd5748 (C-1b..C-5: site-tab, observatory-tab, update-tab, sent-tab + their node suites; the registry lane\'s inventory, grdp and roster reads) = P13-T1/T7 + P13-C-P0.1 (ui/panel/tabs.json, tab-registry.ts) + P13-C-P0.1b (ui/panel/tab-strip.ts — the registry-driven tablist; registry diagnostics as machine tokens for l10n_extract R4). Pair-bumped same-day with each P13 commit per docs/process/cross-repo-pin.md.
gclient_url_scheme: "https"                                  # pinned https remotes only
chromium_milestone: 152
chromium_version: "152.0.7977.82"
pinned_on: "2026-09-07"
