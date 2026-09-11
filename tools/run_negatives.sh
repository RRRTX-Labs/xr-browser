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
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export NEG_TMP="$TMP"
export PY

# shellcheck disable=SC1091
. tools/negatives/lib.sh

# The ordered case-file list (the dispatcher's only hand-written bit; each
# file must exist or the gate fails closed rather than silently dropping an
# area). p9_ci.sh carries the T1–T12 runner canaries.
NEG_FILES=(p1_p2.sh p3_p4.sh p5_p6.sh p7_p8.sh p9_core.sh p9_ci.sh p10_release.sh p11_t0.sh p11_t0d.sh p11_t0e.sh p11_t1.sh p11_t2.sh)

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
