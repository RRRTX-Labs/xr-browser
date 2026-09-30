# tools/negatives/p13_c06.sh — P13-C-P0.6 negatives: the SKIP-law SHAPE, pinned.
#
# The shape at the pin was correct and fragile-looking enough that a future edit
# would delete it:
#
#   if bash build/webui/panel-tests.sh; then :; elif [ $? -eq 77 ]; then
#     echo "SKIP: …"; else echo "FAIL: …"; die; fi
#
# Three exit codes, three meanings, one deleted `else` away from a silent pass —
# and it read `$?` out of a `then :` branch to do it. The fix is not "add a
# comment saying don't touch this": the three-way decision now lives in ONE
# function (p13_exit_code_lane in tools/checks/p13_gates.sh) whose command is an
# ARGUMENT, so all three branches can be driven from a scratch script here.
#
# This is the brief's C-0.6 case, verbatim: force exit 1 ⇒ FAIL and die; exit 77
# ⇒ visible SKIP; exit 0 ⇒ nothing.
#
# Also asserted: the FAIL branch actually stops the run (a `die` that returns is
# not a die), and the real lane the gate calls is the one under test — the
# negative drives the same function `run_checks.sh` calls, not a copy of it.
#
# Offline and deterministic: scratch scripts in $NEG_TMP, no node, no network.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The gate's `die` aborts the run; under this harness we want the abort
# OBSERVABLE without killing the harness, so the sourced function is run in a
# subshell and `die` is redefined to exit that subshell.
_p13c06_drive() {   # <exit-code> -> stdout of the lane, rc in $?
  local rc_want="$1" script="$NEG_TMP/c06-exit$1.sh"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'echo "scratch lane: exit %s"\n' "$rc_want"
    printf 'exit %s\n' "$rc_want"
  } > "$script"
  (
    set -euo pipefail
    PY="${PY:-python3}"
    die() { echo "NEGATIVE-DIE"; exit 1; }
    # shellcheck disable=SC1090,SC1091
    . "$REPO_ROOT/tools/checks/p13_gates.sh"
    p13_exit_code_lane "scratch lane" "the toolchain is absent" bash "$script"
  ) 2>&1
}

# --- 0: pass prints nothing verdict-shaped ----------------------------------
case_c06_zero_is_silent() {
  local out rc
  out="$(_p13c06_drive 0)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && ! printf '%s' "$out" | grep -qE 'FAIL|SKIP|NEGATIVE-DIE'; then
    echo "ok: exit 0 => no FAIL, no SKIP, no die (a pass is not announced as a skip)"
  else
    echo "NEGATIVE-FAIL: exit 0 must be silent (rc=$rc): $out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c06_zero_is_silent

# --- 77: VISIBLE skip, and the run continues --------------------------------
case_c06_77_is_a_visible_skip() {
  local out rc
  out="$(_p13c06_drive 77)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "SKIP: scratch lane skipped"; then
    echo "ok: exit 77 => visible SKIP naming the lane and the missing toolchain, run continues"
  else
    echo "NEGATIVE-FAIL: exit 77 must skip visibly and continue (rc=$rc): $out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c06_77_is_a_visible_skip

# --- 1: FAIL and DIE — the else branch is load-bearing ----------------------
case_c06_one_reddens_and_dies() {
  local out rc
  out="$(_p13c06_drive 1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q "FAIL: scratch lane failed (exit 1)" \
     && printf '%s' "$out" | grep -q "NEGATIVE-DIE"; then
    echo "ok: exit 1 => FAIL printed AND the run stops (the else branch is load-bearing)"
  else
    echo "NEGATIVE-FAIL: exit 1 must print FAIL and die (rc=$rc): $out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c06_one_reddens_and_dies

# --- any other nonzero exit is a FAIL, not a skip ---------------------------
case_c06_arbitrary_failure_is_not_a_skip() {
  local out rc
  out="$(_p13c06_drive 3)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q "FAIL: scratch lane failed (exit 3)"; then
    echo "ok: exit 3 is a FAILURE, never a skip (only 77 means 'not available here')"
  else
    echo "NEGATIVE-FAIL: exit 3 must FAIL, not skip (rc=$rc): $out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c06_arbitrary_failure_is_not_a_skip

# --- the real lane is the shape under test ---------------------------------
case_c06_real_lane_uses_the_pinned_helper() {
  local n
  n="$(grep -c 'p13_exit_code_lane' "$REPO_ROOT/tools/checks/p13_gates.sh" || true)"
  if [ "$n" -ge 4 ]; then
    echo "ok: the three panel lanes call the pinned helper ($n occurrences incl. its definition)"
  else
    echo "NEGATIVE-FAIL: the panel lanes no longer route through p13_exit_code_lane ($n occurrences)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c06_real_lane_uses_the_pinned_helper
