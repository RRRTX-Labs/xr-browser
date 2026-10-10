# tools/checks/p14_gates.sh — the P14 gate sections of run_checks.sh.
#
# Same split-by-size-law reason as p9/p11/p12/p13_gates.sh: the dispatcher
# stays under the 380-line touched-file ceiling, the bodies live here.
#
# Sourced by tools/run_checks.sh; nothing here runs unless called.

p14_parity() {
  # P14-P0-2: the local-vs-CI capability parity line. Deliberately NOT a
  # gate red — a laptop legitimately lacks CI's tools — but the final tally
  # (kr_finish) echoes its verdict line, and evidence/P<n>/report.md §⑨ must
  # quote it: a phase may not report "gate green" while the parity line says
  # lanes were weaker locally. The tool re-probes every run (network rows are
  # never inherited from a note) and exits 0 for PASS and PARTIAL alike; only
  # its own --self-test failure (exit 1) reddens, because a broken detector
  # is worse than no detector.
  echo "== P14-P0-2: ci-parity (local capability vs hosted lanes; a printed fact, never a gate red) =="
  local out rc had_e=0
  case $- in *e*) had_e=1 ;; esac
  set +e
  out="$("$PY" tools/ci_parity_check.py 2>&1)"
  rc=$?
  [ "$had_e" = "1" ] && set -e
  printf '%s\n' "$out"
  if [ "$rc" -ne 0 ]; then
    echo "FAIL: ci_parity_check exited $rc (only its --self-test may fail; the probe itself never reddens the gate)"
    die
    return
  fi
  # The verdict line the tally re-echoes: "ci-parity: PASS …" or
  # "ci-parity: PARTIAL (N lane(s) will be stricter on CI: …)". A run that
  # printed no verdict line is not a verdict (the never-silent law).
  P14_PARITY_VERDICT="$(printf '%s\n' "$out" | grep '^ci-parity: ' | tail -1)"
  if [ -z "$P14_PARITY_VERDICT" ]; then
    echo "FAIL: ci_parity_check printed no 'ci-parity:' verdict line"
    die
    return
  fi
}

p14_parity_selftest() {
  # The negative half: the tool's own --self-test (offline, deterministic)
  # must pass — it proves the verdict is a function of the host rather than
  # a constant, including the actionlint-without-shellcheck composite that
  # was the P13-CLOSE governance red.
  echo "== P14-P0-2: ci-parity --self-test (the detector can detect) =="
  "$PY" tools/ci_parity_check.py --self-test
}

p14c_ledger_identity() {
  # P14-CLOSE C-2 (P14-T5): ledger-identity-overlay-v1 — every golden vector
  # byte-identical across the compiled identity_host and fakes/ledger_identity.py,
  # identity_id required on every class, the frozen ActivityKind set read live,
  # and the zero-delta history oracle. g++/make absent => visible SKIP of the
  # C++ half (the Python half and every law still run), never a silent pass.
  echo "== P14-CLOSE C-2: ledger identity overlay (both backends, identity_id on every class, upstream zero-delta) =="
  p13_exit_code_lane "ledger overlay C++ parity" \
    "tool absent: g++/make; the Python half and every law still ran; local hint: apt-get install g++ make" \
    "$PY" tools/ledger_identity_check.py
}

p14c_identity_chrome() {
  # P14-CLOSE C-1 (P14-T4): the identity chrome. Three things are checked:
  #   * the state law + per-layout x per-theme STRUCTURAL snapshots (--check;
  #     a gate never rewrites them, --write is the deliberate regeneration);
  #   * the TypeScript core against the same snapshots under node:test;
  #   * --plant-drift, a scratch-copy core drift that MUST redden that suite.
  # Pixels are NOT-RUN (docs/qa/browser-harness.md#identity-chrome-visual).
  # Node/registry absent => visible SKIP (77) of the TS half, never a pass.
  echo "== P14-CLOSE C-1: identity chrome (state law + structural snapshots; TS core == snapshots; planted drift reddens) =="
  "$PY" tools/identity_chrome_check.py --check
  p13_exit_code_lane "identity-chrome core lane" \
    "node/toolchain unavailable" bash build/webui/identity-chrome-tests.sh
  p13_exit_code_lane "identity-chrome planted-drift lane" \
    "node/toolchain unavailable" bash build/webui/identity-chrome-tests.sh --plant-drift
}

p14c_identities_page() {
  # P14-CLOSE C-3 (P14-T7): the xr://identities dev page. The TS core runs
  # under node:test against the compiled identity_host's LIVE replies (every
  # page state, the release/nightly-test refusal included), and the planted
  # missing-state drift must redden that suite. The state-coverage and
  # dev-only laws are shield_state_check's (tools/identity_page_states.py);
  # the silence law is attention_check's. The rendered page is NOT-RUN
  # (docs/qa/browser-harness.md#identities-page-rendered).
  echo "== P14-CLOSE C-3: xr://identities dev page (TS core vs live host replies; planted drift reddens) =="
  p13_exit_code_lane "identities-page core lane" \
    "node/toolchain or g++/make unavailable" bash build/webui/identities-page-tests.sh
  p13_exit_code_lane "identities-page planted-drift lane" \
    "node/toolchain or g++/make unavailable" bash build/webui/identities-page-tests.sh --plant-drift
}
