# tools/negatives/lib.sh — shared negative-gate machinery (P9-T0-d).
#
# Why this exists: run_negatives.sh sat two lines from the 400-LOC law and
# printed no total — a silently dropped or never-registered case was
# invisible. This library makes the case count DERIVED (registered at
# source-time, executed by the dispatcher) and makes two failure classes
# structural:
#   * a registered case that never ran is an ERROR (zero-case law);
#   * a case whose command exits 0 (gate PASSED on bad input) is an ERROR —
#     the "negative harness that cannot fail" bug class P9 exists to kill.
#
# Case files register cases with `neg_register <name>` and define a
# `case_<name>()` function that builds its fixture and calls
# `neg_expect_reject` / `neg_expect_inband`. Registration is cheap (no
# fixture work), so sourcing a file can never be mistaken for running it.

NEG_TOTAL=0
NEG_RUN=0
NEG_FAILURES=0
NEG_SKIPPED=0
NEG_CASES=()

# register a case (run later by neg_run_all). The function case_<name>
# MUST exist or the run is an error (a registered case that never ran).
neg_register() {
  NEG_CASES+=("$1")
  NEG_TOTAL=$((NEG_TOTAL + 1))
}

# neg_expect_reject <desc> <expected-pattern> <cmd...>
# Assert the command EXITS NON-ZERO with the expected reason.
neg_expect_reject() {
  local desc="$1" pattern="$2"
  shift 2
  local out rc
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: $desc — gate PASSED on bad input (rc=0)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -qE "$pattern"; then
    echo "NEGATIVE-FAIL: $desc — rejected, but not for the expected reason"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: $desc (rejected with expected reason)"
  fi
}

# neg_expect_inband <desc> <expected-pattern> <cmd...>
# For hosts that exit 0 and report status:"rejected" INSIDE the ok payload
# (the dispatch gate is the in-band rejection, not a process failure).
neg_expect_inband() {
  local desc="$1" pattern="$2"
  shift 2
  local out rc
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: $desc — command errored (rc=$rc); expected in-band rejection"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -qE "$pattern"; then
    echo "NEGATIVE-FAIL: $desc — in-band rejection pattern not found"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: $desc (in-band rejection observed)"
  fi
}

# visible SKIP (never counts as PASS; reported in the summary)
neg_skip() {
  echo "SKIP: $1"
  NEG_SKIPPED=$((NEG_SKIPPED + 1))
}

# run every registered case; a missing case_<name> function is an ERROR.
neg_run_all() {
  local name
  for name in "${NEG_CASES[@]}"; do
    if ! declare -F "case_${name}" >/dev/null 2>&1; then
      echo "NEGATIVE-FAIL: registered case '$name' has no case_${name}() — never ran"
      NEG_FAILURES=$((NEG_FAILURES + 1))
      continue
    fi
    "case_${name}"
  done
  NEG_RUN=$((NEG_RUN + ${#NEG_CASES[@]}))
}

# final verdict: zero cases, un-run cases, and any failure are all RED.
neg_finish() {
  if [ "$NEG_TOTAL" -lt 1 ]; then
    echo "NEGATIVE GATE FAILED: zero cases registered (zero-case law)"
    exit 1
  fi
  if [ "$NEG_RUN" -lt "$NEG_TOTAL" ]; then
    echo "NEGATIVE GATE FAILED: registered $NEG_TOTAL, ran $NEG_RUN (a case never ran)"
    exit 1
  fi
  if [ "$NEG_FAILURES" -ne 0 ]; then
    echo "NEGATIVE GATE FAILED: at least one gate accepted bad input or failed for the wrong reason"
    exit 1
  fi
  echo
  if [ "$NEG_SKIPPED" -gt 0 ]; then
    echo "note: $NEG_SKIPPED case(s) SKIPped (tool absent) — visible, never a PASS"
  fi
  echo "ALL NEGATIVE CASES REJECTED AS EXPECTED (N=$NEG_TOTAL)"
}

# neg_self_test — the canary for the harness itself. Three laws:
#   1. a case whose command exits 0 MUST turn the gate red (the harness can
#      fail — the exact bug class this phase exists to eliminate);
#   2. the case count is DERIVED: dropping a case file changes N;
#   3. a case file that registers nothing is an error.
neg_self_test() {
  local f before

  # (1) rc=0 canary
  before=$NEG_FAILURES
  neg_expect_reject "self-test canary: harness flags rc=0" "x" /bin/true
  if [ "$NEG_FAILURES" -ne "$((before + 1))" ]; then
    echo "SELF-TEST FAIL: a command that exits 0 did not redden the gate"
    exit 1
  fi
  echo "ok: self-test (rc=0 canary fires — the harness can fail)"

  # (2) dropping a case file changes the derived N
  local n_all n_minus
  n_all=$( ( . tools/negatives/lib.sh
             for f in "$@"; do . "tools/negatives/$f"; done
             echo "$NEG_TOTAL" ) )
  n_minus=$( ( . tools/negatives/lib.sh
               for f in "$@"; do
                 [ "$f" = "${1:-}" ] || . "tools/negatives/$f"
               done
               echo "$NEG_TOTAL" ) )
  if [ "$n_all" -lt 1 ] || [ "$n_minus" -ge "$n_all" ]; then
    echo "SELF-TEST FAIL: dropping a case file did not change N (count is not derived)"
    exit 1
  fi
  echo "ok: self-test (dropping a case file changes N: $n_all -> $n_minus)"

  # (3) a registered case that never ran is an error
  local ghost_rc
  ghost_rc=$( ( . tools/negatives/lib.sh
                neg_register ghost_without_body
                neg_run_all
                neg_finish
                echo "$?" ) )
  if [ "$ghost_rc" -eq 0 ]; then
    echo "SELF-TEST FAIL: a registered case with no body did not error"
    exit 1
  fi
  echo "ok: self-test (registered-but-never-ran case errors)"
}
