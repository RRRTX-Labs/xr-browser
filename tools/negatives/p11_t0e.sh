# tools/negatives/p11_t0e.sh — P11-T0-e negative cases: the touched-file
# size law (<=380 lines for every .py/.sh the phase touched) must redden on
# an over-limit file, and pass on a range that touches nothing over-limit.

# --- 73. touched-file size law: a fat touched file reddens --touched --------
case_touched_size_law() {
  local R="$NEG_TMP/sizelaw"; mkdir -p "$R/tools"
  git -C "$R" init -q
  git -C "$R" config user.email "neg@fixture"
  git -C "$R" config user.name "neg fixture"
  printf '#!/bin/sh\necho small\n' > "$R/tools/small.sh"
  git -C "$R" add -A && git -C "$R" commit -qm "base"
  local BASE; BASE=$(git -C "$R" rev-parse HEAD)
  local i
  { printf '#!/bin/sh\n'; for i in $(seq 1 385); do printf 'echo line %s\n' "$i"; done; } > "$R/tools/fat.sh"
  git -C "$R" add -A && git -C "$R" commit -qm "fat"
  neg_expect_reject "touched-file size law: 386-line touched .sh reddens --touched" \
    'fat\.sh' \
    "$PY" build/tests/test_file_size_law.py --touched "$BASE..HEAD" --repo "$R"
  # positive control: a range that touched nothing over-limit passes (an
  # empty range is vacuously green BY RULE — it judges no files and says so)
  if "$PY" build/tests/test_file_size_law.py --touched "$BASE..$BASE" --repo "$R" >/dev/null 2>&1; then
    echo "ok: touched-file size law positive control (empty range passes)"
  else
    echo "NEGATIVE-FAIL: touched-file positive control must pass on an empty range"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register touched_size_law
