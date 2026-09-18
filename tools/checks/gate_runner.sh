# tools/checks/gate_runner.sh — the keep-going legs of run_checks.sh (T0-U1).
#
# Why this exists. The push gate is `set -euo pipefail`, so it ABORTS at its
# first FAIL; one broken optional dependency then conceals every downstream
# verdict — which is how a red gate took a whole phase to surface (108 PASS
# then FAIL at lane 109, 27 lanes never run). The default stays exactly that
# (fail-fast; byte-identical to every prior phase). `--keep-going` is the
# diagnosability mode: every lane runs, every failure is reported with the
# failing command text, and the runner exits 1 with the count.
#
# run_checks.sh is the DISPATCHER and sits at the <=380 touched-file law
# ceiling, so this file carries the flag parsing, the ERR trap, `die` (the
# keep-going-aware replacement for a fallback `exit 1`), and the final tally.
# Sourced by tools/run_checks.sh; nothing here runs unless called.

KEEP_GOING=0
RANGE=""
KR_FAILED=0

# Consume --keep-going (if present) and arm the tracer; set RANGE from the
# remaining first argument (the PR/push git range). Called BEFORE the gate
# bodies so `set -E` is in effect for the sourced gate functions too.
kr_parse_args() {
  if [ "${1:-}" = "--keep-going" ]; then
    KEEP_GOING=1
    shift
    set -E +e   # keep-going: a failing lane is traced, never aborting
    trap 'kr_lane_fail "$BASH_COMMAND"' ERR
  fi
  RANGE="${1:-}"
}

# ERR-trap body: record one lane failure and continue. Returns 0 so the trap
# never recurses and never aborts the shell it runs in.
kr_lane_fail() {
  KR_FAILED=$((KR_FAILED + 1))
  printf 'LANE FAIL (keep-going): %s\n' "$*" >&2
  return 0
}

# Fail-fast exit under the default gate; a counted, non-aborting record under
# --keep-going. Replaces the fallback `exit 1` in the gate bodies so both
# modes share one failure ledger.
die() {
  KR_FAILED=$((KR_FAILED + 1))
  if [ "$KEEP_GOING" = "1" ]; then
    # continue at top level OR return from a sourcing gate function; the
    # stderr-suppressed `return 0` keeps the top-level case quiet because
    # `return` is invalid outside a function/sourced file
    return 0 2>/dev/null || true
  fi
  exit 1
}

# The gate's last line. Default: the all-green banner. --keep-going: exit 1
# with the tally when any lane failed (the failures were already printed with
# their command text), else the all-green banner.
kr_finish() {
  if [ "$KEEP_GOING" = "1" ]; then
    if [ "$KR_FAILED" -gt 0 ]; then
      echo "FAIL: $KR_FAILED lane(s) failed (see the 'LANE FAIL (keep-going)'"
      echo "lines above; the default gate aborts at the first of them)"
      exit 1
    fi
    echo "PASS: --keep-going run complete — every lane green"
    exit 0
  fi
  echo "== ALL GOVERNANCE CHECKS PASSED =="
  exit 0
}
