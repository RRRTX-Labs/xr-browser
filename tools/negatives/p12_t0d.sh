# tools/negatives/p12_t0d.sh — P12-T0-d scratch-hygiene negatives.
#
# Split out of p12_t0.sh by the P11-T0-e touched-file size law (<=380 lines on
# any file this phase touches): p12_t0.sh reached 402 once the T0-d cases were
# added. This is the same fix applied to tools/run_checks.sh at 384 lines —
# move the body into a module, keep the dispatcher thin. The cases are
# unchanged; only the file they live in moved.
#
# Sourced by tools/run_negatives.sh through NEG_FILES, which provides lib.sh
# (neg_expect_reject / neg_expect_inband / neg_skip / neg_register) and
# REPO_ROOT / PY. tools/scratch.sh is sourced by the runner before this file.

# --- T0-d: scratch hygiene -------------------------------------------------
case_scratch_preflight_fails_fast() {
  # A scratch dir below the required free space must fail BEFORE any work,
  # with the number it needed — not mid-run with a tar ENOSPC.
  local out rc
  out="$(cd "$REPO_ROOT" && bash -c '. tools/scratch.sh; scratch_require 999999999' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: scratch_require accepted an impossible free-space demand"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'need >= 999999999 MiB free in'; then
    echo "NEGATIVE-FAIL: scratch_require failed but did not name the requirement"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch_require fails fast with the free space it needs"
  fi
}
neg_register scratch_preflight_fails_fast

case_scratch_preflight_skip_shape() {
  local out rc
  out="$(cd "$REPO_ROOT" && SCRATCH_SKIP_ON_SHORT=1 bash -c \
    '. tools/scratch.sh; scratch_require 999999999' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 77 ]; then
    echo "NEGATIVE-FAIL: SCRATCH_SKIP_ON_SHORT must yield a visible SKIP (77), got rc=$rc"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'SKIP (scratch space)'; then
    echo "NEGATIVE-FAIL: the SKIP line must be visible, not silent"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch short-fall SKIPs visibly (77) rather than failing silently"
  fi
}
neg_register scratch_preflight_skip_shape

case_scratch_tar_excludes_build_outputs() {
  # The exclusion list IS the fix (build outputs are what filled the ~993 MiB
  # tmpfs), so assert it directly rather than tarring the whole tree inline --
  # a full-tree copy in a negative case costs more than the battery's budget
  # and would itself look like a hang.
  local missing=0 e
  for e in "./.git" "'*/build/*'" "'target'" "'node_modules'" \
           "'__pycache__'" "'*.o'"; do
    if ! grep -qF -- "--exclude=$e" "$REPO_ROOT/tools/scratch.sh"; then
      echo "NEGATIVE-FAIL: SCRATCH_TAR_EXCLUDES is missing $e"
      missing=$((missing + 1))
    fi
  done
  if [ "$missing" -ne 0 ]; then
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  fi
  # and prove the helper actually produces a tree WITHOUT .git on a tiny
  # synthetic source, so the assertion is about behaviour, not just text.
  local S="$NEG_TMP/scratch-src" D="$NEG_TMP/scratch-dst"
  rm -rf "$S" "$D"; mkdir -p "$S/.git" "$S/sub/build" "$S/__pycache__"
  echo keep > "$S/keep.txt"; echo junk > "$S/.git/obj"
  echo junk > "$S/sub/build/art.o"; echo junk > "$S/__pycache__/x.pyc"
  ( cd "$S" && tar "${SCRATCH_TAR_EXCLUDES[@]}" -cf - . ) \
    | ( mkdir -p "$D" && cd "$D" && tar -xf - )
  # Assert on FILES, not directories: `--exclude=*/build/*` matches the
  # CONTENTS of build/, so an emptied build/ directory may legitimately ride
  # along. What must never arrive is a .git object, a .o, or a .pyc.
  if find "$D" -name '*.o' -o -name '*.pyc' | grep -q . \
     || [ -e "$D/.git" ]; then
    echo "NEGATIVE-FAIL: the exclude list did not keep build outputs out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif [ ! -f "$D/keep.txt" ]; then
    echo "NEGATIVE-FAIL: the exclude list threw away source it should keep"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch excludes keep .git/build/__pycache__ out and source in"
  fi
}
neg_register scratch_tar_excludes_build_outputs

case_scratch_preflight_positive_control() {
  if (cd "$REPO_ROOT" && bash -c '. tools/scratch.sh; scratch_require 64') >/dev/null 2>&1; then
    echo "ok: scratch_require positive control (a satisfiable demand passes)"
  else
    echo "NEGATIVE-FAIL: scratch_require must pass when the space is there"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register scratch_preflight_positive_control

case_scratch_refuses_repo_into_itself() {
  # The incident this guards: a tree copied under work/scratch nested
  # recursively, producing a 305 MB tree that made license_audit report 2759
  # hits against copies of its own source.
  #
  # The invariant is NOT "refuse any destination inside the repo" — that broke
  # the pre-existing fixtures, which legitimately snapshot a tree under
  # $NEG_TMP. The invariant is "the copy must not contain itself", which the
  # tar's --exclude=./work already guarantees. So this case asserts the real
  # property on both sides: a copy under the scratch root must SUCCEED and must
  # not contain a nested copy, while a destination that IS the repo root or a
  # parent of it must be refused.
  local out rc B="$REPO_ROOT/work/scratch/selftest.$$"
  rm -rf "$B"
  out="$(cd "$REPO_ROOT" && bash -c ". tools/scratch.sh; scratch_tar_tree '$B'" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: scratch_tar_tree refused a legitimate scratch destination"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif [ -d "$B/work" ]; then
    echo "NEGATIVE-FAIL: the copy contains a nested work/ tree — recursion is not excluded"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif [ ! -f "$B/tools/scratch.sh" ]; then
    echo "NEGATIVE-FAIL: the copy is missing real source (exclude set is too broad)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch_tar_tree copies without self-nesting (no work/ inside the copy, real source present)"
  fi
  rm -rf "$B"

  # The refusals that ARE load-bearing: the repo onto itself, and into a parent.
  local d
  for d in "$REPO_ROOT" "$(cd "$REPO_ROOT/.." && pwd)"; do
    out="$(cd "$REPO_ROOT" && bash -c ". tools/scratch.sh; scratch_tar_tree '$d'" 2>&1)" && rc=0 || rc=$?
    if [ "$rc" -eq 0 ]; then
      echo "NEGATIVE-FAIL: scratch_tar_tree accepted a self-nesting destination ($d)"
      NEG_FAILURES=$((NEG_FAILURES + 1))
    elif ! printf '%s' "$out" | grep -q 'SCRATCH-FAIL'; then
      echo "NEGATIVE-FAIL: refused $d but not with SCRATCH-FAIL"
      printf '%s\n' "$out" | sed 's/^/    | /'
      NEG_FAILURES=$((NEG_FAILURES + 1))
    else
      echo "ok: scratch_tar_tree refuses a self-nesting destination ($d)"
    fi
  done
}
neg_register scratch_refuses_repo_into_itself

case_license_audit_skips_scratch() {
  # The other half of the same incident: a scratch tree inside the repo must
  # not be scanned as source.
  local R="$NEG_TMP/la-scratch"; rm -rf "$R"
  mkdir -p "$R/work/scratch/copy" "$R/docs/state"
  printf 'x = 1\n' > "$R/keep.py"
  # The marker text lives in a FIXTURE, not here: license_audit fails copyleft
  # tokens in code/shell files unconditionally, so spelling them out in this
  # case file reddened the very gate that runs it. The
  # tools/tests/fixtures/p11_vendor_red_licenses.json precedent.
  local FIX="$REPO_ROOT/tools/tests/fixtures/p12_copyleft_markers.json"
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); open(sys.argv[2],'w').write(d['scratch_marker']+chr(10))" \
    "$FIX" "$R/work/scratch/copy/junk.md"
  # the audit needs an allowlist to run at all (it exits 2 without one, which
  # would "pass" this case for the wrong reason)
  printf 'schema_version: 1\nallowlist: []\n' > "$R/docs/state/license-allowlist.yaml"
  cp "$REPO_ROOT/LICENSE" "$R/LICENSE"
  # positive control first: the SAME marker in a real source path must redden,
  # or a green here means the audit is simply not looking
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); open(sys.argv[2],'w').write(d['real_source_marker']+chr(10))" \
    "$FIX" "$R/real_source.md"
  if "$PY" "$REPO_ROOT/tools/license_audit.py" --repo "$R" >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: license_audit did NOT flag a copyleft marker in a real source path (the audit is not looking, so the scratch skip proves nothing)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  fi
  rm -f "$R/real_source.md"
  if "$PY" "$REPO_ROOT/tools/license_audit.py" --repo "$R" >/dev/null 2>&1; then
    echo "ok: license_audit skips the work/ scratch root (no hits on scratch copies)"
  else
    echo "NEGATIVE-FAIL: license_audit scanned work/ scratch and reddened on a copy"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register license_audit_skips_scratch
