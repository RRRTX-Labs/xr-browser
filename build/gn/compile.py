"""build/gn/compile.py — `./scripts/build compile`: run ninja on a target.

Default target //xr:xr_all (the xr-core root group). Zero network by
construction. MOCK mode prints the MOCK banner; never pretends a build ran.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, mock_enabled, run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(prog="build/gn/compile.py",
                                     description="Run ninja on a target in a gn-generated out dir.")
    parser.add_argument("--checkout", required=True, help="checkout root (contains src/)")
    parser.add_argument("--out", default="out/xr_release", help="out dir relative to checkout")
    parser.add_argument("--target", default="//xr:xr_all", help="ninja target (default //xr:xr_all)")
    add_common_flags(parser)
    args = parser.parse_args()

    def run_compile() -> int:
        checkout = Path(args.checkout).resolve()
        out_dir = checkout / args.out
        if not (out_dir / "build.ninja").exists() and not mock_enabled():
            raise ToolError(f"{out_dir}/build.ninja missing; run ./scripts/build gen first")
        if mock_enabled():
            print(f"MOCK MODE — not a build: would run ninja -C {out_dir} {args.target}")
            return emit(args.json, {"tool": "compile", "mode": "mock", "target": args.target})
        run(["ninja", "-C", str(out_dir), args.target], cwd=checkout / "src")
        return emit(args.json, {"tool": "compile", "target": args.target, "out": str(out_dir)})

    main_with_guard(run_compile)


if __name__ == "__main__":
    main()
