# tools/checks/p9_gates.sh — the P9 gate sections of run_checks.sh.
#
# P13-P0-A split by the touched-file size law (<=380 lines): the P0-A work has
# to ADD lanes to the dispatcher, and the dispatcher was already at 380. Same
# fix as P11-T0-e and P12-T1 applied to the gate bodies that were still inline
# here: move a coherent block into a function-file, keep the dispatcher thin.
# The lanes themselves are unchanged and keep their original order — T1..T4
# (browser-test fixtures, isolation-matrix cells, leaktest, compat corpus) run
# exactly where they ran before, between the P9-T0-a parity lanes and the
# P9-T5 perf lanes. Sourced by tools/run_checks.sh; uses $PY and runs under the
# caller's `set -euo pipefail` (an `exit 1` here ends the run, as before).

p9_test_lanes() {
  echo "== P9-T1: browser-test fixture lint (fixtures are the spec) =="
  "$PY" tools/browser_test_lint.py --repo .

  echo "== P9-T2: isolation-matrix fake cells (identity x mechanism) =="
  "$PY" tools/isolation_matrix.py --repo . --check

  echo "== P9-T3: leaktest self-test + loopback canary (0 leaks) =="
  "$PY" tools/leaktest.py --repo . --self-test
  "$PY" tools/leaktest.py --repo . --mode loopback

  echo "== P9-T4: compat corpus validate + offline replay =="
  "$PY" tools/compat.py --repo . validate
  "$PY" tools/compat.py --repo . replay
}
