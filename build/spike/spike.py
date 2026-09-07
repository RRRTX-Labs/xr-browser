"""spike.py — `./scripts/build spike <sub>` (P4).

Subcommands
  genpatch        real apply/verify/revert round-trip of the candidate patch
                  against pinned-rev Chromium files (fetch -> apply -> verify
                  -> revert byte-exact + drift negative)
  citation-audit  re-fetch every file:line citation in the spike docs at the
                  pin and verify the quoted text is still there
  census-lint     enforce the papercut census schema
  probe           probe driver: --offline (static + fixture) or --farm (HG-21)

Exit codes follow the house rule: 0 pass · 1 fail · 2 usage. --json everywhere.
Network is only ever touched inside genpatch/citation-audit, and only through
build/upstream/fetch.py.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_p / "upstream"))
        break

from _common import ToolError, main_with_guard  # noqa: E402

HERE = Path(__file__).resolve().parent
USAGE = {
    "genpatch": "apply/verify/revert the 0042 candidate patch at the pin (real bytes)",
    "citation-audit": "re-verify every file:line citation in docs/spike-identity/",
    "census-lint": "enforce the papercut census schema (13 named surfaces)",
    "probe": "run probe lanes: --offline (no browser) or --farm (HG-21)",
}


def _run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(HERE.parent.parent)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(prog="build/spike/spike.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("genpatch", help=USAGE["genpatch"])
    g.add_argument("--xr-core", default="../xr-core")
    g.add_argument("--out", default="work/spike-checkout")
    g.add_argument("--json", action="store_true")
    c = sub.add_parser("citation-audit", help=USAGE["citation-audit"])
    c.add_argument("--out", default="evidence/P4/logs/citation-audit.txt")
    c.add_argument("--json", action="store_true")
    cl = sub.add_parser("census-lint", help=USAGE["census-lint"])
    cl.add_argument("--json", action="store_true")
    p = sub.add_parser("probe", help=USAGE["probe"])
    p.add_argument("--offline", action="store_true")
    p.add_argument("--farm", action="store_true")
    p.add_argument("--binary")
    p.add_argument("--checkout")
    p.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "genpatch":
        return _run([sys.executable, str(HERE / "genpatch.py"),
                     "--xr-core", args.xr_core, "--out", args.out]
                    + (["--json"] if args.json else []))
    if args.cmd == "citation-audit":
        return _run([sys.executable, str(HERE / "citation_audit.py"),
                     "--out", args.out] + (["--json"] if args.json else []))
    if args.cmd == "census-lint":
        return _run([sys.executable, str(HERE / "census_lint.py")]
                    + (["--json"] if args.json else []))
    if args.cmd == "probe":
        cmd = [sys.executable, str(HERE / "probe_driver.py")]
        if args.farm:
            cmd += ["--farm", "--binary", args.binary or "",
                    "--checkout", args.checkout or "."]
        else:
            cmd += ["--offline"]
        return _run(cmd + (["--json"] if args.json else []))
    raise ToolError(f"unknown subcommand {args.cmd!r}")


if __name__ == "__main__":
    main_with_guard(main)
