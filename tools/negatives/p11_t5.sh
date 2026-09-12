# tools/negatives/p11_t5.sh — P11-T5 negative cases: the activity-ledger
# emitter's governance wires each get a canary (harness law: a runner that
# cannot redden is invisible). Covered: the block-event golden's schema
# strictness, the reason-code table's five-way sync law (a dropped code
# reddens pytest), the vectors' byte-identical-regen law (a fake emitter
# that stops redacting must DRIFT), the parity-corpus coverage floor for
# event-emit, and the host_protocol.md row <-> code-literal cross-check
# for the new method.
#
# Snapshots are WORKING-TREE copies (tar, .git excluded — the p11_t4
# pattern). Helpers are self-contained (_t5 names): no source-order
# dependency on the other case files.

XR_CORE_ABS_T5="$(cd ../xr-core && pwd)"

snapshot_core_t5() {
  mkdir -p "$1"
  tar -C "$XR_CORE_ABS_T5/.." \
    --exclude='xr-core/.git' --exclude='xr-core/shield/tests/build' \
    -cf - xr-core | tar -C "$1" -xf -
}

snapshot_browser_t5() {
  mkdir -p "$1"
  tar -C . --exclude='./.git' --exclude='*__pycache__*' -cf - . \
    | tar -C "$1" -xf -
}

# sibling layout ($1/xr-browser + $1/xr-core) for tests that resolve
# CORE = REPO.parent / "xr-core" (the conftest/pytest idiom).
snapshot_pair_t5() {
  snapshot_core_t5 "$1"
  snapshot_browser_t5 "$1/xr-browser"
}

# --- golden schema canary: a mutated golden row reddens xr_schema ----------
case_t5_golden_schema() {
  local B="$NEG_TMP/t5-badgolden"
  snapshot_browser_t5 "$B"
  "$PY" - "$B" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "docs/contracts/tests/golden-block-event.json"
doc = json.loads(p.read_text())
doc["action"] = "blocked"  # non-frozen spelling: the enum must refuse it
p.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")
PYEOF
  neg_expect_reject "xr_schema: a mutated golden action (non-frozen spelling) reddens block-event validation" \
    'FAIL' \
    "$PY" tools/xr_schema.py --repo "$B" validate block-event \
      "$B/docs/contracts/tests/golden-block-event.json"
  local C="$NEG_TMP/t5-golden-clean"
  snapshot_browser_t5 "$C"
  if "$PY" tools/xr_schema.py --repo "$C" validate block-event \
      "$C/docs/contracts/tests/golden-block-event.json" \
      >/dev/null 2>&1; then
    echo "ok: xr_schema block-event positive control (clean golden validates)"
  else
    echo "NEGATIVE-FAIL: the clean golden must validate"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t5_golden_schema

# --- reason-code drift canary: dropping a code reddens the sync test -------
case_t5_reason_drift() {
  local N="$NEG_TMP/t5-reasondrift"
  snapshot_pair_t5 "$N"
  "$PY" - "$N" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "xr-browser/docs/shield/reason-codes.json"
doc = json.loads(p.read_text())
before = len(doc["codes"])
doc["codes"] = [c for c in doc["codes"] if c["why_code"] != "kill-switch"]
assert len(doc["codes"]) < before, "no kill-switch code to drop"
p.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "pytest five-way sync: a dropped reason code (kill-switch) reddens test_block_event" \
    'failed|FAILED|AssertionError' \
    "$PY" -m pytest -q -p no:cacheprovider \
      "$N/xr-browser/docs/contracts/tests/test_block_event.py" \
      -k five_way
  local C="$NEG_TMP/t5-reason-clean"
  snapshot_pair_t5 "$C"
  if "$PY" -m pytest -q -p no:cacheprovider \
      "$C/xr-browser/docs/contracts/tests/test_block_event.py" \
      -k five_way >/dev/null 2>&1; then
    echo "ok: five-way sync positive control (clean table passes)"
  else
    echo "NEGATIVE-FAIL: the clean reason-code table must pass the sync test"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t5_reason_drift

# --- emitter redaction canary: a fake that stops redacting drifts ----------
case_t5_vectors_drift() {
  local N="$NEG_TMP/t5-fakedrift"
  snapshot_pair_t5 "$N"
  grep -q 'redact_target(ctx\["parts"\])' "$N/xr-core/fakes/shield.py" || {
    echo "NEGATIVE-FAIL: ledger_row redaction text moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i 's/redact_target(ctx\["parts"\])/ctx["url"]/' \
    "$N/xr-core/fakes/shield.py"
  neg_expect_reject "gen_shield_vectors --check: a fake emitter that leaks raw urls into target reddens the byte-identical-regen law" \
    'DRIFT|FAIL' \
    "$PY" "$N/xr-browser/tools/gen_shield_vectors.py" \
      --repo "$N/xr-browser" --xr-core "$N/xr-core" --check
  if "$PY" tools/gen_shield_vectors.py --check >/dev/null 2>&1; then
    echo "ok: vectors regen positive control (working tree regenerates byte-identical)"
  else
    echo "NEGATIVE-FAIL: the working tree must regenerate the vectors"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t5_vectors_drift

# --- corpus coverage canary: dropping event-emit's cases reddens -----------
case_t5_corpus_gap() {
  local B="$NEG_TMP/t5-nocorpus"
  snapshot_browser_t5 "$B"
  "$PY" - "$B" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "tools/parity/corpus-shield.json"
doc = json.loads(p.read_text())
before = len(doc["cases"])
doc["cases"] = [c for c in doc["cases"] if c["method"] != "event-emit"]
assert len(doc["cases"]) < before, "no event-emit cases to drop"
p.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "parity_completeness: a documented method with zero corpus cases (event-emit dropped) reddens" \
    'event-emit|FAIL' \
    "$PY" tools/parity_completeness.py --repo "$B" --xr-core "$XR_CORE_ABS_T5"
}
neg_register t5_corpus_gap

# --- protocol row canary: deleting the Methods row reddens the doc check ---
case_t5_protocol_row() {
  local N="$NEG_TMP/t5-norow"
  snapshot_core_t5 "$N"
  sed -i '/^| `event-emit` |/d' "$N/xr-core/shield/host_protocol.md"
  neg_expect_reject "host_protocol_check: an undocumented dispatch literal (event-emit row deleted) reddens" \
    'FAIL' \
    "$PY" tools/host_protocol_check.py --xr-core "$N/xr-core"
  local C="$NEG_TMP/t5-row-clean"
  snapshot_core_t5 "$C"
  if "$PY" tools/host_protocol_check.py --xr-core "$C/xr-core" >/dev/null 2>&1; then
    echo "ok: host_protocol_check positive control (clean snapshot passes)"
  else
    echo "NEGATIVE-FAIL: host_protocol_check must pass on the working tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register t5_protocol_row
