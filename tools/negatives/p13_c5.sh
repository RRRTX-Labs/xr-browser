# tools/negatives/p13_c5.sh — P13-T6 negatives: the tab registry lane.
#
# The contract is only worth its schema if the LANE that reads it bites. Three
# cases, each one a way somebody could make the panel look finished:
#
#   1. THE BYPASS: a frame that names a tab id as a literal instead of asking
#      the registry. This is the shape the brief calls out — a tab that
#      hardcodes itself into the frame must redden — and it is also how a tab
#      silently stops being rendered when a later tab is added.
#   2. THE PLACEHOLDER: a declared tab whose allowlist entry carries no
#      `sources:` claim. The forbidden fix is spelled out in the fixture: a
#      `skip:` key. A skip is not a claim, and the case asserts the lane says so.
#   3. THE DECORATIVE VECTOR: an accept payload that no longer validates. A
#      vector file that nothing executes is documentation wearing a test's name.
#
# Deterministic and offline: the fixtures are scratch copies of the sibling ui/
# tree and the three repo files the lane reads, never the pinned checkout (a
# negative that dirties the sibling is the P13-C-P0.2c defect).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13c5_fixture <dir> — a scratch repo + scratch core tree with the same shape
# the lane reads: docs/contracts/{schema,vectors,allowlist} and core/{ui,l10n}.
_p13c5_fixture() {
  local D="$1"
  rm -rf "$D"
  mkdir -p "$D/repo/docs/contracts/vectors" "$D/core/l10n"
  cp "$REPO_ROOT/docs/contracts/panel-tab-registration-v1.schema.json" \
     "$D/repo/docs/contracts/panel-tab-registration-v1.schema.json"
  cp "$REPO_ROOT/docs/contracts/vectors/panel-tab-registration-v1.json" \
     "$D/repo/docs/contracts/vectors/panel-tab-registration-v1.json"
  cp "$REPO_ROOT/docs/contracts/coverage-allowlist.yaml" \
     "$D/repo/docs/contracts/coverage-allowlist.yaml"
  cp -r "$REPO_ROOT/../xr-core/ui" "$D/core/ui"
  cp "$REPO_ROOT/../xr-core/l10n/xr_strings.grdp" "$D/core/l10n/xr_strings.grdp"
}

# --- 1: a frame that names a tab id => red, naming file and id --------------
case_c5_bypass_literal_in_frame_reddens() {
  local D="$NEG_TMP/c5-bypass"
  _p13c5_fixture "$D"
  printf 'const OPENER_TAB = %s;\n' "'site'" > "$D/core/ui/panel/panel-frame.ts.tmp"
  cat "$D/core/ui/panel/panel-frame.ts" >> "$D/core/ui/panel/panel-frame.ts.tmp"
  mv "$D/core/ui/panel/panel-frame.ts.tmp" "$D/core/ui/panel/panel-frame.ts"
  neg_expect_reject "a frame naming a tab id (bypass) reddens and names the file" \
    "panel-frame.ts names the tab id" \
    "$PY" "$REPO_ROOT/tools/panel_registry_check.py" \
    --repo "$D/repo" --ui-root "$D/core/ui"
}

neg_register c5_bypass_literal_in_frame_reddens

# --- 2: a declared tab with no sources: claim => red, and skip: is not a fix -
case_c5_placeholder_tab_reddens_and_skip_is_not_a_fix() {
  local D="$NEG_TMP/c5-placeholder"
  _p13c5_fixture "$D"
  python3 - "$D/repo/docs/contracts/coverage-allowlist.yaml" <<'PY'
import re, sys
p = sys.argv[1]
src = open(p, encoding="utf-8").read()
# the forbidden fix, verbatim: no sources, a skip key instead
src = src.replace("    sources:\n      - panel/site-tab.ts\n",
                  "    skip: [panel/site-tab.ts]\n", 1)
open(p, "w", encoding="utf-8").write(src)
PY
  neg_expect_reject "a declared tab with no sources claim reddens (a skip: is not a claim)" \
    "claims no \`sources:\` file" \
    "$PY" "$REPO_ROOT/tools/panel_registry_check.py" \
    --repo "$D/repo" --ui-root "$D/core/ui"
}

neg_register c5_placeholder_tab_reddens_and_skip_is_not_a_fix

# --- 3: an accept vector that no longer validates => red --------------------
case_c5_decorative_vector_reddens() {
  local D="$NEG_TMP/c5-vector"
  _p13c5_fixture "$D"
  python3 - "$D/repo/docs/contracts/vectors/panel-tab-registration-v1.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["accept"][0]["payload"]["page_html"] = "<div>content</div>"
json.dump(d, open(p, "w", encoding="utf-8"))
PY
  neg_expect_reject "an accept vector the schema refuses reddens (the file is executed)" \
    "vector accept/" \
    "$PY" "$REPO_ROOT/tools/panel_registry_check.py" \
    --repo "$D/repo" --ui-root "$D/core/ui"
}

neg_register c5_decorative_vector_reddens
