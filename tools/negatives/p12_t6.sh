# tools/negatives/p12_t6.sh — P12-T6 negative cases: the xr://shield cosmetic
# rows' governance wires each get a canary (a runner that cannot redden is
# invisible). Covered: the seam-guard union (a view that forgets a guard state
# reddens shield_state_check), the cosmetic rows' presence on the page
# (dropping a COSMETIC string reddens both shield_state_check and
# attention_check), and the attention rule for cosmetic (a planted modal in a
# cosmetic string reddens attention_check).
#
# Snapshots are WORKING-TREE copies; helpers are self-contained (_t6c names).

snapshot_pair_t6c() {
  mkdir -p "$1"
  scratch_tar_xr_core "$1"
  scratch_tar_tree "$1/xr-browser"
}

# --- seam-guard union canary: a view that forgets a guard state reddens ----
case_t6c_guard_gap() {
  local N="$NEG_TMP/t6c-guardgap"
  snapshot_pair_t6c "$N"
  grep -q "'hook-dead'," "$N/xr-core/ui/shield/shield.ts" || {
    echo "NEGATIVE-FAIL: the view's seam-guard union moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i "s/  'hook-dead',//" "$N/xr-core/ui/shield/shield.ts"
  neg_expect_reject "shield_state_check: a seam-guard union missing hook-dead reddens" \
    'seam-guard|FAIL' \
    "$PY" "$N/xr-browser/tools/shield_state_check.py"
}
neg_register t6c_guard_gap

# --- cosmetic absence canary: dropping every cosmetic string reddens -------
case_t6c_cosmetic_dropped() {
  local N="$NEG_TMP/t6c-drop"
  snapshot_pair_t6c "$N"
  grep -q "IDS_XR_SHIELD_COSMETIC_HEADING" "$N/xr-core/l10n/xr_strings.grdp" || {
    echo "NEGATIVE-FAIL: the cosmetic grdp block moved — fix the canary's grep"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  "$PY" - "$N/xr-core/l10n/xr_strings.grdp" <<'PYEOF'
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text()
start = text.index('  <message name="IDS_XR_SHIELD_COSMETIC_HEADING"')
end = text.index('</grit-part>')
p.write_text(text[:start] + text[end:])
PYEOF
  neg_expect_reject "shield_state_check: a page with no cosmetic rows reddens" \
    'IDS_XR_SHIELD_COSMETIC|FAIL' \
    "$PY" "$N/xr-browser/tools/shield_state_check.py"
  neg_expect_reject "attention_check: a grdp with no COSMETIC messages reddens" \
    'COSMETIC|FAIL|no IDS_XR_SHIELD_COSMETIC' \
    "$PY" "$N/xr-browser/tools/attention_check.py"
}
neg_register t6c_cosmetic_dropped

# --- cosmetic attention canary: a planted modal in a cosmetic string -------
case_t6c_cosmetic_modal() {
  local N="$NEG_TMP/t6c-modal"
  snapshot_pair_t6c "$N"
  grep -q "Blob-cache occupancy" "$N/xr-core/l10n/xr_strings.grdp" || {
    echo "NEGATIVE-FAIL: the cosmetic blob row moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i 's/Blob-cache occupancy/Blob-cache occupancy — modal alert now/' \
    "$N/xr-core/l10n/xr_strings.grdp"
  neg_expect_reject "attention_check: a planted modal in a cosmetic string reddens" \
    'cosmetic string|escalation|FAIL' \
    "$PY" "$N/xr-browser/tools/attention_check.py"
}
neg_register t6c_cosmetic_modal
