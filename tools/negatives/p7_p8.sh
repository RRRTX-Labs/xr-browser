# tools/negatives/p7_p8.sh — P7/P8 gate negatives (csp/a11y/rtl/menu/
# coverage lints + commands_host in-band page-reject). P9-T0-d split.

# --- 26. csp_lint: a WebUI view that reaches the network at runtime --------
case_csp_runtime_fetch() {
  local CU="$NEG_TMP/cspui"; mkdir -p "$CU"
  printf '// Copyright 2026 RRRTX Labs\nexport async function load() {\n  return await fetch("https://example.com");\n}\n' > "$CU/rogue.ts"
  neg_expect_reject "csp_lint: runtime fetch( in ui/** (no runtime egress)" \
    'fetch\(' \
    "$PY" tools/csp_lint.py --ui-root "$CU" --commands-root "$NEG_TMP/does-not-exist"
}
neg_register csp_runtime_fetch

# --- 27. a11y_lint: palette missing SR-critical aria-activedescendant ------
case_a11y_combobox() {
  local AP="$NEG_TMP/a11y"; mkdir -p "$AP/palette" "$AP/help-index"
  printf 'export class X { render() { return `<div role="combobox"></div>`; } }\n' > "$AP/palette/palette.ts"
  printf 'export class Y { render() { return `<div aria-live="polite"></div>`; } }\n' > "$AP/help-index/help-index.ts"
  printf ':focus-visible { outline: 1px solid red; }\n' > "$AP/tokens.css"
  neg_expect_reject "a11y_lint: palette missing ARIA APG combobox token" \
    'aria-activedescendant' \
    "$PY" tools/a11y_lint.py --palette-dir "$AP/palette" --ui-dir "$AP"
}
neg_register a11y_combobox

# --- 28. rtl_lint: physical margin-left / text-align:left ------------------
case_rtl_physical() {
  local RT="$NEG_TMP/rtl"; mkdir -p "$RT"
  printf '.x { margin-left: 8px; text-align: left; }\n' > "$RT/bad.css"
  neg_expect_reject "rtl_lint: physical left/right CSS (logical-only law)" \
    'margin-left/right' \
    "$PY" tools/rtl_lint.py --ui-dir "$RT"
}
neg_register rtl_physical

# --- 29. menu_model_check: a 10-tier-1 roster => rejected ------------------
case_menu_tier1_budget() {
  local MM="$NEG_TMP/tier1"; mkdir -p "$MM"
  "$PY" - "$MM" <<'NEG'
import json, sys, pathlib
src = pathlib.Path("../xr-core/commands/core/roster_v1.json")
reg = json.loads(src.read_text())
n = 0
for c in reg["commands"]:
    c["descriptor"]["attention_tier"] = "tier1"
    n += 1
    if n >= 10:
        break
(pathlib.Path(sys.argv[1]) / "roster10.json").write_text(json.dumps(reg))
NEG
  neg_expect_reject "menu_model_check: 10-tier-1 roster breaches the Attention Budget" \
    'tier1|Tier-1' \
    "$PY" tools/menu_model_check.py --roster "$MM/roster10.json" --out "$MM/x.json"
}
neg_register menu_tier1_budget

# --- 30. coverage_check: a LANDED surface with no registered command -------
case_coverage_undeclared() {
  local CV="$NEG_TMP/cov"; mkdir -p "$CV/ui/settings"
  printf 'export class Rogue {}\n' > "$CV/ui/settings/rogue-section.ts"
  neg_expect_reject "coverage_check: landed settings surface maps to no command (§10)" \
    'has no command registered' \
    "$PY" tools/coverage_check.py --ui-root "$CV/ui"
}
neg_register coverage_undeclared

# --- 31. commands_host: a PAGE-originated invoke => rejected in-band -------
case_commands_host_page_reject() {
  local CH=../xr-core/commands/tests/build/commands_host
  if [ ! -x "$CH" ]; then
    neg_skip "commands_host page-reject negative (host not built; CI has g++)"
    return 0
  fi
  local CHT="$NEG_TMP/ch"; mkdir -p "$CHT"
  neg_expect_inband "commands_host: page-originated invoke rejected in-band" \
    '"status":"rejected"' \
    "$CH" --store-dir "$CHT" --roster ../xr-core/commands/core/roster_v1.json \
      --flag xr_command_registry_v1=on \
      '{"method":"invoke","args":{"id":"tab.new","source":"page"}}'
}
neg_register commands_host_page_reject
