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
# P13-P0-C: the closing form of the finality law. 0 (the default, and what CI
# runs on every push) judges every CLOSED phase strictly and lets the phase the
# tree declares in flight (docs/state/phase-base.json) be `state: "interim"` —
# the only shape that is legal for a bundle which must exist from the phase's
# first commit. 1 (`--phase-final`) is the CLOSING invocation: the in-flight
# phase is demanded final too, so a phase cannot close with the sentinel still
# in place. The clean-clone gate run recorded at a phase's final commit uses
# `--phase-final`; docs/process/ci-invocation.md carries the two invocations.
PHASE_FINAL=0

# Consume --keep-going/--via-ci-invocation/--phase-final (if present) and arm
# the tracer; set RANGE from the remaining first argument (the PR/push git
# range). Called BEFORE the gate bodies so `set -E` is in effect for the sourced
# gate functions too.
kr_parse_args() {
  local via_ci=0
  while :; do
    case "${1:-}" in
      --keep-going)
        KEEP_GOING=1
        shift
        set -E +e   # keep-going: a failing lane is traced, never aborting
        trap 'kr_lane_fail "$BASH_COMMAND"' ERR
        ;;
      --via-ci-invocation)
        via_ci=1
        shift
        ;;
      --phase-final)
        PHASE_FINAL=1
        shift
        ;;
      *) break ;;
    esac
  done
  RANGE="${1:-}"
  if [ "$via_ci" = "1" ]; then
    kr_ci_invocation "$RANGE"
  fi
}

# kr_ci_invocation — run the gate the way the WORKFLOW runs it (P0-A item 4).
#
# The workflow says:
#     tools/run_checks.sh "$CHECK_RANGE"        # direct exec, one argv
# `bash tools/run_checks.sh` cannot see a mode bit, an argv difference, or a
# `set -e`-with-range difference: bash IS the executable, so the file's mode is
# not load-bearing. That invisibility is exactly how the exec bit stayed
# dropped for three commits while every local run was green. This mode:
#   1. asserts BOTH index (100755 — what a runner checks out) and filesystem
#      executability, naming exit 126 and the fix instead of reproducing a
#      "Permission denied" nobody can read;
#   2. then `exec`s the literal workflow command line, so the local run and the
#      hosted step are the same process image, argv and cwd.
# The rule of record: "run the gate the way CI runs it."
# Docs: docs/process/ci-invocation.md.
kr_ci_invocation() {
  local range="$1" self="./tools/run_checks.sh" mode idx
  idx="$(git ls-files -s -- "$self" | awk '{print $1}')"
  mode="$(stat -c '%a' "$self" 2>/dev/null || echo '???')"
  if [ "$idx" != "100755" ] || [ ! -x "$self" ]; then
    echo "CI-INVOCATION FAIL: $self is not executable (index mode ${idx:-untracked}, filesystem mode $mode)."
    echo "  On a runner this is exactly: exit code 126, 'Process completed with exit code 126'."
    echo "  \`bash $self\` cannot see it (bash is the executable). Fix: git update-index --chmod=+x $self"
    return 1
  fi
  echo "== CI-invocation: exec $self ${range:-<no range: full history>} (the workflow's own command line) =="
  # Argv fidelity matters as much as the mode: with an empty CHECK_RANGE the
  # workflow calls the script with NO argument, not with "".
  if [ -n "$range" ]; then
    KR_CI_EXEC=1 exec "$self" "$range"
  else
    KR_CI_EXEC=1 exec "$self"
  fi
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
  # P14-P0-2: the final tally echoes the parity verdict — the honesty
  # mechanism. A phase may not report "gate green" while the parity line
  # said lanes were weaker locally; a reader of the gate's last lines sees
  # both facts, always, in both modes.
  if [ -n "${P14_PARITY_VERDICT:-}" ]; then
    echo "parity verdict: $P14_PARITY_VERDICT"
  fi
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
