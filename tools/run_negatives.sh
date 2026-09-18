#!/usr/bin/env bash
# run_negatives.sh — proof that the P1→P9 gates fail on bad input (dispatcher).
#
# P9-T0-d: this is now a THIN dispatcher. Every case lives in a per-area
# file under tools/negatives/ (each well under the 400-LOC law); the shared
# expect_reject helper, the failure counter, the totals and the self-test
# live in tools/negatives/lib.sh. The case count is DERIVED at runtime from
# registration (a hard-coded number is a lie waiting to happen), a case that
# never ran is an error, and a case whose command exits 0 reddens the gate.
#
# Usage: tools/run_negatives.sh [--self-test]
#   --self-test  run the harness's own canaries (rc=0, derived-N, never-ran).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
# P12-T0-d: scratch is preflighted, not discovered mid-run by a tar ENOSPC.
# The negatives battery tars whole trees into scratch; on a ~993 MiB $TMPDIR
# tmpfs that used to die partway with
#   tar: xr-core/update/tests/build/test_update_fuzz: Cannot write:
#       No space left on device
# which reads exactly like a real defect. tools/scratch.sh prefers the
# repo-local work/scratch, excludes build outputs from every fixture tar, and
# fails fast with the free space it needs.
# shellcheck disable=SC1091
. "$(dirname "$0")/scratch.sh"
scratch_require "${XR_NEG_SCRATCH_MIB:-512}" || {
  rc=$?
  [ "$rc" -eq 77 ] && exit 77
  exit 1
}
TMP="$(scratch_dir)/negatives.$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT
export NEG_TMP="$TMP"
export PY

# shellcheck disable=SC1091
. tools/negatives/lib.sh

# The ordered case-file list (the dispatcher's only hand-written bit; each
# file must exist or the gate fails closed rather than silently dropping an
# area). p9_ci.sh carries the T1–T12 runner canaries.
NEG_FILES=(p1_p2.sh p3_p4.sh p5_p6.sh p7_p8.sh p9_core.sh p9_ci.sh p10_release.sh p11_t0.sh p11_t0d.sh p11_t0e.sh p11_t1.sh p11_t2.sh p11_t3.sh p11_t4.sh p11_t5.sh p11_t6.sh p11_t10.sh p12_t0.sh p12_t0d.sh p12_close.sh)

if [ "${1:-}" = "--self-test" ]; then
  neg_self_test "${NEG_FILES[@]}"
  echo "NEGATIVE GATE SELF-TEST OK"
  exit 0
fi

for f in "${NEG_FILES[@]}"; do
  if [ ! -f "tools/negatives/$f" ]; then
    echo "NEGATIVE GATE FAILED: case file tools/negatives/$f missing (a dropped area is invisible otherwise)"
    exit 1
  fi
  # shellcheck disable=SC1090
  . "tools/negatives/$f"
done

neg_run_all
neg_finish
