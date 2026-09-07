#!/usr/bin/env python3
"""build/contracts.py — P5 contract-freeze dispatcher (./scripts/build contracts).

Subcommands: manifest | lint | vectors | freeze | all
Each delegates to the corresponding tool under tools/. `all` runs the set and
returns non-zero if any fails. Stdlib only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
CORE_MOJOM = ROOT.parent / "xr-core" / "mojom"

STEPS = {
    "lint": [sys.executable, str(TOOLS / "mojom_lint.py"), "--roundtrip", str(CORE_MOJOM)],
    "manifest": [sys.executable, str(TOOLS / "contracts_manifest.py")],
    "vectors": [sys.executable, str(TOOLS / "vectors_check.py")],
    "freeze": [sys.executable, str(TOOLS / "freeze_check.py")],
}
ORDER = ["lint", "manifest", "vectors", "freeze"]


def main(argv: list[str]) -> int:
    sub = argv[0] if argv else "all"
    if sub not in (*STEPS, "all"):
        print(f"error: unknown contracts subcommand {sub!r} "
              f"(manifest|lint|vectors|freeze|all)", file=sys.stderr)
        return 2
    steps = ORDER if sub == "all" else [sub]
    rc = 0
    for s in steps:
        print(f"== contracts {s} ==")
        r = subprocess.run(STEPS[s], cwd=ROOT)
        rc = rc or r.returncode
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
