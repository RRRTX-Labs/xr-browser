#!/usr/bin/env bash
# tools/scratch.sh — scratch-space hygiene for the harnesses (P12-T0-d).
#
# Root cause. tools/run_negatives.sh (and friends) tar the tree — INCLUDING
# xr-core/*/tests/build/** artifacts — into $TMPDIR, which on this class of
# machine is a ~993 MiB tmpfs. The observed failure was
#   tar: xr-core/update/tests/build/test_update_fuzz: Cannot write:
#       No space left on device
# and, run concurrently with the gate, two tests failed that pass in isolation
# and in a clean sequential run. "Cannot write" mid-gate is indistinguishable
# from a real defect for whoever reads the log next, so this module makes
# scratch a first-class, preflighted concern.
#
# Laws implemented here:
#   * scratch prefers a REPO-LOCAL work/scratch (gitignored) over $TMPDIR,
#     because $TMPDIR on these machines is a small tmpfs; $TMPDIR is honoured
#     when the caller explicitly sets XR_SCRATCH_DIR or when work/ is not
#     writable;
#   * fixture tars EXCLUDE build outputs (*/build/, target/, node_modules/,
#     __pycache__, *.o, .git) — they are regenerable and they are what fills
#     the volume;
#   * a preflight FAILS FAST with "need >= N MiB free in <dir>; got M" before
#     any work starts, instead of a mid-run tar ENOSPC;
#   * tests still never write into the repo tree (work/ is gitignored scratch,
#     not a source path).
#
# Usage (sourced):
#   . tools/scratch.sh
#   scratch_require 512        # fail fast unless >= 512 MiB free
#   D="$(scratch_dir)"         # the chosen scratch root
#   scratch_tar_tree "$DEST"   # copy the tree, excluding build outputs

# Exclude list for fixture tars. Build outputs are the thing that fills a
# tmpfs and they are always regenerable, so they never ride along.
SCRATCH_TAR_EXCLUDES=(
  --exclude=./.git
  --exclude='.git'
  --exclude='*/build/*'
  --exclude='./build/qa/*/build'
  --exclude='target'
  --exclude='node_modules'
  --exclude='__pycache__'
  --exclude='*.pyc'
  --exclude='*.o'
  --exclude='*.log'
  --exclude='.pytest_cache'
  --exclude='.mypy_cache'
  --exclude='.ruff_cache'
)

_scratch_root="${XR_SCRATCH_DIR:-}"

# scratch_dir — echo the scratch root, creating it if needed.
scratch_dir() {
  local d
  if [ -n "$_scratch_root" ]; then
    d="$_scratch_root"
  else
    # Repo-local first: $TMPDIR is a small tmpfs on these machines.
    d="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/work/scratch"
    if ! mkdir -p "$d" 2>/dev/null; then
      d="${TMPDIR:-/tmp}/xr-scratch"
      mkdir -p "$d" 2>/dev/null || { echo "" ; return 1; }
    fi
  fi
  printf '%s\n' "$d"
}

# _scratch_free_mib <dir> — free MiB on the filesystem holding <dir>.
_scratch_free_mib() {
  local d="$1"
  # 1K blocks -> MiB. POSIX-portable enough for Linux/macOS.
  df -Pm "$d" 2>/dev/null | awk 'NR==2 {print $4}'
}

# scratch_require <mib> — fail fast with a clear message, or SKIP-visible.
# Exit 77 when the caller wants a visible SKIP rather than a hard failure
# (set SCRATCH_SKIP_ON_SHORT=1); otherwise exit 1.
scratch_require() {
  local need="${1:-256}"
  local d free
  d="$(scratch_dir)" || {
    echo "SCRATCH-FAIL: no writable scratch directory (tried repo-local work/scratch and \$TMPDIR)"
    return 1
  }
  free="$(_scratch_free_mib "$d")"
  if [ -z "$free" ]; then
    echo "SCRATCH-FAIL: could not determine free space in $d (df failed)"
    return 1
  fi
  if [ "$free" -lt "$need" ]; then
    echo "SCRATCH-FAIL: need >= ${need} MiB free in ${d}; got ${free} MiB."
    echo "  A mid-run 'tar: Cannot write: No space left on device' is"
    echo "  indistinguishable from a real defect, so this fails BEFORE any"
    echo "  work starts. Free space, or point XR_SCRATCH_DIR at a larger"
    echo "  volume (the repo-local default is work/scratch because \$TMPDIR"
    echo "  is a small tmpfs on these machines)."
    if [ "${SCRATCH_SKIP_ON_SHORT:-0}" = "1" ]; then
      echo "SKIP (scratch space): need >= ${need} MiB, got ${free} MiB — needed for: running the fixture battery without a mid-run ENOSPC"
      return 77
    fi
    return 1
  fi
  echo "scratch: ${d} (${free} MiB free, >= ${need} MiB required)"
  return 0
}

# scratch_tar_tree <dest-dir> — copy the xr-browser tree into <dest-dir>,
# excluding build outputs AND the scratch root itself.
#
# Refusing a dest inside the source tree is load-bearing, not politeness: a
# copy of the repo written under work/scratch nests a second copy of every
# file, the next copy nests that one, and one negative case produced a 305 MB
# recursive tree that then made license_audit report 2759 hits against copies
# of its own source. Excluding ./work stops the recursion; the guard stops the
# class.
scratch_tar_tree() {
  local dest="$1"
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  # Match the RAW path. Resolving `dirname "$dest"` first is wrong: when the
  # parent does not exist yet the `cd` fails, the substitution collapses to
  # "/<basename>", and the guard silently stops matching (that exact bug let a
  # repo-into-itself copy through once already).
  case "$dest" in
    "$root"/*|"$root")
      echo "SCRATCH-FAIL: refusing to copy the repo into itself ($dest is under $root) — a tree copied under work/scratch nests recursively and poisons every tree-scanning gate"
      return 1
      ;;
  esac
  mkdir -p "$dest" || return 1
  ( cd "$root" && tar "${SCRATCH_TAR_EXCLUDES[@]}" --exclude=./work -cf - . ) \
    | ( cd "$dest" && tar -xf - )
}

# scratch_tar_xr_core <dest-parent> — copy ../xr-core into <dest-parent>,
# excluding build outputs (the fixture that filled the tmpfs).
scratch_tar_xr_core() {
  local dest_parent="$1"
  local core
  core="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../xr-core" 2>/dev/null && pwd)" \
    || { echo "scratch: no sibling xr-core checkout; skipping"; return 0; }
  mkdir -p "$dest_parent" || return 1
  ( cd "$core/.." && tar "${SCRATCH_TAR_EXCLUDES[@]}" -cf - \
      "$(basename "$core")" ) | ( cd "$dest_parent" && tar -xf - )
}
