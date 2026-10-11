# shellcheck shell=bash
# tools/negatives/p15c_c10.sh — P15-CLOSE C10 negatives: the interference
# hazard is reproduced (red) and fixed (green), and the single-instance lock
# refuses a second battery and names the holder.
#
# The nested battery is always `run_negatives.sh --self-test`: the lock is
# taken BEFORE that branch, so a working lock refuses it, and a broken lock
# lets it run only the quick canaries (exit 0, which reddens the case) — never
# a recursive full battery. Each case uses its own lock file under a per-case
# mktemp -d, so the outer battery's own lock is never involved.

# _c10_hold <lockfile> <dir> [mode]: a background holder of <lockfile>;
# echoes its pid once it holds the lock (bounded wait, no wall clock). The
# holder's stdout is detached: a command substitution waits for every writer.
_c10_hold() {
  local L="$1" W="$2" mode="${3:-auto}" i=0
  XR_NEG_LOCK_MODE="$mode" bash -c '. tools/negatives/isolation.sh
    neg_lock_acquire "$1" >/dev/null || exit 1
    : >"$2/held"
    while [ ! -e "$2/release" ]; do sleep 0.05; done
    neg_lock_release' _ "$L" "$W" >/dev/null 2>&1 &
  local pid=$!
  while [ ! -e "$W/held" ] && [ "$i" -lt 400 ]; do sleep 0.05; i=$((i + 1)); done
  echo "$pid"
}

_c10_release() {   # <dir> <pid> — the holder is not our child: poll, bounded
  local i=0
  : >"$1/release"
  while kill -0 "$2" 2>/dev/null && [ "$i" -lt 200 ]; do sleep 0.05; i=$((i + 1)); done
}

case_p15c_interference_red() {
  neg_expect_reject "C10: two concurrent runs on the pre-fix shared scratch shape collide (the red)" \
    'collision: run [AB] found run [AB]' \
    "$PY" tools/neg_interference_repro.py --mode legacy
  local out rc
  out="$("$PY" tools/neg_interference_repro.py --mode fixed 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; neg_out_has '^GREEN: no collision'; }; then
    echo "ok: C10 positive control (per-case mktemp -d: the same two runs do not collide)"
  else
    echo "NEGATIVE-FAIL: C10 the fixed scratch shape must not collide (rc=$rc)"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register p15c_interference_red

case_p15c_lock_flock() {
  local W pid
  W="$(neg_case_dir p15c-c10-flock)"
  pid="$(_c10_hold "$W/neg.lock" "$W" auto)"
  neg_expect_reject "C10: a second run_negatives.sh refuses while the first holds the lock (flock) and names the holder" \
    "held by pid $pid: " \
    env XR_NEG_LOCK="$W/neg.lock" bash tools/run_negatives.sh --self-test
  _c10_release "$W" "$pid"
}
neg_register p15c_lock_flock

case_p15c_lock_mkdir() {
  local W pid
  W="$(neg_case_dir p15c-c10-mkdir)"
  pid="$(_c10_hold "$W/neg.lock" "$W" mkdir)"
  neg_expect_reject "C10: the mkdir fallback lock refuses a second run while a LIVE holder has it" \
    "held by pid $pid: " \
    env XR_NEG_LOCK_MODE=mkdir XR_NEG_LOCK="$W/neg.lock" bash tools/run_negatives.sh --self-test
  _c10_release "$W" "$pid"
}
neg_register p15c_lock_mkdir

case_p15c_lock_stale() {
  # A dead holder's mkdir lock is reclaimed (stale-pid detection), so a crash
  # never wedges the gate. The pid is a process that has already exited.
  local W dead out rc
  W="$(neg_case_dir p15c-c10-stale)"
  bash -c 'exit 0' &
  dead=$!
  wait "$dead" || true
  mkdir "$W/neg.lock.d"
  printf 'pid %s: crashed battery\n' "$dead" >"$W/neg.lock.d/pid"
  out="$(env XR_NEG_LOCK_MODE=mkdir XR_NEG_LOCK="$W/neg.lock" bash tools/run_negatives.sh --self-test 2>&1)" \
    && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && { neg_out_file "$out"; neg_out_has 'reclaiming a stale negatives lock'; } \
     && [ ! -e "$W/neg.lock.d" ]; then
    echo "ok: C10 positive control (a dead holder's mkdir lock is reclaimed and released on exit)"
  else
    echo "NEGATIVE-FAIL: C10 a stale mkdir lock must be reclaimed (rc=$rc)"
    printf '%s\n' "$out" | tail -n 5 | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register p15c_lock_stale
