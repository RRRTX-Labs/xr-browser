# tools/negatives/p11_t4.sh — P11-T4 negative cases: the exception surface's
# governance wires each get a canary (harness law: a runner that cannot
# redden is invisible). Covered: the host_protocol.md Methods row ↔ code-
# literal cross-check, the parity-corpus coverage floor for a new method,
# the golden vectors pinning the sweep's INCLUSIVE expiry boundary (a
# mutated fake must drift), and the shield ledger's missing-section law.
# The ledger's grammar/reason/expiry/toggle-shape negatives (19 fixtures)
# live in tools/tests/test_p11_exceptions.py — pytest territory.
#
# Snapshots are WORKING-TREE copies (tar, .git excluded — the p11_t3 cp -r
# pattern): a git clone would snapshot the committed state and miss the
# very changes these canaries govern.

XR_CORE_ABS="$(cd ../xr-core && pwd)"

# snapshot_core <dest-parent>: creates <dest-parent>/xr-core (no .git, no
# prebuilt host — shield_vectors_check rebuilds it via make when needed).
snapshot_core() {
  mkdir -p "$1"
  tar -C "$XR_CORE_ABS/.." \
    --exclude='xr-core/.git' --exclude='xr-core/shield/tests/build' \
    -cf - xr-core | tar -C "$1" -xf -
}

# snapshot_browser <dest>: copies the repo working tree (no .git/pycache).
snapshot_browser() {
  mkdir -p "$1"
  tar -C . --exclude='./.git' --exclude='*__pycache__*' -cf - . \
    | tar -C "$1" -xf -
}

# --- protocol row canary: deleting a Methods row reddens the doc↔code check --
case_protocol_row() {
  local N="$NEG_TMP/t4-norow"
  snapshot_core "$N"
  sed -i '/^| `site-toggle` |/d' "$N/xr-core/shield/host_protocol.md"
  neg_expect_reject "host_protocol_check: an undocumented dispatch literal (site-toggle row deleted) reddens" \
    'FAIL' \
    "$PY" tools/host_protocol_check.py --xr-core "$N/xr-core"
  # positive control: the UNMUTATED snapshot passes
  local C="$NEG_TMP/t4-core-clean"
  snapshot_core "$C"
  if "$PY" tools/host_protocol_check.py --xr-core "$C/xr-core" >/dev/null 2>&1; then
    echo "ok: host_protocol_check positive control (clean snapshot passes)"
  else
    echo "NEGATIVE-FAIL: host_protocol_check must pass on the working tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register protocol_row

# --- corpus coverage canary: dropping a method's cases reddens completeness --
case_corpus_coverage() {
  local B="$NEG_TMP/t4-nocase"
  snapshot_browser "$B"
  "$PY" - "$B" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "tools/parity/corpus-shield.json"
doc = json.loads(p.read_text())
before = len(doc["cases"])
doc["cases"] = [c for c in doc["cases"] if c["method"] != "exception-sweep"]
assert len(doc["cases"]) < before, "no exception-sweep cases to drop"
p.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "parity_completeness: a documented method with zero corpus cases (exception-sweep dropped) reddens" \
    'exception-sweep|FAIL' \
    "$PY" tools/parity_completeness.py --repo "$B" --xr-core "$XR_CORE_ABS"
}
neg_register corpus_coverage

# --- vector boundary canary: flipping the fake's sweep boundary drifts -------
case_vector_boundary() {
  local N="$NEG_TMP/t4-flip"
  snapshot_core "$N"
  # the sweep law: expiry_mono >= 0 && now_mono >= expiry_mono ⇒ swept
  # (INCLUSIVE). Flip >= to > in the fake's method_exception_sweep only —
  # covers() uses now_mono/scope[...] wording, so this sed is unique.
  grep -q 'nm >= s\["expiry_mono"\]' "$N/xr-core/fakes/shield.py" || {
    echo "NEGATIVE-FAIL: sweep boundary text moved — fix the canary's sed"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return; }
  sed -i 's/nm >= s\["expiry_mono"\]/nm > s["expiry_mono"]/' \
    "$N/xr-core/fakes/shield.py"
  neg_expect_reject "shield_vectors_check: a mutated sweep boundary in the fake reddens against the pinned vectors" \
    'FAIL|DRIFT' \
    "$PY" tools/shield_vectors_check.py --repo . --xr-core "$N/xr-core"
}
neg_register vector_boundary

# --- ledger section canary: deleting the shield section reddens the ledger ---
case_ledger_section() {
  local B="$NEG_TMP/t4-nosection"
  snapshot_browser "$B"
  # the shield ledger section is the LAST section of limitations.md
  sed -i '/^## shield exception ledger rows$/,$d' "$B/docs/limitations.md"
  neg_expect_reject "exception_ledger_check: a missing shield ledger section reddens" \
    'shield exception ledger rows' \
    "$PY" tools/exception_ledger_check.py --repo "$B" \
      --matrix-json "$XR_CORE_ABS/test/isolation/isolation-matrix.json"
}
neg_register ledger_section
