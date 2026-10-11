#!/usr/bin/env python3
"""tools/neg_interference_repro.py — P15-CLOSE C10: reproduce the negatives
interference hazard (red) and prove its fix (green).

Two concurrent "runs" each execute the same case body: build the case's
scratch directory, write an owner marker, meet at a barrier (so the overlap
is deterministic, not a timing accident), then read the marker back. A run
that reads the OTHER run's marker has collided.

  --mode legacy  the pre-fix shape: NEG_TMP unset, so the scratch root falls
                 back to the shared `${NEG_TMP:-${TMPDIR:-/tmp}}` (what
                 lib.sh did before C10), plus a FIXED case path under it (the
                 `$NEG_TMP/t4-norow` shape). Both runs share one TMPDIR.
                 Expected: collision -> exit 1 (the captured red).
  --mode fixed   the shipped shape: source tools/negatives/isolation.sh, take
                 the root from neg_tmp_root and the case dir from
                 neg_case_dir. Exercised twice — NEG_TMP unset (each run gets
                 a private mktemp -d root) and NEG_TMP SHARED by both runs
                 (neg_case_dir still separates them). Expected: no collision
                 -> exit 0 (the captured green).

Nothing here reads the wall clock; the barrier polls files with a bounded
iteration count. Stdlib only. Exit: 0 no collision · 1 collision or barrier
failure · 2 usage.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ISOLATION = REPO / "tools" / "negatives" / "isolation.sh"

# The case body both runs execute. $D is chosen by the mode prologue.
BODY = r'''
mkdir -p "$D" || { echo "setup failed: $D"; exit 3; }
printf '%s\n' "$TAG" >"$D/owner"
: >"$SYNC/ready.$TAG"
i=0
while [ ! -e "$SYNC/ready.$OTHER" ]; do
  i=$((i + 1))
  if [ "$i" -gt 2000 ]; then echo "barrier failed: $TAG never met $OTHER"; exit 3; fi
  sleep 0.01
done
got="$(cat "$D/owner")"
if [ "$got" != "$TAG" ]; then
  echo "collision: run $TAG found run $got's marker in $D"
  exit 1
fi
echo "clean: run $TAG kept $D to itself"
'''

PROLOGUE = {
    # Pre-C10 lib.sh fallback + a fixed per-case name.
    "legacy": 'unset NEG_TMP\nD="${NEG_TMP:-${TMPDIR:-/tmp}}/t4-norow"\n',
    # The shipped helpers (NEG_TMP state decided by the variant).
    "fixed": f'. "{ISOLATION}"\nneg_tmp_root || exit 3\nD="$(neg_case_dir t4-norow)" || exit 3\n',
}


def run_pair(mode: str, shared_negtmp: bool, work: Path) -> tuple[bool, list[str]]:
    sync = Path(tempfile.mkdtemp(prefix="sync.", dir=work))
    tmpdir = work / "shared-TMPDIR"  # both runs share ONE TMPDIR (the hazard)
    tmpdir.mkdir(exist_ok=True)
    negtmp = work / "shared-NEG_TMP"
    negtmp.mkdir(exist_ok=True)
    procs = []
    for tag, other in (("A", "B"), ("B", "A")):
        env = dict(os.environ, TAG=tag, OTHER=other, SYNC=str(sync), TMPDIR=str(tmpdir))
        env.pop("NEG_TMP", None)
        if shared_negtmp:
            env["NEG_TMP"] = str(negtmp)
        script = "set -u\n" + PROLOGUE[mode] + BODY
        procs.append(subprocess.Popen(["bash", "-c", script], env=env, cwd="/",
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True))
    lines, collided = [], False
    for p in procs:
        out, _ = p.communicate()
        lines.extend(ln for ln in out.splitlines() if ln.strip())
        if p.returncode != 0:
            collided = True
    return collided, lines


def main() -> int:
    ap = argparse.ArgumentParser(prog="neg_interference_repro")
    ap.add_argument("--mode", choices=["legacy", "fixed"], required=True)
    args = ap.parse_args()
    if not ISOLATION.is_file():
        print(f"FAIL: {ISOLATION} missing")
        return 1
    variants = ([("shared TMPDIR, NEG_TMP unset", False)] if args.mode == "legacy"
                else [("shared TMPDIR, NEG_TMP unset", False),
                      ("shared TMPDIR, NEG_TMP shared", True)])
    bad = False
    with tempfile.TemporaryDirectory(prefix="xr-neg-repro-") as tmp:
        for i, (label, shared) in enumerate(variants):
            work = Path(tmp) / f"v{i}"
            work.mkdir()
            collided, lines = run_pair(args.mode, shared, work)
            print(f"== {args.mode}: two concurrent runs, {label}")
            for ln in lines:
                print(f"   {ln.replace(tmp, '<work>')}")
            bad = bad or collided
    if bad:
        print(f"RED: concurrent runs collided ({args.mode} scratch shape)")
        return 1
    print(f"GREEN: no collision ({args.mode} scratch shape: per-case mktemp -d)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
