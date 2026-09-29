# tools/checks/p13_gates.sh — the P13 gate sections of run_checks.sh.
#
# Same split-by-size-law reason as p9_gates.sh / p11_gates.sh / p12_gates.sh:
# the dispatcher sits at the <=380-line touched-file ceiling, so P13's gates
# live here as functions called from the right point in the sequence. Sourced
# by tools/run_checks.sh; uses $PY and $RANGE, and runs under the caller's
# `set -euo pipefail` (an `exit 1` here ends the run, exactly as an inline
# block would).

p13_evidence_bundles() {
  # The bundle lane (P13-P0-C, moved out of run_checks.sh by the size law).
  # Contract: docs/contracts/evidence-bundle-v1.md. Two invocations, one law:
  #   * the DEFAULT run is what CI does on every push — strict over every phase
  #     newer than the P2 legacy exemption, with the declared in-flight phase
  #     allowed to be `state: "interim"`;
  #   * `run_checks.sh --phase-final` is the CLOSING run — the in-flight phase
  #     must be final too (report.md, a declared head, a same-head ci-run row
  #     per claimed workflow). That is the invocation the phase's final commit
  #     and the clean-clone gate record use, so "close the phase" cannot happen
  #     with sentinels still standing.
  echo "== evidence bundles (contract: docs/contracts/evidence-bundle-v1.md) =="
  "$PY" tools/evidence_check.py
  # strict: auto-covers every bundle newer than the P2 legacy exemption (P3+);
  # P1/P2 stay exempt per the HG-25 ruling (no hardcoded list to forget, T0).
  # T0-U2: phase_head bundles print both heads compared (`head-match:` lines).
  if [ "${PHASE_FINAL:-0}" = "1" ]; then
    echo " (--phase-final: the declared in-flight phase must be final too)"
    "$PY" tools/evidence_check.py --strict --require-phase-final
  else
    "$PY" tools/evidence_check.py --strict
  fi
}

p13_p0_gates() {
  # P0-A: the index-mode law, in both of its forms.
  #   Law 1 — every workflow-invoked DIRECT entry point is 100755 in the index
  #           (`bash`/`python3 <path>` are exempt, and the tool says so in its
  #           own output rather than silently passing them);
  #   Law 2 — no commit in the pushed range drops an exec bit (--range). The
  #           5e3d1d4 class, caught at push time with the commit named.
  echo "== P13-P0-A: workflow entry-point modes (index 100755 for direct exec) + mode-drift law =="
  if [ -n "$RANGE" ]; then
    "$PY" tools/entrypoint_mode_check.py --repo . --range "$RANGE"
  else
    "$PY" tools/entrypoint_mode_check.py --repo .
  fi
  echo "== P13-P0-A: in-place rewrites preserve the mode (the defect shape loses it) =="
  "$PY" tools/inplace.py --self-test

  # P0-B: the diagnosis path. The triage tool's self-test is offline and
  # fixture-backed, so this lane never needs the network; the live endpoint set
  # is exercised by the scheduled-lane checker and by the hosted call in the
  # phase report.
  echo "== P13-P0-B: CI triage reads the public check-run/annotation endpoints (offline self-test) =="
  "$PY" tools/ci_triage.py --self-test

  # P0-C: the phase-finality law. The self-test proves each rule bites offline
  # (final vocabulary + PENDING, append-only corrections, report.md, in-flight
  # interim, invented states, pre-law scoping); the live judgement runs in the
  # evidence-bundle section above via --require-phase-final, so a bundle that
  # regresses reddens on the bundle line, not here.
  echo "== P13-P0-C: phase-finality law (state interim|final; the 12-section report) =="
  "$PY" tools/evidence_finality.py --self-test
}
