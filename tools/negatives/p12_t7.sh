# tools/negatives/p12_t7.sh — P12-T7 negatives (perf budgets + bench).
#
# Two defects the phase exists to make impossible:
#   * a cosmetic surrogate row WITHOUT `surrogate:true` must be refused by
#     perf_gate — otherwise a synthetic cosmetic_host number would read as a
#     Blink measurement it is not (the phase's disqualifier, made law);
#   * a cosmetic surrogate row must NEVER emit MET — the committed trend
#     input is surrogate/model-labelled and NEUTRAL, so a hand-raised
#     sv that would let perf_gate rule MET (value below budget) is still
#     refused/NEUTRAL, never a green claim.
#
# Sourced by tools/run_negatives.sh through NEG_FILES (provides lib.sh + PY).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- an unlabelled cosmetic surrogate must be refused ----------------------
case_perf_gate_unlabelled_surrogate() {
  local B="$NEG_TMP/bench-cosmetic-unlabelled.json"
  printf '{"name":"canary","rig_class":"trend","unit":"us","rows":[{"metric":"cosmetic_keyset_build_ms","value_us":2.0,"unit":"ms"}]}' > "$B"
  neg_expect_reject "perf_gate: a cosmetic surrogate row without surrogate:true is refused (a synthetic number reading as a Blink measurement)" \
    'surrogate' \
    "$PY" tools/perf_gate.py --repo . --bench "$B"
}
neg_register perf_gate_unlabelled_surrogate

# --- a cosmetic surrogate never emits MET --------------------------------
case_perf_gate_surrogate_never_met() {
  local B="$NEG_TMP/bench-cosmetic-met.json"
  # value far below budget: any non-surrogate row would rule MET. The
  # surrogate law must still pin it NEUTRAL, and the gate output (not a FAIL)
  # must show NEUTRAL — assert via the report line.
  printf '{"name":"canary","rig_class":"trend","unit":"us","rows":[{"metric":"cosmetic_keyset_build_ms","value_us":0.5,"unit":"ms","surrogate":true}]}' > "$B"
  local out rc
  out="$("$PY" tools/perf_gate.py --repo . --bench "$B" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: perf_gate must PASS (no MISSED) on a surrogate below budget — it rules NEUTRAL, not an error"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q "NEUTRAL"; then
    echo "NEGATIVE-FAIL: surrogate below budget must read NEUTRAL, never MET"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: perf_gate surrogate law (a below-budget surrogate reads NEUTRAL, never MET)"
  fi
}
neg_register perf_gate_surrogate_never_met
