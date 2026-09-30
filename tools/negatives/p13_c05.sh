# tools/negatives/p13_c05.sh — P13-C-P0.5 negatives: a cited path must exist.
#
# The class, found in the tree rather than imagined: `evidence/P13/human-gates.md`
# cites `docs/panel/breakage-report.md` twice as the HG-33 drill method, and that
# file does not exist (`ls docs/panel` → no such directory). A
# `NOT-RUN (method: <path>)` whose path dangles is not a method — it is a claim
# with a decorative citation, unfalsifiable by construction: the reader cannot
# run it, cannot see the instrument, and cannot tell a deliberate deferral from
# a typo. The same scan found `build/qa/perf/perf_budgets.py` (the tool is
# `gen_perf_budgets.py`) and a bundle whose brace citation lists four members,
# one of which was missing.
#
# Cases:
#   1. a P13+ bundle citing a path that does not exist            => RED, named;
#   2. the same tree with the cited file planted                  => GREEN;
#   3. a pre-law bundle with the identical dangling citation      => skipped and
#      COUNTED (grandfathering is declared, never silent — prior-phase evidence
#      is append-only, so rewriting P1's prose to satisfy a checker written
#      twelve phases later would be the worse act);
#   4. a brace citation whose members exist EXCEPT one            => RED (the
#      shorthand a bundle uses to list what it claims to be complete is not a
#      loophole).
#
# Offline and deterministic: scratch trees, no network.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCREF="$REPO_ROOT/tools/doc_reference_check.py"

# _p13c05_tree <dir> <phase> <citation> [--plant]
_p13c05_tree() {
  local R="$1" phase="$2" cite="$3" plant="${4:-}"
  rm -rf "$R"
  mkdir -p "$R/evidence/$phase" "$R/docs/plans"
  # the bundle's own `plan` field is a citation too, so the fixture plants it:
  # otherwise every case would redden on the fixture rather than on its subject.
  printf '# planted plan\n' > "$R/docs/plans/x.md"
  "$PY" - "$R" "$phase" "$cite" <<'PY'
import json, sys
R, phase, cite = sys.argv[1:4]
json.dump({"phase": phase, "generated": "2026-09-30", "plan": "docs/plans/x.md",
           "dod_rows": [{"id": f"{phase}-X-1", "dod": "a planted row",
                         "status": "VERIFIED", "source": "local-run",
                         "evidence": [cite]}]},
          open(f"{R}/evidence/{phase}/evidence.json", "w"), indent=1)
PY
  printf '# human gates (fixture)\n' > "$R/evidence/$phase/human-gates.md"
  if [ "$plant" = "--plant" ]; then
    local dir
    dir="$(dirname "$R/$cite")"
    mkdir -p "$dir"
    printf 'planted instrument\n' > "$R/$cite"
  fi
}

_p13c05_run() { "$PY" "$DOCREF" --repo "$1" 2>&1; }

# --- 1: a dangling citation in a P13+ bundle => red, and it NAMES the path ----
case_c05_dangling_citation_reddens() {
  local R="$NEG_TMP/c05-dangle" cite="build/qa/does_not_exist.py"
  _p13c05_tree "$R" P13 "$cite"
  neg_expect_reject "a dangling build/ citation in a P13 bundle reddens and is named" \
    "$cite" \
    _p13c05_run "$R"
}
neg_register c05_dangling_citation_reddens

# --- 2: plant the instrument => green ---------------------------------------
case_c05_planted_instrument_is_green() {
  local R="$NEG_TMP/c05-planted" cite="build/qa/does_not_exist.py" out rc
  _p13c05_tree "$R" P13 "$cite" --plant
  out="$(_p13c05_run "$R")" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "0 dangling citation(s)"; }; then
    echo "ok: control — the same bundle is green once the cited path exists"
  else
    echo "NEGATIVE-FAIL: planting the cited path must make it green (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c05_planted_instrument_is_green

# --- 3: a pre-law bundle is skipped AND counted -----------------------------
case_c05_prelaw_bundle_is_grandfathered() {
  local R="$NEG_TMP/c05-prelaw" out rc
  _p13c05_tree "$R" P9 "build/qa/does_not_exist.py"
  out="$(_p13c05_run "$R")" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "2 pre-law file(s) grandfathered"; }; then
    echo "ok: grandfathering is declared and counted, not silent"
  else
    echo "NEGATIVE-FAIL: a pre-law bundle must be skipped and counted (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c05_prelaw_bundle_is_grandfathered

# --- 4: a brace citation is expanded, and one bad member reddens -------------
case_c05_brace_citation_member_reddens() {
  local R="$NEG_TMP/c05-brace"
  mkdir -p "$R/evidence/P13/logs"
  printf 'x\n' > "$R/evidence/P13/evidence.json"
  printf 'x\n' > "$R/evidence/P13/human-gates.md"
  "$PY" -c "
import json, sys
R = sys.argv[1]
json.dump({'phase': 'P13', 'generated': '2026-09-30', 'plan': 'docs/plans/x.md',
           'dod_rows': [{'id': 'P13-EVIDENCE', 'dod': 'the bundle claims four things',
                         'status': 'BLOCKED-PENDING-EVIDENCE', 'source': 'local-run',
                         'evidence': ['evidence/P13/{evidence.json,human-gates.md,logs,report.md}']}]},
          open(f'{R}/evidence/P13/evidence.json', 'w'), indent=1)
" "$R"
  neg_expect_reject "a brace citation reddens when ONE member is missing (the shorthand is not a loophole)" \
    "evidence/P13/report.md" \
    _p13c05_run "$R"
}
neg_register c05_brace_citation_member_reddens
