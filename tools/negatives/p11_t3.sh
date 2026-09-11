# tools/negatives/p11_t3.sh — P11-T3 negative cases: every new xr-lists
# runner gets a canary (harness law: a runner that cannot redden is
# invisible). Covered: the compile-vector byte law, the FROZEN schema pin
# (the STOP-condition tripwire), the refusal-coverage floor, the whole-
# package regeneration drift, and the round-trip matrix itself.

# --- compile-vector drift: --check reddens on a hand-edited expectation ----
case_lists_vector_drift() {
  local R="$NEG_TMP/t3-drift-repo"
  mkdir -p "$R/docs/contracts/vectors"
  cp -r xr-lists "$R/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$R/docs/contracts/vectors/"
  "$PY" - "$R" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "docs/contracts/vectors/xr-lists-compile-v1.json"
doc = json.loads(p.read_text())
for c in doc["cases"]:
    if "rule" in c["expect"]:  # the first rule case — flip its action
        c["expect"]["rule"]["action"] = \
            "allow" if c["expect"]["rule"]["action"] == "block" else "block"
        break
p.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "gen_lists_compile_vectors --check: hand-edited expectation reddens" \
    'DRIFT' \
    "$PY" tools/gen_lists_compile_vectors.py --repo "$R" --check
  # positive control: the UNMUTATED copy regenerates byte-identical
  local C="$NEG_TMP/t3-drift-clean"
  mkdir -p "$C/docs/contracts/vectors"
  cp -r xr-lists "$C/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$C/docs/contracts/vectors/"
  if "$PY" tools/gen_lists_compile_vectors.py --repo "$C" --check >/dev/null 2>&1; then
    echo "ok: gen_lists_compile_vectors --check positive control (clean copy passes)"
  else
    echo "NEGATIVE-FAIL: gen_lists_compile_vectors --check must pass on the committed vectors"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register lists_vector_drift

# --- FROZEN schema pin: editing list-bundle-manifest-v1 reddens the check --
case_lists_frozen_schema_edit() {
  local R="$NEG_TMP/t3-schema-repo"
  mkdir -p "$R/docs/contracts/vectors"
  cp -r xr-lists "$R/"
  cp docs/contracts/list-bundle-manifest-v1.schema.json \
     docs/contracts/list-bundle-manifest-v1.md "$R/docs/contracts/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$R/docs/contracts/vectors/"
  printf '\n' >> "$R/docs/contracts/list-bundle-manifest-v1.schema.json"
  neg_expect_reject "list_bundle_check: an EDITED frozen schema reddens the sha256 pin (STOP-and-report tripwire)" \
    'FROZEN contract file CHANGED' \
    "$PY" tools/list_bundle_check.py --repo "$R"
  # positive control: the untouched copy passes the pin
  local C="$NEG_TMP/t3-schema-clean"
  mkdir -p "$C/docs/contracts/vectors"
  cp -r xr-lists "$C/"
  cp docs/contracts/list-bundle-manifest-v1.schema.json \
     docs/contracts/list-bundle-manifest-v1.md "$C/docs/contracts/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$C/docs/contracts/vectors/"
  if "$PY" tools/list_bundle_check.py --repo "$C" >/dev/null 2>&1; then
    echo "ok: list_bundle_check positive control (untouched schema passes)"
  else
    echo "NEGATIVE-FAIL: list_bundle_check must pass on the committed tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register lists_frozen_schema_edit

# --- refusal-coverage floor: pruning refusal cases below 30 reddens --------
case_lists_refusal_gap() {
  local R="$NEG_TMP/t3-gap-repo"
  mkdir -p "$R/docs/contracts/vectors"
  cp -r xr-lists "$R/"
  cp docs/contracts/list-bundle-manifest-v1.schema.json \
     docs/contracts/list-bundle-manifest-v1.md "$R/docs/contracts/"
  "$PY" - "$R" <<'PYEOF'
import json, sys
from pathlib import Path
src = Path("docs/contracts/vectors/xr-lists-compile-v1.json")
doc = json.loads(src.read_text())
kept, refs = [], 0
for c in doc["cases"]:
    if "refusals" in c["expect"]:
        refs += 1
        if refs <= 15:  # prune the refusal table below the 30-case floor
            kept.append(c)
    else:
        kept.append(c)
doc["cases"] = kept
out = Path(sys.argv[1]) / "docs/contracts/vectors/xr-lists-compile-v1.json"
out.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "list_bundle_check: a pruned refusal table (<30 cases) reddens" \
    'refusal' \
    "$PY" tools/list_bundle_check.py --repo "$R"
}
neg_register lists_refusal_gap

# --- package drift: mutating a SOURCE list reddens the regeneration --------
case_lists_package_drift() {
  local R="$NEG_TMP/t3-pkg-repo"
  mkdir -p "$R/docs/contracts/vectors"
  cp -r xr-lists "$R/"
  cp docs/contracts/list-bundle-manifest-v1.schema.json \
     docs/contracts/list-bundle-manifest-v1.md "$R/docs/contracts/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$R/docs/contracts/vectors/"
  printf '||sneaky-extra.example^\n' >> "$R/xr-lists/sources/xr-synthetic-default.txt"
  neg_expect_reject "list_bundle_check --check: a mutated source list reddens the golden package" \
    'DRIFT: testdata' \
    "$PY" tools/list_bundle_check.py --repo "$R" --check
  # positive control: the clean copy regenerates byte-identical
  local C="$NEG_TMP/t3-pkg-clean"
  mkdir -p "$C/docs/contracts/vectors"
  cp -r xr-lists "$C/"
  cp docs/contracts/list-bundle-manifest-v1.schema.json \
     docs/contracts/list-bundle-manifest-v1.md "$C/docs/contracts/"
  cp docs/contracts/vectors/xr-lists-compile-v1.json "$C/docs/contracts/vectors/"
  if "$PY" tools/list_bundle_check.py --repo "$C" --check >/dev/null 2>&1; then
    echo "ok: list_bundle_check --check positive control (clean tree regenerates)"
  else
    echo "NEGATIVE-FAIL: list_bundle_check --check must pass on the committed tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register lists_package_drift

# --- the round-trip matrix itself must be able to redden -------------------
case_lists_roundtrip_red() {
  local R="$NEG_TMP/t3-rt-repo"
  mkdir -p "$R/build"
  cp -r xr-lists "$R/"
  cp -r build/signing "$R/build/"
  "$PY" - "$R" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "xr-lists/sources/config-hotpin-v1.json"
cfg = json.loads(p.read_text())
cfg["lists"][1]["attribution"] = "broken"  # one segment: shape law must redden
p.write_text(json.dumps(cfg, indent=2) + "\n")
PYEOF
  neg_expect_reject "roundtrip.sh: a malformed attribution reddens the matrix" \
    'FAIL' \
    bash "$R/xr-lists/tests/roundtrip.sh"
  # positive control: the clean copy runs the full matrix green (host cells
  # included — XR_CORE points at the real sibling checkout)
  local C="$NEG_TMP/t3-rt-clean"
  mkdir -p "$C/build"
  cp -r xr-lists "$C/"
  cp -r build/signing "$C/build/"
  if XR_CORE="$PWD/../xr-core" bash "$C/xr-lists/tests/roundtrip.sh" >/dev/null 2>&1; then
    echo "ok: roundtrip.sh positive control (clean tree passes the matrix)"
  else
    echo "NEGATIVE-FAIL: roundtrip.sh must pass on the committed tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register lists_roundtrip_red
