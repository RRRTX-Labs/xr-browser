# tools/negatives/p13_c01.sh — P13-C-P0.1 negatives: the §10 unit is a DECLARED
# tab/section, and the forbidden fixes really are forbidden.
#
# What was wrong, measured at e503f9e: `tools/coverage_check.py` treated every
# `ui/panel/<name>.ts` as a surface, so it demanded a command for the focus trap
# and the frame — and it did so in a way that could not be satisfied honestly.
# The repair is a declaration mechanism (xr-core's ui/panel/tabs.json, joined
# to `sources:` membership in docs/contracts/coverage-allowlist.yaml), and these
# cases are the proof that the mechanism bites in both directions:
#
#   1. control  — a fixture with a satisfying inventory + `sources:` is GREEN
#                 (so 2-5 are not "everything reddens");
#   2. a tab that registers itself but has no declared covering surface in the
#      allowlist => RED (the brief's "plant ui/panel/evil-tab.ts that registers
#      a tab");
#   3. a `.ts` that does NOT register a tab but IS claimed under a declared
#      surface => GREEN (the brief's second case: it proves the directory is not
#      blanket-exempted AND that every file is not required to be a tab);
#   4. a `.ts` that nothing claims => RED (the file-as-unit scan is gone, but
#      "I cannot tell which surface this file is for" must still fail);
#   5. the FORBIDDEN fix, asserted to be forbidden: an allowlist that carries
#      `skip: [panel/focus-trap.ts]` instead of a `sources:` claim => still RED
#      (a skip pattern is not a declaration; nothing here reads that key);
#   6. same for widening: an allowlist that drops a tab surface while the
#      inventory still declares the tab => RED (you cannot shrink your way out).
#
# Deterministic and offline (the checker is pure stdlib + the sibling roster at
# the pin; no network). Sourced by tools/run_negatives.sh through NEG_FILES.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13c01_fixture <dir> [--tabs a,b] [--evil] [--orphan] [--claim-metrics]
#                      [--skip-focus]
# Builds a fixture ui-root + allowlist. The generator is inside this case file
# so the fixture's shape is reviewed next to the assertions it feeds.
_p13c01_fixture() {
  "$PY" - "$@" <<'PYEOF'
import json, sys
from pathlib import Path

args = list(sys.argv[1:])
d = Path(args[0])
opts = set(args[1:])
tabs = ["site", "observatory"]
for o in args[1:]:
    if o.startswith("--tabs="):
        tabs = [t for t in o.split("=", 1)[1].split(",") if t]
panel = d / "ui" / "panel"
panel.mkdir(parents=True, exist_ok=True)
for f in ("panel-frame.ts", "focus-trap.ts", "tab-registry.ts"):
    (panel / f).write_text("// fixture source\n", encoding="utf-8")

inventory = [{"id": t, "title_msgid": f"panel.tab.{t}", "order": 10 * (i + 1),
              "requires_identity_scope": True} for i, t in enumerate(tabs)]
if "--evil" in opts:
    (panel / "evil-tab.ts").write_text("// fixture: registers a tab\n", encoding="utf-8")
    inventory.append({"id": "evil", "title_msgid": "panel.tab.evil",
                      "order": 10 * (len(tabs) + 1), "requires_identity_scope": True})
if "--orphan" in opts:
    (panel / "orphan.ts").write_text("// fixture: claimed by nobody\n", encoding="utf-8")
if "--claim-metrics" in opts:
    (panel / "metrics.ts").write_text("// fixture: a non-tab source\n", encoding="utf-8")
(panel / "tabs.json").write_text(json.dumps(
    {"schema": "xr-panel-tabs", "schema_version": 1, "tabs": inventory}, indent=1),
    encoding="utf-8")

frame_sources = ["panel/panel-frame.ts", "panel/tab-registry.ts"]
if "--skip-focus" not in opts:
    frame_sources.insert(1, "panel/focus-trap.ts")
for extra in ("panel/evil-tab.ts", "panel/metrics.ts"):
    if (panel / Path(extra).name).exists():
        frame_sources.append(extra)

lines = ["schema: xr-coverage-allowlist", "schema_version: 2", "surfaces:",
         "  - surface: panel/xr", "    unit: frame", "    command: panel.open",
         "    phase: P13", "    sources: [" + ", ".join(frame_sources) + "]"]
if "--skip-focus" in opts:
    lines += ["    skip: [panel/focus-trap.ts]"]
for t in tabs:
    lines += [f"  - surface: panel/{t}", "    unit: tab", f"    target: {t}",
              "    command: panel.open", "    phase: P13"]
if "--declared-evil" in opts:
    lines += ["  - surface: panel/evil", "    unit: tab", "    target: evil",
              "    command: panel.open", "    phase: P13"]
(d / "allowlist.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
PYEOF
}

# --- 1: control — a satisfying fixture is GREEN ------------------------------
case_c01_control_is_green() {
  local CV="$NEG_TMP/c01-green"
  _p13c01_fixture "$CV"
  local out rc
  out="$("$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "ok: coverage unit control (a satisfying inventory + sources: is green)"
  else
    echo "NEGATIVE-FAIL: the coverage-unit control fixture must pass (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c01_control_is_green

# --- 2: a registered tab with no declared covering surface => RED ------------
case_c01_undeclared_tab_reddens() {
  local CV="$NEG_TMP/c01-evil"
  _p13c01_fixture "$CV" --tabs=site,observatory --evil
  neg_expect_reject "coverage: a tab registered without a declared covering surface reddens (§10)" \
    "registered in the panel's tab inventory with no declared covering surface" \
    "$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml"
}
neg_register c01_undeclared_tab_reddens

# --- 3: a non-tab .ts that IS claimed is GREEN -------------------------------
case_c01_claimed_non_tab_source_is_green() {
  local CV="$NEG_TMP/c01-metrics"
  _p13c01_fixture "$CV" --tabs=site,observatory --claim-metrics
  local out rc
  out="$("$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "ok: coverage unit (panel/metrics.ts registers no tab, is claimed under panel/xr => green)"
  else
    echo "NEGATIVE-FAIL: a claimed non-tab source must be green — the check must not require every .ts to be a tab (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c01_claimed_non_tab_source_is_green

# --- 4: an unclaimed .ts => RED ---------------------------------------------
case_c01_unaccounted_source_reddens() {
  local CV="$NEG_TMP/c01-orphan"
  _p13c01_fixture "$CV" --tabs=site,observatory --orphan
  neg_expect_reject "coverage: a source no surface claims reddens ('a file is not a unit')" \
    'unaccounted source panel/orphan.ts' \
    "$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml"
}
neg_register c01_unaccounted_source_reddens

# --- 5: the forbidden `skip:` fix is not a fix -------------------------------
case_c01_skip_pattern_is_not_a_fix() {
  local CV="$NEG_TMP/c01-skip"
  _p13c01_fixture "$CV" --tabs=site,observatory --skip-focus
  neg_expect_reject "coverage: an allowlist 'skip:' pattern for focus-trap.ts is still RED (nothing reads it)" \
    'unaccounted source panel/focus-trap.ts' \
    "$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml"
}
neg_register c01_skip_pattern_is_not_a_fix

# --- 6: you cannot shrink your way out (allowlist ⊄ inventory) ---------------
case_c01_declaration_outrunning_inventory_reddens() {
  local CV="$NEG_TMP/c01-stale"
  _p13c01_fixture "$CV" --tabs=site --declared-evil
  neg_expect_reject "coverage: an allowlist tab surface with no inventory entry reddens (a declaration that outruns the inventory is untestable)" \
    'has no such tab' \
    "$PY" tools/coverage_check.py --ui-root "$CV/ui" \
      --allowlist "$CV/allowlist.yaml"
}
neg_register c01_declaration_outrunning_inventory_reddens
