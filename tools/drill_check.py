#!/usr/bin/env python3
"""tools/drill_check.py — the drill-matrix data gate (P9-T10/T11).

Plan P9-T10 (update-drill lab) and P9-T11 (crash/recovery kill matrix) are
VM/browser drills: their execution is farm work (HG-33/HG-34), but their
MATRICES are data this repo owns, and this gate keeps them honest:

  1. EMPTY-RUN — zero rows in either matrix is a failure.
  2. COMPLETE — the kill matrix names all 8 §11.10 process types
     (browser/renderer/network/vaultd/tord/wgd/inspect/gpu); the update
     drill names all 3 OS (linux/macos/windows).
  3. OWNED + ASSERTED — every row has non-empty assertions; a row with no
     assertion is a failure (the canary: delete one and watch it go red).
  4. FARM-RUNNER PRESENT — build/qa/drill/drill_run.sh exists and is
     SKIP-visible (exit 77) without the farm browser — never a fake pass.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE  # noqa: E402

KILL_MATRIX = "build/qa/drill/kill-matrix.yaml"
UPDATE_DRILL = "build/qa/drill/update-drill.yaml"
DRILL_RUN = "build/qa/drill/drill_run.sh"
REQUIRED_PROCESSES = ["browser", "renderer", "network", "vaultd", "tord",
                      "wgd", "inspect", "gpu"]
REQUIRED_OS = ["linux", "macos", "windows"]


def check(repo: Path, *, kill_matrix: Path | None = None,
          update_drill: Path | None = None) -> list[str]:
    import yaml
    fails: list[str] = []

    km = kill_matrix or (repo / KILL_MATRIX)
    if not km.exists():
        fails.append(f"missing {KILL_MATRIX}")
        return fails
    kdoc = yaml.safe_load(km.read_text(encoding="utf-8"))
    krows = list(kdoc.get("rows") or [])
    if not krows:
        fails.append(f"{KILL_MATRIX}: zero rows (empty-run law)")
    procs = [r.get("process") for r in krows]
    for req in REQUIRED_PROCESSES:
        if req not in procs:
            fails.append(f"{KILL_MATRIX}: missing process type {req!r}")
    for r in krows:
        if not r.get("assertions"):
            fails.append(f"{KILL_MATRIX}: row {r.get('process')!r} has no "
                         f"assertions")

    ud = update_drill or (repo / UPDATE_DRILL)
    if not ud.exists():
        fails.append(f"missing {ud}")
        return fails
    udoc = yaml.safe_load(ud.read_text(encoding="utf-8"))
    urows = list(udoc.get("rows") or [])
    if not urows:
        fails.append(f"{UPDATE_DRILL}: zero rows (empty-run law)")
    oses = [r.get("os") for r in urows]
    for req in REQUIRED_OS:
        if req not in oses:
            fails.append(f"{UPDATE_DRILL}: missing OS {req!r}")
    for r in urows:
        if not r.get("assertions") or not r.get("kill_point"):
            fails.append(f"{UPDATE_DRILL}: row {r.get('os')!r} has no "
                         f"assertions/kill_point")

    runner = repo / DRILL_RUN
    if not runner.exists():
        fails.append(f"missing {DRILL_RUN}")
    else:
        proc = subprocess.run(["bash", str(runner), "kill-matrix"],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 77:
            fails.append(f"{DRILL_RUN} should SKIP (77) without the farm "
                         f"browser; got {proc.returncode}")
        if "SKIP" not in (proc.stdout + proc.stderr):
            fails.append(f"{DRILL_RUN}: SKIP not visible (honesty law)")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="drill_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--kill-matrix", default="", help="override path (fixtures)")
    p.add_argument("--update-drill", default="", help="override path (fixtures)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    km = Path(args.kill_matrix) if args.kill_matrix else None
    ud = Path(args.update_drill) if args.update_drill else None
    fails = check(repo, kill_matrix=km, update_drill=ud)
    if args.json:
        print(json.dumps({"tool": "drill_check", "count": len(fails),
                          "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"drill_check: {len(fails)} violation(s) "
              f"({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
