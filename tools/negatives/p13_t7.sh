# tools/negatives/p13_t7.sh — P13-T7 negatives: the panel's perf budgets.
#
# T7's law is about what a number is ALLOWED to mean, so the negatives are all
# about refusal:
#
#   1. a PANEL row asserting a browser-side budget from a `trend` rig must be
#      REFUSED (the rig-class law, now exercised with the panel's own metric —
#      the cosmetic case proves the law exists, this proves it reaches the new
#      rows);
#   2. a `panel_*` surrogate that does not declare itself (`surrogate: true`)
#      must be REFUSED (a synthetic number presented as a Blink measurement is
#      the phase disqualifier);
#   3. the budget rows may come ONLY from build/qa/perf/gen_perf_budgets.py:
#      a hand-edited value in the committed JSON must make `--check` redden;
#   4. the committed trend input must carry the panel rows: drop them in a
#      scratch copy and `tools/panel_bench.py --check` must redden.
#
# Deterministic and offline (the comparator and the generator are pure stdlib).
# Sourced by tools/run_negatives.sh through NEG_FILES (lib.sh, $PY, $NEG_TMP).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_t13t7_bench() {   # <file> <metric> <value> <surrogate:yes|no>
  "$PY" - "$@" <<'PYEOF'
import json, sys
path, metric, value, surrogate = sys.argv[1:5]
row = {"metric": metric, "unit": "ms", "value_us": float(value),
       "sampled": True}
if surrogate == "yes":
    row["surrogate"] = True
doc = {"name": "planted panel bench (negative)", "rig_class": "trend",
       "rows": [row]}
open(path, "w", encoding="utf-8").write(json.dumps(doc, indent=1) + "\n")
PYEOF
}

# --- 1: a panel row may not assert the browser-side budget from a trend rig --
case_panel_trend_rig_may_not_assert_browser_budget() {
  local B="$NEG_TMP/t7-rigclass.json"
  _t13t7_bench "$B" panel_open_ms 1.0 yes
  neg_expect_reject "panel budget: a trend rig may not assert the browser-side panel_open_ms budget" \
    'trend rig cannot assert a browser-side budget' \
    "$PY" tools/perf_gate.py --repo . --bench "$B"
}
neg_register panel_trend_rig_may_not_assert_browser_budget

# --- 2: an undeclared surrogate must be refused ------------------------------
case_panel_surrogate_must_declare_itself() {
  local B="$NEG_TMP/t7-surrogate.json"
  _t13t7_bench "$B" panel_open_core_ms 0.004 no
  neg_expect_reject "panel surrogate: a panel_* number that does not say 'surrogate: true' is refused" \
    'surrogate/model measures in this sandbox' \
    "$PY" tools/perf_gate.py --repo . --bench "$B"
  # positive control: the same row, declaring itself, is accepted (NEUTRAL at
  # worst — a surrogate never reads MET)
  _t13t7_bench "$B" panel_open_core_ms 0.004 yes
  local out rc
  out="$("$PY" tools/perf_gate.py --repo . --bench "$B" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; neg_out_has_fixed 'NEUTRAL'; } \
      && ! { neg_out_file "$out"; neg_out_has_fixed 'MET       '; }; then
    echo "ok: panel surrogate positive control (declared surrogate reads NEUTRAL, never MET)"
  else
    echo "NEGATIVE-FAIL: a declared panel surrogate must pass and read NEUTRAL (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register panel_surrogate_must_declare_itself

# --- 3: budget rows come ONLY from the generator ----------------------------
case_panel_budget_value_hand_edit_reddens() {
  local T="$NEG_TMP/t7-budgets"
  rm -rf "$T"; mkdir -p "$T/build/qa/perf" "$T/docs/plans"
  cp build/qa/perf/gen_perf_budgets.py "$T/build/qa/perf/"
  cp build/qa/perf/perf-budgets.json "$T/build/qa/perf/"
  cp docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md "$T/docs/plans/"
  mkdir -p "$T/build/qa"; cp build/qa/_common.py "$T/build/qa/" 2>/dev/null || true
  cp build/_common.py "$T/build/" 2>/dev/null || true
  # the planted hand-edit: someone "fixes" the panel surrogate's ceiling by hand
  "$PY" - "$T/build/qa/perf/perf-budgets.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
doc = json.loads(open(p, encoding="utf-8").read())
for row in doc["rows"]:
    if row["id"] == "panel-open-core-surrogate":
        row["value"] = 7          # not what the plan says
open(p, "w", encoding="utf-8").write(json.dumps(doc, indent=1) + "\n")
PYEOF
  neg_expect_reject "panel budgets: a hand-edited budget value reddens gen_perf_budgets --check" \
    'drifted from the pinned plan' \
    "$PY" "$T/build/qa/perf/gen_perf_budgets.py" --repo "$T" --check
}
neg_register panel_budget_value_hand_edit_reddens

# --- 4: the committed trend input must carry the panel rows ------------------
case_panel_trend_input_must_carry_the_rows() {
  local T="$NEG_TMP/t7-trend"
  rm -rf "$T"; mkdir -p "$T/docs/state" "$T/docs/qa" "$T/tools"
  cp tools/panel_bench.py "$T/tools/"
  "$PY" - "$T/docs/state/bench-trend.json" <<'PYEOF'
import json, sys
doc = json.loads(open("docs/state/bench-trend.json", encoding="utf-8").read())
doc["rows"] = [r for r in doc["rows"] if not r["metric"].startswith("panel_")]
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(doc) + "\n")
PYEOF
  neg_expect_reject "panel bench: a trend input without the panel rows reddens --check" \
    'is missing' \
    "$PY" "$T/tools/panel_bench.py" --repo "$T" --check
}
neg_register panel_trend_input_must_carry_the_rows
