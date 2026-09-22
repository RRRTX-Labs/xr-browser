# tools/negatives/p12_t2.sh — P12-T2 negatives (cosmetic.mojom + fuzz coverage).
#
# T2 added the ninth frozen interface (xr-core/mojom/cosmetic.mojom) and the
# fifth fuzz-fleet target. Each macOS here plants the exact defect the phase
# exists to make impossible:
#   * a scope-key request that smuggles the embedder site must be REFUSED —
#     the "key on the frame site only" law (renderer/cosmetic/core/scope_key.h
#     promises this fixture by name);
#   * a fleet target whose corpus dir is empty must FAIL the fleet gate (the
#     empty-run law the corpus seeds exist to serve).
#
# Sourced by tools/run_negatives.sh through NEG_FILES, which provides lib.sh
# (neg_expect_reject / neg_expect_inband / neg_skip / neg_register) and PY.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- scope-key: a non-empty embedder_site is REFUSED, never ignored --------
case_embedder_scope_key_refused() {
  # The fake is the deterministic reference backend (no g++ needed). The
  # request frame is exactly the host protocol's scope-key shape; the law is
  # "embedder-site ⇒ in-band kRejected embedder-refused", so this is an
  # IN-BAND rejection (the fake exits 0 and reports the refusal inside the ok
  # payload), matching neg_expect_inband.
  local FAKE="$REPO_ROOT/../xr-core/fakes/cosmetic.py"
  if [ ! -f "$FAKE" ]; then
    neg_skip "embedder_scope_key_refused needs ../xr-core/fakes/cosmetic.py"
    return 0
  fi
  neg_expect_inband "scope-key: a non-empty embedder_site must be refused (key on the frame site only, never silently dropped)" \
    'embedder-refused' \
    "$PY" "$FAKE" '{"method":"scope-key","args":{"frame_site":"frame.example","frame_identity":"xr:00000000-0000-4000-8000-000000000001","trust":"anonymous","navigation":"initial","url_class":"article","embedder_site":"top.example"}}'
}
neg_register embedder_scope_key_refused

# --- fuzz fleet: an empty corpus dir must FAIL (empty-run law) --------------
case_fuzz_fleet_empty_corpus_reddens() {
  if ! command -v g++ >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    neg_skip "fuzz_fleet empty-corpus negative (g++/make absent; CI runs it)"
    return 0
  fi
  local R="$NEG_TMP/fleet-empty"; mkdir -p "$R/build/fuzz/corpus/ghost-core"
  sed 's|build/fuzz/corpus/|build/fuzz/ghost-corpus/|g' \
    "$REPO_ROOT/build/fuzz/fleet.yaml" > "$R/build/fuzz/fleet.yaml"
  # The target list must still be there (the plant is ONLY the empty corpus:
  # a red for any other reason would be the wrong reason).
  grep -q 'cosmetic-core' "$R/build/fuzz/fleet.yaml" || {
    echo "NEGATIVE-FAIL: fleet_empty_corpus plant lost the target list"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return 1; }
  neg_expect_reject "fuzz_fleet: a target whose corpus dir is empty reddens (empty-run law — a seeded corpus is the libFuzzer lane's floor)" \
    'corpus dir .* is empty' \
    "$PY" "$REPO_ROOT/tools/fuzz_fleet.py" --repo "$R" --timebox 60
}
neg_register fuzz_fleet_empty_corpus_reddens
