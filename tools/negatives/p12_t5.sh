# tools/negatives/p12_t5.sh — P12-T5 negatives (exception interplay).
#
# T5: "Cosmetic and network must consult the SAME P11 exception-add/scopes
# object; shields-down flips one bit both read." Two planted defects prove the
# gates that make that law structural can actually fail:
#   * split-brain: cosmetic reading its OWN private exception store — the
#     single-scope-object grep (tools/cosmetic_scope_single_check.py) must
#     redden the gate;
#   * naive optimization: keying on the top-level (embedder) site — the
#     byte-parity checker must DRIFT when the fake silently adopts it.
#
# Sourced by tools/run_negatives.sh through NEG_FILES (provides lib.sh and PY).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- split-brain: a private exception store in the cosmetic surface ---------
case_cosmetic_split_brain_private_store() {
  local T="$NEG_TMP/t5-splitbrain"
  mkdir -p "$T/renderer" "$T/fakes"
  cp -r ../xr-core/renderer/cosmetic "$T/renderer/cosmetic"
  rm -rf "$T/renderer/cosmetic/tests/build"
  cp ../xr-core/fakes/cosmetic.py ../xr-core/fakes/_base.py "$T/fakes/"
  # positive control: the unmutated copy passes the single-scope-object check
  if ! "$PY" tools/cosmetic_scope_single_check.py --repo . --xr-core "$T" \
      >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: cosmetic_scope_single_check positive control must pass on the clean copy"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  echo "ok: cosmetic_scope_single_check positive control (clean copy passes)"
  # plant the defect: a private exception store the cosmetic half reads on its
  # own — the exact split-brain the phase exists to make impossible.
  printf '\n// PRIVATE exception-sweep store: cosmetic must consult the SAME\n// P11 scopes object shield writes, never its own copy.\n' \
    >> "$T/renderer/cosmetic/core/scope_key.h"
  neg_expect_reject "cosmetic single-scope-object: a planted private exception store reddens" \
    'single-scope-object law' \
    "$PY" tools/cosmetic_scope_single_check.py --repo . --xr-core "$T"
}
neg_register cosmetic_split_brain_private_store

# --- naive optimization: key on the top-level (embedder) site --------------
case_cosmetic_naive_embedder_key() {
  if ! command -v g++ >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    neg_skip "cosmetic naive-embedder-key negative (g++/make absent; CI runs it)"
    return 0
  fi
  local T="$NEG_TMP/t5-naive"
  mkdir -p "$T/renderer"
  cp -r ../xr-core/renderer/cosmetic "$T/renderer/cosmetic"
  cp -r ../xr-core/common "$T/common"
  cp -r ../xr-core/fakes "$T/fakes"
  rm -rf "$T/renderer/cosmetic/tests/build"
  # positive control: the unmutated copy replays byte-identical
  if ! "$PY" tools/cosmetic_vectors_check.py --repo . --xr-core "$T" \
      >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: cosmetic_vectors_check positive control must pass on the clean copy"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  echo "ok: cosmetic_vectors_check positive control (clean copy passes)"
  # plant the naive optimization: silently key on the embedder instead of
  # refusing it ("key on top-level site only"), one drift, one red.
  python3 - "$T/fakes/cosmetic.py" <<'PYEOF'
import sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
# drop the embedder refusal (the law it made structural) …
t = t.replace(
    """    embedder = args.get("embedder_site")
    if isinstance(embedder, str) and embedder:
        return _rejected("embedder-refused",
                         "the embedder site is not an input to the scope key")""",
    "    embedder = args.get(\"embedder_site\")")
# … and fold the embedder into the key (the naive optimization itself) …
t = t.replace(
    '    frame = sep.join(["cosmetic-scope-v1", args["frame_site"], trust,\n'
    '                      args["frame_identity"], args["url_class"], nav_token])',
    '    frame = sep.join(["cosmetic-scope-v1", args["frame_site"], trust,\n'
    '                      args["frame_identity"], args["url_class"], nav_token,\n'
    '                      str(embedder)])')
p.write_text(t, encoding="utf-8")
PYEOF
  neg_expect_reject "cosmetic byte-parity: keying on the embedder (naive optimization) reddens" \
    'DRIFT' \
    "$PY" tools/cosmetic_vectors_check.py --repo . --xr-core "$T"
}
neg_register cosmetic_naive_embedder_key
