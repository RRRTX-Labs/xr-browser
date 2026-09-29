# tools/negatives/p13_p0b.sh — P13-P0-B negative cases: the diagnosis machinery
# must be able to fail, and must never invent a cause.
#
# The brief's negative for P0-B is explicit: "a lane forced to fail in a local
# `act`-less harness — i.e. a unit test on the emitted line format — must prove
# the annotation text contains the lane name". That is case 1 below, run as a
# shell step exactly as a workflow step runs it. Cases 2–4 cover the triage
# tool's refusal semantics: a red run must name its annotations, and a missing
# fact must degrade to BLOCKED-NET rather than to a guess.
#
# Sourced by tools/run_negatives.sh through NEG_FILES (lib.sh, $PY, $NEG_TMP
# available; tools/scratch.sh already sourced).

# --- 1: the act-less annotation harness --------------------------------------
case_annotation_names_the_lane() {
  local out rc
  # A workflow step body, reduced to its essentials: capture preamble, a gate
  # that fails, exit non-zero. No `act`, no runner, no network.
  out="$(bash -c '. tools/ci_capture.sh governance; \
      echo "== a gate =="; \
      echo "FAIL: planted-gate (the harness must be able to fail)"; \
      false' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: the forced-failure step exited 0"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -qE '^::error::governance: .+ - .+$'; then
    echo "NEGATIVE-FAIL: no well-formed annotation was emitted"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'planted-gate'; then
    echo "NEGATIVE-FAIL: the annotation does not name the failing gate"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: a forced lane failure emits ::error::<lane>: <gate> - <reason>"
  fi
  # and the same body, succeeding, must emit NOTHING (no crying wolf)
  local out_ok
  out_ok="$(bash -c '. tools/ci_capture.sh governance; true' 2>&1)" || true
  if printf '%s' "$out_ok" | grep -q '::error::'; then
    echo "NEGATIVE-FAIL: a green step emitted a failure annotation"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: a green step emits no annotation (the harness is not crying wolf)"
  fi
}
neg_register annotation_names_the_lane

# --- 2: triage reads the public annotation off a recorded red SHA ------------
case_ci_triage_reads_the_annotation() {
  local sha
  sha="$(cat tools/fixtures/ci_triage/RED_SHA.txt)"
  neg_expect_reject "ci_triage --offline: the red fixture exits 1 and names the 126 annotation" \
    'exit code 126' \
    "$PY" tools/ci_triage.py --offline tools/fixtures/ci_triage --sha "$sha"
  neg_expect_reject "ci_triage --offline: the failing step name is surfaced" \
    'Governance checks' \
    "$PY" tools/ci_triage.py --offline tools/fixtures/ci_triage --sha "$sha"
}
neg_register ci_triage_reads_the_annotation

# --- 3: a missing fact is BLOCKED-NET, never a guess -------------------------
case_ci_triage_never_guesses() {
  local empty="$NEG_TMP/p0b-empty"
  mkdir -p "$empty"
  neg_expect_reject "ci_triage --offline with no fixtures: BLOCKED-NET, not a verdict" \
    'BLOCKED-NET.*fixture missing' \
    "$PY" tools/ci_triage.py --offline "$empty" --sha 0000000000000000000000000000000000000000
  # The refusal must not carry a verdict line (that would be the guess).
  local out
  out="$("$PY" tools/ci_triage.py --offline "$empty" --sha 0000000000000000000000000000000000000000 2>&1)" || true
  if printf '%s' "$out" | grep -q 'verdict:'; then
    echo "NEGATIVE-FAIL: the blocked path printed a verdict — that is the guess"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: the blocked path printed no verdict (nothing invented)"
  fi
}
neg_register ci_triage_never_guesses

# --- 4: the annotation extractor refuses an empty transcript -----------------
case_annotation_refuses_an_empty_log() {
  local log="$NEG_TMP/p0b-clean.log"
  printf '== plan pin ==\nPASS: plan_pin_check\n' > "$log"
  neg_expect_reject "gate_annotation: a clean transcript yields no annotation (exit 1)" \
    'reason unavailable' \
    "$PY" tools/gate_annotation.py --lane governance --log "$log"
}
neg_register annotation_refuses_an_empty_log
