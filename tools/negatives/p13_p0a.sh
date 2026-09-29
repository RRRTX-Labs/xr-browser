# tools/negatives/p13_p0a.sh — P13-P0-A negative cases: the entry-point-mode
# machinery and the mode-preservation law must be able to fail.
#
# Why these exist: the incident (5e3d1d4) could not be seen locally for three
# commits because `bash tools/run_checks.sh` cannot see a mode bit, and no lane
# checked the INDEX at all. A gate for that class is worthless unless a planted
# defect reddens it, so every case here plants the defect in a scratch mirror
# (worktree tar, .git excluded — then `git init` so the mirror has a real index
# to judge) and asserts the refusal.
#
# Sourced by tools/run_negatives.sh through NEG_FILES, which provides lib.sh
# (neg_expect_reject / neg_expect_inband / neg_skip / neg_register) and $PY.
# tools/scratch.sh is sourced by the runner before this file, which gives
# scratch_tar_tree (build outputs and ./work excluded).

# _p0a_mirror <dest>: a scratch mirror of this repo with a real git index whose
# modes come from the mirrored worktree — i.e. the same source of truth a fresh
# `git clone` gives a runner.
_p0a_mirror() {
  local dest="$1"
  rm -rf "$dest"
  scratch_tar_tree "$dest" || return 1
  ( cd "$dest" && git init -q && git add -A ) || return 1
}

_p0a_git() {
  git -c user.email=neg@x -c user.name=neg -c commit.gpgsign=false -C "$1" "${@:2}"
}

# --- Law 1: a planted 644 direct-exec entry point must redden ---------------
case_entry_mode_planted_644() {
  local R="$NEG_TMP/p0a-entry"
  _p0a_mirror "$R" || {
    echo "NEGATIVE-FAIL: could not build the scratch mirror"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  }
  printf '#!/bin/sh\nexit 0\n' > "$R/tools/planted_entry.sh"
  chmod 644 "$R/tools/planted_entry.sh"
  # a workflow step that executes it DIRECTLY (the governance.yml shape)
  printf '      - name: planted\n        run: ./tools/planted_entry.sh\n' \
    >> "$R/.github/workflows/governance.yml"
  ( cd "$R" && git add -A ) >/dev/null 2>&1
  # positive control first: the untouched mirror is clean, or the case is noise
  if "$PY" tools/entrypoint_mode_check.py --repo "$R" >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: the clean mirror did not pass the entry-point mode law"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  fi
  neg_expect_reject "entrypoint_mode_check: a planted 644 direct-exec entry point reddens" \
    'exit code 126' \
    "$PY" tools/entrypoint_mode_check.py --repo "$R"
  # and the exemption is real: the same file invoked as `bash <path>` is NOT a
  # violation (the interpreter is the executable), so that shape must pass.
  printf '      - name: planted-ok\n        run: bash tools/planted_entry.sh\n' \
    >> "$R/.github/workflows/governance.yml"
  sed -i 's|^        run: \./tools/planted_entry.sh$|        run: "true"|' \
    "$R/.github/workflows/governance.yml"
  ( cd "$R" && git add -A ) >/dev/null 2>&1
  if "$PY" tools/entrypoint_mode_check.py --repo "$R" >/dev/null 2>&1; then
    echo "ok: the interpreted form is exempt (a 644 file run as \`bash <path>\` passes)"
  else
    echo "NEGATIVE-FAIL: the interpreted exemption is broken (bash <path> reddened)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register entry_mode_planted_644

# --- Law 2: a commit inside the range that drops an exec bit must redden ----
case_entry_mode_drift_range() {
  local R="$NEG_TMP/p0a-drift"
  _p0a_mirror "$R" || {
    echo "NEGATIVE-FAIL: could not build the scratch mirror"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  }
  _p0a_git "$R" add -A >/dev/null 2>&1
  _p0a_git "$R" commit -qm "base: as the mirror found it" >/dev/null 2>&1
  # a benign commit, so the positive control has a real range to judge
  printf 'x\n' >> "$R/README.md"
  _p0a_git "$R" add -A >/dev/null 2>&1
  _p0a_git "$R" commit -qm "benign: a content-only change" >/dev/null 2>&1
  # the defect: exactly the 5e3d1d4 change, a dropped exec bit on an entry point
  chmod 644 "$R/tools/run_checks.sh"
  _p0a_git "$R" add -A >/dev/null 2>&1
  _p0a_git "$R" commit -qm "plant: drop the exec bit (the 5e3d1d4 shape)" >/dev/null 2>&1
  neg_expect_reject "entrypoint_mode_check --range: a dropped exec bit reddens with commit + path" \
    'lost its executable bit' \
    "$PY" tools/entrypoint_mode_check.py --repo "$R" --range HEAD~1..HEAD
  # Positive control, scoped deliberately: Law 1 judges the HEAD state, and this
  # mirror's HEAD is red on purpose (that is the plant), so the control reads the
  # RANGE law alone off the same invocation — the range HEAD~2..HEAD~1 contains
  # no mode change and must produce no drift finding.
  local out_clean
  out_clean="$("$PY" tools/entrypoint_mode_check.py --repo "$R" --range HEAD~2..HEAD~1 2>&1)" || true
  if { neg_out_file "$out_clean"; neg_out_has_fixed 'FAIL (mode drift)'; }; then
    echo "NEGATIVE-FAIL: the mode-drift law fired on a clean range"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: a clean range yields no mode-drift finding (no false positive)"
  fi
}
neg_register entry_mode_drift_range

# --- The mode-preservation canary: the naive rewrite must lose the bit ------
case_inplace_naive_rewrite_drops_mode() {
  neg_expect_reject "inplace --simulate-naive: the write-new-then-replace shape is caught" \
    'dropped the exec bit' \
    "$PY" tools/inplace.py --self-test --simulate-naive
  # positive control: the real helper passes the same assertions
  if "$PY" tools/inplace.py --self-test >/dev/null 2>&1; then
    echo "ok: inplace --self-test passes with the mode-preserving helper"
  else
    echo "NEGATIVE-FAIL: the mode-preserving helper failed its own assertions"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register inplace_naive_rewrite_drops_mode

# --- The fix's visibility: the CI-identical invocation must notice a 644 -----
# `bash tools/run_checks.sh` is blind to this by construction, which is why the
# first three "fix the CI" commits chased the wrong cause. `--via-ci-invocation`
# runs the gate the way the workflow does and refuses loudly instead.
case_ci_invocation_sees_a_644_entry_point() {
  local R="$NEG_TMP/p0a-ci"
  _p0a_mirror "$R" || {
    echo "NEGATIVE-FAIL: could not build the scratch mirror"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  }
  chmod 644 "$R/tools/run_checks.sh"
  ( cd "$R" && git add -A ) >/dev/null 2>&1         # index now says 100644
  neg_expect_reject "run_checks --via-ci-invocation: a 644 entry point is named, not executed" \
    'CI-INVOCATION FAIL.*100644' \
    bash -c "cd '$R' && bash tools/run_checks.sh --via-ci-invocation"
}
neg_register ci_invocation_sees_a_644_entry_point
