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
