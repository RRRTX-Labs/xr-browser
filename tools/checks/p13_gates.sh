# tools/checks/p13_gates.sh — the P13 gate sections of run_checks.sh.
#
# Same split-by-size-law reason as p9_gates.sh / p11_gates.sh / p12_gates.sh:
# the dispatcher sits at the <=380-line touched-file ceiling, so P13's gates
# live here as functions called from the right point in the sequence. Sourced
# by tools/run_checks.sh; uses $PY and $RANGE, and runs under the caller's
# `set -euo pipefail` (an `exit 1` here ends the run, exactly as an inline
# block would).

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
}
