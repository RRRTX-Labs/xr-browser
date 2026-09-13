# tools/negatives/p11_t6.sh — P11-T6 negative cases: the dev-only debug
# page's governance wires each get a canary (harness law: a runner that
# cannot redden is invisible). Covered: the channel gate's fail-closed
# default in the reference fake (a flipped default must DRIFT the golden
# vectors), the state-coverage gate (a view that forgets a host state must
# redden shield_state_check; a tier escalation of shield.page must
# redden it too), the Attention-Budget shield rule (attention-escalation
# vocabulary injected into a shield surface must redden attention_check),
# and the host_protocol.md row <-> dispatch-literal cross-check for the
# two new methods.
#
# Snapshots are WORKING-TREE copies (tar, .git excluded — the p11_t4/t5
# pattern). Helpers are self-contained (_t6 names): no source-order
# dependency on the other case files.

XR_CORE_ABS_T6="$(cd ../xr-core && pwd)"

snapshot_core_t6() {
  mkdir -p "$1"
  tar -C "$XR_CORE_ABS_T6/.." \
    --exclude='xr-core/.git' --exclude='xr-core/shield/tests/build' \
    --exclude='xr-core/commands/tests/build' \
    -cf - xr-core | tar -C "$1" -xf -
}

snapshot_browser_t6() {
  mkdir -p "$1"
  tar -C . --exclude='./.git' --exclude='*__pycache__*' -cf - . \
    | tar -C "$1" -xf -
}

# sibling layout ($1/xr-browser + $1/xr-core) for tests that resolve
# CORE = REPO.parent / "xr-core" (the conftest/pytest idiom).
snapshot_pair_t6() {
  snapshot_core_t6 "$1"
  snapshot_browser_t6 "$1/xr-browser"
}

# --- channel-gate canary: a fake that serves the page on release DRIFTS ---
case_t6_gate_drift() {
  local N="$NEG_TMP/t6-gatedrift"
  snapshot_pair_t6 "$N"
  grep -q 'channel = "release"  # P11-T6' "$N/xr-core/fakes/shield.py" || {
    echo "NEGATIVE-FAIL: the fake's fail-closed channel default moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i 's/channel = "release"  # P11-T6/channel = "dev"  # P11-T6/' \
    "$N/xr-core/fakes/shield.py"
  neg_expect_reject "gen_shield_vectors --check: a fake that serves debug-page on the default channel reddens the byte-identical-regen law" \
    'DRIFT|FAIL' \
    "$PY" "$N/xr-browser/tools/gen_shield_vectors.py" \
      --repo "$N/xr-browser" --xr-core "$N/xr-core" --check
  # positive control: the REAL fake refuses typed on the default channel
  local out
  out="$(printf '{"args":{},"method":"debug-page"}' \
    | "$PY" "$XR_CORE_ABS_T6/fakes/shield.py" 2>/dev/null)" || true
  if printf '%s' "$out" | grep -q 'build-channel-not-dev:release'; then
    echo "ok: fake debug-page positive control (default channel refuses typed)"
  else
    echo "NEGATIVE-FAIL: the fake must refuse debug-page on the default channel"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t6_gate_drift

# --- state-coverage canary: a view that forgets a state reddens -----------
case_t6_state_gap() {
  local N="$NEG_TMP/t6-stategap"
  snapshot_pair_t6 "$N"
  grep -q "'route-loss'," "$N/xr-core/ui/shield/shield.ts" || {
    echo "NEGATIVE-FAIL: the view's state union moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i "s/'route-loss',//" "$N/xr-core/ui/shield/shield.ts"
  neg_expect_reject "shield_state_check: a debug-page view missing a host state (route-loss dropped) reddens" \
    'route-loss|FAIL' \
    "$PY" "$N/xr-browser/tools/shield_state_check.py"
  local C="$NEG_TMP/t6-state-clean"
  snapshot_pair_t6 "$C"
  if "$PY" "$C/xr-browser/tools/shield_state_check.py" >/dev/null 2>&1; then
    echo "ok: shield_state_check positive control (clean snapshot passes)"
  else
    echo "NEGATIVE-FAIL: shield_state_check must pass on the working tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t6_state_gap

# --- tier-escalation canary: shield.page as tier1 reddens ------------------
case_t6_tier_law() {
  local N="$NEG_TMP/t6-tierlaw"
  snapshot_pair_t6 "$N"
  "$PY" - "$N" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "xr-core/commands/core/roster_v1.json"
doc = json.loads(p.read_text())
hit = 0
for c in doc["commands"]:
    if c["descriptor"]["id"] == "shield.page":
        c["descriptor"]["attention_tier"] = "tier1"  # chip-count law broken
        hit += 1
assert hit == 1, "shield.page not in the roster"
p.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "shield_state_check: a tier1 escalation of shield.page (attention-budget law) reddens" \
    'tier2|FAIL' \
    "$PY" "$N/xr-browser/tools/shield_state_check.py"
}
neg_register t6_tier_law

# --- attention-vocabulary canary: an escalating shield view reddens --------
case_t6_attention_vocab() {
  local N="$NEG_TMP/t6-attnvocab"
  snapshot_pair_t6 "$N"
  printf '\n// show a toast when the count changes\nexport function ping() { return "toast"; }\n' \
    >> "$N/xr-core/ui/shield/shield.ts"
  neg_expect_reject "attention_check: a shield surface carrying attention-escalation vocabulary (toast) reddens" \
    'toast|FAIL' \
    "$PY" "$N/xr-browser/tools/attention_check.py"
  local C="$NEG_TMP/t6-attn-clean"
  snapshot_pair_t6 "$C"
  if "$PY" "$C/xr-browser/tools/attention_check.py" >/dev/null 2>&1; then
    echo "ok: attention_check positive control (clean snapshot passes)"
  else
    echo "NEGATIVE-FAIL: attention_check must pass on the working tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t6_attention_vocab

# --- protocol row canary: deleting a T6 Methods row reddens the doc check --
case_t6_protocol_row() {
  local N="$NEG_TMP/t6-norow"
  snapshot_core_t6 "$N"
  sed -i '/^| `debug-page` |/d' "$N/xr-core/shield/host_protocol.md"
  neg_expect_reject "host_protocol_check: an undocumented dispatch literal (debug-page row deleted) reddens" \
    'FAIL' \
    "$PY" tools/host_protocol_check.py --xr-core "$N/xr-core"
}
neg_register t6_protocol_row
