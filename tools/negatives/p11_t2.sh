# tools/negatives/p11_t2.sh — P11-T2 negative cases: the shield vector
# machinery must redden on committed-vector drift, on a mutated Python
# reference fake (the byte-parity canary), on an undocumented shield host,
# on a phantom method-table entry, and on a parity corpus with a method gap.

# --- vector-file drift: --check must redden when the committed vectors are
# --- not EXACTLY the generator's deterministic output --------------------
case_shield_vector_drift() {
  local R="$NEG_TMP/t2-drift-repo"
  mkdir -p "$R/docs/contracts/vectors"
  "$PY" - "$R" <<'PYEOF'
import json, sys
from pathlib import Path
src = Path("docs/contracts/vectors/shield-v1.json")
doc = json.loads(src.read_text())
# a semantic mutation: flip one expected why_code (the kind of "small fix"
# a hand-edit would try)
for c in doc["cases"]:
    if c["id"] == "m-block-basic":
        c["expect"]["verdict"]["why_code"] = "no-match"
        break
out = Path(sys.argv[1]) / "docs/contracts/vectors/shield-v1.json"
out.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
PYEOF
  neg_expect_reject "gen_shield_vectors --check: hand-edited vectors redden" \
    'DRIFT' \
    "$PY" tools/gen_shield_vectors.py --repo "$R" --xr-core ../xr-core --check
  # positive control: the UNMUTATED copy regenerates byte-identical
  local C="$NEG_TMP/t2-clean-repo"
  mkdir -p "$C/docs/contracts/vectors"
  cp docs/contracts/vectors/shield-v1.json "$C/docs/contracts/vectors/"
  if "$PY" tools/gen_shield_vectors.py --repo "$C" --xr-core ../xr-core \
      --check >/dev/null 2>&1; then
    echo "ok: gen_shield_vectors --check positive control (clean copy passes)"
  else
    echo "NEGATIVE-FAIL: gen_shield_vectors --check must pass on the committed vectors"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register shield_vector_drift

# --- byte-parity canary: a mutated Python reference reddens the checker ---
case_shield_fake_mutation() {
  if ! command -v g++ >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    echo "SKIP: SKIP (tool absent: g++/make) — needed for: the shield fake-mutation canary (compiled host side); local hint: apt-get install g++ make (build-essential)"
    return 0
  fi
  local T="$NEG_TMP/t2-core"
  mkdir -p "$T"
  cp -r ../xr-core/shield ../xr-core/common ../xr-core/fakes "$T/"
  # the checker builds the host inside the copied tree on demand
  if ! "$PY" tools/shield_vectors_check.py --repo . --xr-core "$T" \
      >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: shield_vectors_check positive control must pass on the unmutated copy"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  echo "ok: shield_vectors_check positive control (unmutated copy passes)"
  # mutate the reference fake's why_code vocabulary — one word, one drift
  sed -i 's/"block": "rule-blocked"/"block": "blocked-by-rule"/' \
    "$T/fakes/shield.py"
  neg_expect_reject "shield_vectors_check: a mutated reference fake reddens" \
    'DRIFT' \
    "$PY" tools/shield_vectors_check.py --repo . --xr-core "$T"
}
neg_register shield_fake_mutation

# --- host doc law: the shield host without its protocol doc reddens -------
case_shield_hostdoc_missing() {
  local T="$NEG_TMP/t2-hostdoc"
  mkdir -p "$T"
  cp -r ../xr-core/shield "$T/shield"
  rm "$T/shield/host_protocol.md"
  # a documented host so the discovery is non-empty on its own merits
  cp -r ../xr-core/update "$T/update"
  rm -rf "$T/update/tests/build" "$T/update/core" "$T/update/tests"
  neg_expect_reject "host_protocol_check: shield host with no protocol doc reddens" \
    'shield.*does not exist' \
    "$PY" tools/host_protocol_check.py --xr-core "$T"
}
neg_register shield_hostdoc_missing

# --- bidirectional table law: a doc-only (phantom) method reddens ---------
case_shield_phantom_method() {
  local T="$NEG_TMP/t2-phantom"
  mkdir -p "$T"
  cp -r ../xr-core/shield "$T/shield"
  rm -rf "$T/shield/tests" "$T/shield/core"
  # the phantom row must land INSIDE the ## Methods table (the parser stops
  # at the next heading), right after the `apply` row
  "$PY" - "$T/shield/host_protocol.md" <<'PYEOF'
import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_text().splitlines(keepends=True)
for i, ln in enumerate(lines):
    if ln.startswith("| `apply` |"):
        lines.insert(i + 1, "| `ghost-method` | `{}` | no dispatching code |\n")
        break
p.write_text("".join(lines))
PYEOF
  neg_expect_reject "host_protocol_check: a phantom shield table entry reddens" \
    'NO dispatching code' \
    "$PY" tools/host_protocol_check.py --xr-core "$T"
}
neg_register shield_phantom_method

# --- corpus completeness: a method with zero parity cases reddens ---------
case_shield_corpus_method_gap() {
  local M="$NEG_TMP/t2-manifest.json" C="$NEG_TMP/t2-corpus-shield.json"
  "$PY" - "$M" "$C" <<'PYEOF'
import json, sys
from pathlib import Path
corpus = json.loads(Path("tools/parity/corpus-shield.json").read_text())
corpus["cases"] = [c for c in corpus["cases"] if c["method"] != "match"]
Path(sys.argv[2]).write_text(json.dumps(corpus, indent=1, sort_keys=True))
man = json.loads(Path("tools/parity/manifest.json").read_text())
for p in man["pairs"]:
    if p["id"] == "shield":
        p["corpus"] = sys.argv[2]  # absolute path override
Path(sys.argv[1]).write_text(json.dumps(man, indent=1, sort_keys=True))
PYEOF
  neg_expect_reject "parity_completeness: a shield corpus with a method gap reddens" \
    'ZERO parity cases' \
    "$PY" tools/parity_completeness.py --repo . --manifest "$M"
}
neg_register shield_corpus_method_gap
