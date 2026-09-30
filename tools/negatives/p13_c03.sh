# tools/negatives/p13_c03.sh — P13-C-P0.3 negatives: closure is CLAIMED.
#
# Reproduced at e503f9e, verbatim from the hosted lane:
#
#   FAIL: evidence/P13/evidence.json: --require-phase-final is set and P13 is
#   the phase closing at this commit, but the bundle still says 'interim' —
#   flip it to 'final' with its report.md and its same-head ci-run rows, or
#   leave the phase open (P13-P0-C)
#
# As wired, the requirement triggered on *being the newest phase in
# docs/state/phase-base.json*, so no in-flight commit could ever be green: the
# presence law requires the bundle from the phase's FIRST commit, and a bundle
# that must exist from commit one cannot be final from commit one. The law was
# right and its TRIGGER was wrong, so `--require-phase-final` reddened
# `governance` for the whole of every future phase while reporting a demand no
# commit could meet.
#
# The fix: closure is claimed, not inferred. A commit that closes a phase
# carries `Phase-Close: P<n>` (validated the way tools/dr_parse.py validates
# Register-Change), and only then does the finality law bind that phase.
#
#   1. trailer + interim            => RED (the claim is checked)
#   2. no trailer + interim         => GREEN with the note "phase open; no
#                                      closure claimed — not a verdict"
#   3. trailer + final, but no same-head ci-run row => RED (a closure claim with
#                                      a final bundle must still point at CI
#                                      that actually ran at the recorded head)
#   4. no trailer, but the bundle is FINAL and broken => the ordinary final rules
#                                      still apply (the carve-out is for an
#                                      OPEN phase, never a shield for a bad one)
#
# Deterministic and offline: scratch git repos, no network. Sourced by
# tools/run_negatives.sh.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13c03_repo <dir> <state> <trailer:yes|no> <report:yes|no> <ci-run:yes|no>
_p13c03_repo() {
  local D="$1" state="$2" trailer="$3" report="${4:-yes}" ci="${5:-no}"
  rm -rf "$D"
  mkdir -p "$D/docs/state" "$D/evidence/P13"
  # the whole tools/ tree: evidence_check pulls in evidence_strict ->
  # runner_caps -> ... and a fixture that copies four files tests the import
  # graph rather than the law it was written for.
  cp -r "$REPO_ROOT/tools" "$D/tools"
  rm -rf "$D/tools/__pycache__" "$D/tools/tests/__pycache__"
  echo '{"phase": "P13", "base_commit": "0000000000000000000000000000000000000000"}' \
    > "$D/docs/state/phase-base.json"
  printf '# human gates (fixture)\n' > "$D/evidence/P13/human-gates.md"
  if [ "$report" = yes ]; then
    printf '# fixture report\n\n①②③④⑤⑥⑦⑧⑨⑩⑪⑫\n' > "$D/evidence/P13/report.md"
  fi
  "$PY" - "$D" "$state" "$ci" <<'PYEOF'
import json, sys
d, state, ci = sys.argv[1], sys.argv[2], sys.argv[3]
doc = {
    "phase": "P13",
    "state": state,
    "generated": "fixture",
    "plan": "fixture",
    "pin": "0000000000000000000000000000000000000000",
    "repos": {"xr-browser": "0" * 40},
    "source_labels": ["fixture"],
    "verdict_vocabulary": ["VERIFIED", "HUMAN-GATED", "PARTIAL", "NOT-BY-DESIGN"],
    "dod_rows": [{
        "id": "FIXTURE-1", "dod": "fixture row", "status": "VERIFIED" if state == "final" else "BLOCKED-PENDING-X",
        "source": "fixture", "evidence": ["evidence/P13/human-gates.md"],
    }],
    # P9-T12: an open row (PARTIAL/BLOCKED*/HUMAN-GATED) requires the reason.
    "not_done_by_design": ["fixture: the row is open on purpose, so the "
                           "finality carve-out is the thing under test"],
}
if state == "final":
    doc["phase_head"] = "0" * 40
    doc["ci_claimed"] = ["governance"]
if ci == "yes":
    doc["ci_runs"] = [{"workflow": "governance", "head_sha": "0" * 40,
                       "run_id": 1, "conclusion": "success"}]
json.dump(doc, open(f"{d}/evidence/P13/evidence.json", "w"), indent=1)
PYEOF
  git -C "$D" init -q
  git -C "$D" config user.email f@example.invalid
  git -C "$D" config user.name fixture
  git -C "$D" add -A
  if [ "$trailer" = yes ]; then
    git -C "$D" commit -qm "P13: closing the phase" -m "Phase-Close: P13"
  else
    git -C "$D" commit -qm "P13: work in flight"
  fi
}

_p13c03_run() {   # <dir> -> stdout+stderr, rc in $?
  "$PY" "$1/tools/evidence_check.py" --repo "$1" --strict --only P13 \
    --require-phase-final --no-presence 2>&1
}

# --- 1: trailer + interim => RED ---------------------------------------------
case_c03_trailer_without_final_reddens() {
  local D="$NEG_TMP/c03-claim"
  _p13c03_repo "$D" interim yes
  neg_expect_reject "finality: a Phase-Close trailer on an interim bundle reddens" \
    'Phase-Close: P13.*claims this phase is closing' \
    _p13c03_run "$D"
}
neg_register c03_trailer_without_final_reddens

# --- 2: no trailer + interim => GREEN, with the note ------------------------
case_c03_no_trailer_is_green_with_note() {
  local D="$NEG_TMP/c03-open" out rc
  _p13c03_repo "$D" interim no
  out="$(_p13c03_run "$D")" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "phase open; no closure claimed"; }; then
    echo "ok: finality: no closure claimed => an open in-flight phase is GREEN with the note"
  else
    echo "NEGATIVE-FAIL: an in-flight phase with no closure claim must be green with the note (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c03_no_trailer_is_green_with_note

# --- 3: trailer + final but no same-head ci-run => RED ----------------------
case_c03_final_without_same_head_ci_reddens() {
  local D="$NEG_TMP/c03-noci"
  _p13c03_repo "$D" final yes yes no
  neg_expect_reject "finality: a closure claim with no same-head ci-run row reddens" \
    'ci-run|ci_run|T0-U2|no ci-run row' \
    _p13c03_run "$D"
}
neg_register c03_final_without_same_head_ci_reddens

# --- 4: the carve-out is for an OPEN phase, never a shield for a bad one ----
case_c03_final_bundle_is_judged_without_trailer() {
  local D="$NEG_TMP/c03-finalbad"
  _p13c03_repo "$D" final no yes no
  neg_expect_reject "finality: a FINAL bundle is judged even with no trailer (the note is not a shield)" \
    'ci-run|ci_run|T0-U2|no ci-run row' \
    _p13c03_run "$D"
}
neg_register c03_final_bundle_is_judged_without_trailer
