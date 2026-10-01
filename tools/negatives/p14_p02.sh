# tools/negatives/p14_p02.sh — P14-P0-2 negative cases: the parity tool must
# be able to fail, must never be a gate red, and the lane must redden on a
# missing verdict.
#
# The brief's negative for P0-2 is the tool's own --self-test; these cases
# guard the three contracts around it:
#   1. a capability gap prints PARTIAL naming the gap AND STILL EXITS 0 —
#      if someone later makes PARTIAL a gate red, this case fails, because
#      "not a gate red" is the law that makes the tool honest (a red gate
#      trains people to install everything or to ignore the lane);
#   2. a sabotaged detector must FAIL its own --self-test — a self-test that
#      cannot fail is decorative, so the sabotage (verdict_of always PASS) is
#      planted in a scratch COPY and the self-test must catch it;
#   3. the gate lane reddens when the tool prints no verdict line — a run
#      without a verdict is not a verdict (the never-silent law);
#   4. ci_triage's 429 classification says RATE-LIMITED and never ADMIN-ONLY,
#      and names the /rate_limit discriminator (C-0.7: the P13 403-from-quota
#      incident must be impossible to repeat as folklore).
#
# Offline and deterministic: pure functions, scratch copies, a PATH stub.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PARITY="$REPO_ROOT/tools/ci_parity_check.py"
PROBES="$REPO_ROOT/tools/ci_parity_probes.py"

neg_register parity_gap_is_partial_and_exits_zero
case_parity_gap_is_partial_and_exits_zero() {
  neg_expect_inband \
    "a gap host prints PARTIAL naming the gap, exit 0 by design" \
    'ci-parity: PARTIAL .*faketime' \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" -c "
import sys; sys.path.insert(0, 'tools')
import ci_parity_check as c
rows = c.tool_rows({'actionlint', 'shellcheck'},
                   {'actionlint': 'x', 'shellcheck': 'x', 'faketime': 'x'})
v, s = c.verdict_of(rows, {'status': 'PASS'}, {'closure': 'PASS'}, [])
print('ci-parity:', v, '—', '; '.join(s))
"
}

neg_register parity_selftest_catches_a_sabotaged_detector
case_parity_selftest_catches_a_sabotaged_detector() {
  local cp="$NEG_TMP/parity-sabotage"
  rm -rf "$cp"; mkdir -p "$cp"
  cp "$PARITY" "$PROBES" "$cp/"
  # Sabotage: verdict_of always returns PASS — the detector that cannot say
  # PARTIAL is the detector that detects nothing.
  "$PY" - "$cp/ci_parity_check.py" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
needle = 'return ("PARTIAL", stricter) if stricter else ("PASS", [])'
assert needle in src, "sabotage anchor moved — update the negative"
open(p, "w").write(src.replace(needle, 'return "PASS", []'))
PY
  neg_expect_reject \
    "a sabotaged verdict_of fails its own --self-test" \
    'FAIL: ci_parity --self-test' \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$cp/ci_parity_check.py" --self-test
}

neg_register parity_lane_reddens_on_a_missing_verdict_line
case_parity_lane_reddens_on_a_missing_verdict_line() {
  local stubdir="$NEG_TMP/stub-bin"
  rm -rf "$stubdir"; mkdir -p "$stubdir"
  printf '#!/bin/sh\necho "== ci-parity =="\necho "rows, but no verdict line"\n' \
    > "$stubdir/python3"
  chmod +x "$stubdir/python3"
  local out rc
  out="$(cd "$REPO_ROOT" && PATH="$stubdir:$PATH" PY=python3 bash -c '
      . tools/checks/gate_runner.sh
      . tools/checks/p14_gates.sh
      p14_parity' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: the parity lane stayed green on a verdict-less run"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! { neg_out_file "$out"; neg_out_has "no .ci-parity.. verdict line"; }; then
    echo "NEGATIVE-FAIL: reddened, but not for the missing-verdict reason"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: a run with no verdict line reddens the lane (never-silent law)"
  fi
}

neg_register triage_429_is_rate_limited_never_admin_only
case_triage_429_is_rate_limited_never_admin_only() {
  local out rc
  out="$(cd "$REPO_ROOT" && PYTHONDONTWRITEBYTECODE=1 "$PY" -c "
import sys; sys.path.insert(0, 'tools')
import ci_triage
print(ci_triage.classify_refusal('/repos/x/actions/runs/1/logs',
                                 'HTTP 429 fetching https://api.github.com/x'))
" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: the classifier itself errored (rc=$rc)"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! { neg_out_file "$out"; neg_out_has_fixed 'RATE-LIMITED'; }; then
    echo "NEGATIVE-FAIL: a 429 is not classified RATE-LIMITED"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif { neg_out_file "$out"; neg_out_has_fixed 'ADMIN-ONLY'; }; then
    echo "NEGATIVE-FAIL: a 429 was labelled ADMIN-ONLY — the C-0.7 confusion is back"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! { neg_out_file "$out"; neg_out_has_fixed '/rate_limit'; }; then
    echo "NEGATIVE-FAIL: the discriminator (/rate_limit) is not named"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: a 429 reads RATE-LIMITED with the /rate_limit discriminator, never ADMIN-ONLY"
  fi
}
