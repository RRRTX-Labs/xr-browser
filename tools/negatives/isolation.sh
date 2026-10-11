# shellcheck shell=bash
# tools/negatives/isolation.sh — scratch isolation + the single-instance lock
# for the negatives battery (P15-CLOSE C10, the "interference hazard").
#
# Sourced by tools/negatives/lib.sh (scratch helpers) and by
# tools/run_negatives.sh (the lock). Not a case file: it registers nothing.
# Paths are resolved from BASH_SOURCE, never from the caller's cwd.
#
# The hazard (P15 brief §GATES): two concurrent batteries could write the
# same fixed path. Before this file, lib.sh fell back to the shared
# `${NEG_TMP:-${TMPDIR:-/tmp}}` when NEG_TMP was unset (a case file sourced
# outside the dispatcher), and the case files built FIXED names under that
# root (`$NEG_TMP/t4-norow`). Two runs sharing a TMPDIR then wrote into one
# directory. tools/neg_interference_repro.py reproduces that collision (red)
# and proves the fix below (green); tools/negatives/p15c_c10.sh pins both.
#
# Laws:
#   * neg_tmp_root: NEG_TMP is ALWAYS a private `mktemp -d` root. When the
#     dispatcher did not set it, one is created here (never a shared path)
#     and removed on exit if the caller has no EXIT trap of its own.
#   * neg_case_dir <tag>: a per-case `mktemp -d` under NEG_TMP, so even two
#     cases (or two runs) that share NEG_TMP never share a directory.
#   * neg_lock_acquire <lockfile>: a second run_negatives.sh refuses to start
#     while the first holds the lock, and SAYS WHO holds it. flock(1) when
#     present (the kernel drops the lock when the holder dies, so there is no
#     stale state); else an atomic `mkdir` lock with a pid file and stale-pid
#     detection (a dead holder's lock is reclaimed, a live one refuses).
#     XR_NEG_LOCK_MODE=mkdir forces the fallback so it stays tested.

neg_tmp_root() {
  if [ -n "${NEG_TMP:-}" ] && [ -d "$NEG_TMP" ]; then
    return 0
  fi
  NEG_TMP="$(mktemp -d "${TMPDIR:-/tmp}/xr-neg.XXXXXX")" || return 1
  export NEG_TMP
  if [ -z "$(trap -p EXIT)" ]; then
    # shellcheck disable=SC2064  # expand now: the path is fixed at creation
    trap "rm -rf '$NEG_TMP'" EXIT
  fi
}

neg_case_dir() {   # <tag> -> echoes a fresh private directory
  neg_tmp_root || return 1
  mktemp -d "$NEG_TMP/${1:-case}.XXXXXX"
}

# _neg_lock_holder <lockfile> — the human-readable owner line, or "unknown".
_neg_lock_holder() {
  local f="$1" line=""
  if [ -s "$f.owner" ]; then
    line="$(head -n 1 "$f.owner" 2>/dev/null || true)"
  elif [ -s "$f.d/pid" ]; then
    line="$(head -n 1 "$f.d/pid" 2>/dev/null || true)"
  fi
  printf '%s\n' "${line:-unknown holder (no owner record)}"
}

_neg_lock_owner_line() {
  local cmd
  cmd="$(tr '\0' ' ' </proc/$$/cmdline 2>/dev/null || printf '%s' "$0")"
  printf 'pid %s: %s(cwd %s)\n' "$$" "$cmd" "$PWD"
}

NEG_LOCK_HELD="${NEG_LOCK_HELD:-}"   # "" | "flock:<file>" | "mkdir:<file>"

neg_lock_release() {   # drop our owner record / mkdir lock (flock dies with fd 9)
  case "$NEG_LOCK_HELD" in
    flock:*) rm -f "${NEG_LOCK_HELD#flock:}.owner" ;;
    mkdir:*) rm -rf "${NEG_LOCK_HELD#mkdir:}.d" ;;
  esac
  NEG_LOCK_HELD=""
}

neg_lock_acquire() {   # <lockfile>; returns 0 = held, 1 = refused (message printed)
  local lock="$1" mode="${XR_NEG_LOCK_MODE:-auto}"
  mkdir -p "$(dirname "$lock")" || return 1
  if [ "$mode" != "mkdir" ] && command -v flock >/dev/null 2>&1; then
    # `<>` opens without truncating, so a refused instance never erases the
    # holder's record. fd 9 stays open for the life of the shell.
    exec 9<>"$lock" || return 1
    if ! flock -n 9; then
      echo "NEGATIVE GATE REFUSED: another run_negatives.sh holds the lock $lock (flock)"
      echo "  held by $(_neg_lock_holder "$lock")"
      echo "  concurrent batteries share the sibling xr-core build dirs; wait for it to finish"
      return 1
    fi
    _neg_lock_owner_line >"$lock.owner"
    NEG_LOCK_HELD="flock:$lock"
    return 0
  fi
  # Fallback: mkdir is atomic on POSIX filesystems.
  local tries=0 pid
  while [ "$tries" -lt 2 ]; do
    if mkdir "$lock.d" 2>/dev/null; then
      _neg_lock_owner_line >"$lock.d/pid"
      NEG_LOCK_HELD="mkdir:$lock"
      return 0
    fi
    pid="$(sed -n '1s/^pid \([0-9][0-9]*\):.*/\1/p' "$lock.d/pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "NEGATIVE GATE REFUSED: another run_negatives.sh holds the lock $lock.d (mkdir)"
      echo "  held by $(_neg_lock_holder "$lock")"
      echo "  concurrent batteries share the sibling xr-core build dirs; wait for it to finish"
      return 1
    fi
    echo "note: reclaiming a stale negatives lock ($lock.d; holder pid ${pid:-?} is gone)"
    rm -rf "$lock.d"
    tries=$((tries + 1))
  done
  echo "NEGATIVE GATE REFUSED: could not take $lock.d after reclaiming a stale lock"
  return 1
}
