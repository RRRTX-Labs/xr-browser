# tools/negatives/p13_c04.sh — P13-C-P0.4 negatives: how a phase may stay open.
#
# P12's red at the pin, verbatim:
#
#   FAIL: evidence/P12/evidence.json: phase records head f96949914955, but no
#   ci-run row carries a matching head_sha for workflow 'governance' (T0-U2) —
#   a final-CI claim must point at the phase's own head, not an older one
#
# and its bundle has no `state` key at all (=> judged final by the fail-closed
# default) while eight `*-PENDING-*` rows remain. The brief permitted two
# answers and forbade a third: (a) declare `interim` with a dated reason, or
# (b) cite a GREEN `governance` run at P12's own recorded head. (b) is
# unavailable — a run four commits back cannot be created — so (a) is taken, and
# the law is tightened in the same commit so that (a) cannot become a free pass:
#
#   * `interim` outside the in-flight window is legal only IN WRITING: at least
#     one `not_done_by_design` row opening with an ISO date;
#   * the T0-U2 same-head claim binds FINAL bundles only — an interim bundle has
#     made no final-CI claim, so `phase_head`/`ci_claimed` are then its recorded
#     INTENT, which is what lets the closing commit satisfy it later.
#
# Cases:
#   1. non-in-flight phase, interim, dated reason => GREEN (the honest middle);
#   2. the same bundle with the date stripped => RED (no author, no date);
#   3. a bundle judged FINAL with the same unsatisfiable claim => RED (the
#      scoping did not disarm the law it scopes).
#
# Offline and deterministic: scratch trees, no network, no gate wiring.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13c04_tree <dir> <state|-> <reason-date|-> <row-status>
# A P12 bundle inside a tree whose phase-base declares P13 in flight.
_p13c04_tree() {
  local R="$1" state="$2" date="$3" status="${4:-BLOCKED-PENDING-T5}"
  rm -rf "$R"
  mkdir -p "$R/docs/state" "$R/evidence/P12/logs"
  printf '{"phase": "P13"}\n' > "$R/docs/state/phase-base.json"
  printf 'transcript\n' > "$R/evidence/P12/logs/local.txt"
  printf '# human gates (fixture)\n' > "$R/evidence/P12/human-gates.md"
  "$PY" - "$R" "$state" "$date" "$status" <<'PY'
import json, sys
R, state, date, status = sys.argv[1:5]
reason = ("2026-09-30 (P13-C-P0.4): this phase cannot cite a same-head ci-run "
          "because no green governance run exists at its recorded head")
if date == "-":
    reason = "this phase is still open, for reasons"
doc = {
    "phase": "P12", "generated": "2026-09-29", "plan": "docs/plans/x.md",
    "pin": "chromium " + "0" * 40,
    "repos": {"xr-browser": "0" * 40},
    "phase_head": "f96949914955b38e2c0204ef9792e685264672e7",
    "ci_claimed": ["governance"],
    "not_done_by_design": [reason],
    "dod_rows": [{"id": "P12-X-1", "dod": "a planted row", "status": status,
                  "source": "local-run", "evidence": ["logs/local.txt"]}],
}
if state != "-":
    doc["state"] = state
json.dump(doc, open(f"{R}/evidence/P12/evidence.json", "w"), indent=1)
PY
}

# --- 1: interim + a DATED reason, not in flight => green --------------------
case_c04_dated_interim_is_legal() {
  local R="$NEG_TMP/c04-dated" out rc
  _p13c04_tree "$R" interim date
  out="$("$PY" "$REPO_ROOT/tools/evidence_check.py" --repo "$R" --strict \
      --no-presence --only P12 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "DECLARED, not the in-flight phase"; }; then
    echo "ok: an open phase may say so in writing (dated interim is legal, and names itself)"
  else
    echo "NEGATIVE-FAIL: a dated interim bundle outside the in-flight window must be green (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c04_dated_interim_is_legal

# --- 2: the same bundle, date stripped => red -------------------------------
case_c04_undated_interim_reddens() {
  local R="$NEG_TMP/c04-undated"
  _p13c04_tree "$R" interim -
  neg_expect_reject "an undated interim outside the in-flight window reddens (no author, no date)" \
    "no dated not_done_by_design row" \
    "$PY" "$REPO_ROOT/tools/evidence_check.py" --repo "$R" --strict \
    --no-presence --only P12
}
neg_register c04_undated_interim_reddens

# --- 3: a FINAL bundle with the same claim => still red ---------------------
case_c04_final_bundle_still_needs_the_head() {
  local R="$NEG_TMP/c04-final"
  _p13c04_tree "$R" final date "VERIFIED"
  neg_expect_reject "the same-head claim still binds a FINAL bundle (the scoping did not disarm it)" \
    "no ci-run row carries a matching head_sha" \
    "$PY" "$REPO_ROOT/tools/evidence_check.py" --repo "$R" --strict \
    --no-presence --only P12
}
neg_register c04_final_bundle_still_needs_the_head
