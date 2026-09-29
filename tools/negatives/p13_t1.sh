# tools/negatives/p13_t1.sh — P13-T1 negatives: the panel's focus containment.
#
# T1's acceptance criterion is deliberately adversarial: the focus trap needs a
# REAL test — "a planted leak ⇒ red", not a docstring. A trap is the classic
# piece of UI whose test passes while containing nothing, so the battery proves
# the lane can fail, in three layers:
#
#   1. positive control — the clean panel sources pass the lane;
#   2. the leaked tree — containment deleted in a scratch copy of xr-core
#      (`containedTarget` -> null) — must REDDEN the lane, with the failure
#      naming the containment assertion (the planted leak, exactly as the brief
#      writes it);
#   3. the lane's own detector — `--plant-leak` must report that its planted
#      leak was caught, so "the lane has a detector" is itself asserted rather
#      than assumed.
#
# Deterministic and offline: the lane bundles with the already-installed pinned
# toolchain and runs node:test; no network, no browser. SKIPs visibly (77) when
# node or the toolchain is unavailable — never a silent pass.
#
# Sourced by tools/run_negatives.sh through NEG_FILES (lib.sh, $PY, $NEG_TMP).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13t1_scratch_core <dir> [leak] — a scratch xr-core with ui/panel (optionally
# leaked) and a toolchain whose node_modules is symlinked from the real one, so
# no install and no network is needed for the fixture.
_p13t1_scratch_core() {
  local D="$1" leak="${2:-}"
  rm -rf "$D"
  mkdir -p "$D/ui/panel/tests" "$D/ui/toolchain"
  cp "$REPO_ROOT/../xr-core/ui/panel/focus-trap.ts" "$D/ui/panel/"
  cp "$REPO_ROOT/../xr-core/ui/panel/panel-frame.ts" "$D/ui/panel/"
  cp "$REPO_ROOT/../xr-core/ui/panel/tests/focus-trap.test.mjs" \
     "$D/ui/panel/tests/"
  ln -s "$REPO_ROOT/../xr-core/ui/toolchain/node_modules" \
     "$D/ui/toolchain/node_modules"
  cp "$REPO_ROOT/../xr-core/ui/toolchain/package.json" "$D/ui/toolchain/" 2>/dev/null || true
  if [ "$leak" = "leak" ]; then
    "$PY" - "$D/ui/panel/focus-trap.ts" <<'PYEOF'
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
anchor = "  const inside = focusables(world, root);\n"
assert anchor in t, "leak anchor missing"
p.write_text(t.replace(anchor, "  if (true) return null;  // PLANTED LEAK\n" + anchor, 1),
             encoding="utf-8")
PYEOF
  fi
}

# --- 1: planted leak (containment deleted) => the lane reddens --------------
case_panel_leaky_trap_reddens() {
  local D="$NEG_TMP/t1-leak"
  _p13t1_scratch_core "$D" leak
  neg_expect_reject "panel focus trap: containment deleted in a scratch core reddens the lane" \
    'focus-containment suite failed' \
    env XR_CORE="$D" bash build/webui/panel-tests.sh
  rm -rf "$D"
}
neg_register panel_leaky_trap_reddens

# --- 2: positive control — the clean sources pass ---------------------------
case_panel_clean_sources_pass() {
  local D="$NEG_TMP/t1-clean" out rc
  _p13t1_scratch_core "$D"
  out="$(env XR_CORE="$D" bash build/webui/panel-tests.sh 2>&1)" && rc=0 || rc=$?
  rm -rf "$D"
  if [ "$rc" -eq 77 ]; then
    neg_skip "panel-tests lane SKIPped (node/toolchain absent): clean-source control not exercised"
    return 0
  fi
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; neg_out_has_fixed 'focus containment'; }; then
    echo "ok: panel focus trap positive control (clean sources pass the lane)"
  else
    echo "NEGATIVE-FAIL: the clean panel sources must pass the lane (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register panel_clean_sources_pass

# --- 3: the lane's own detector can fire ------------------------------------
case_panel_plant_leak_detector() {
  neg_expect_inband "panel-tests --plant-leak: the lane reports that its planted leak was caught" \
    'planted leak reddens the suite' \
    bash build/webui/panel-tests.sh --plant-leak
}
neg_register panel_plant_leak_detector
