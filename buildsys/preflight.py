"""buildsys/preflight.py — `./build preflight`: refuse under-provisioned hosts.

Records nproc/RAM/disk and refuses sync/gen when free disk < 2x the estimated
checkout+out size. Perf row: doc estimates vs actuals (evidence/P2).

Exit 0 = adequate (with probe recorded), 1 = refused, 2 = usage.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root

DEFAULT_ESTIMATE_GB = 120.0  # Chromium checkout + toolchain + out/ at current train size


def probe() -> dict:
    info: dict = {}
    info["nproc"] = os.cpu_count() or 1
    try:
        info["ram_total_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 2)
    except (ValueError, OSError):
        info["ram_total_gb"] = None
    total, used, free = shutil.disk_usage("/")
    info["disk"] = {"total_gb": round(total / 1e9, 2), "used_gb": round(used / 1e9, 2),
                    "free_gb": round(free / 1e9, 2)}
    info["at"] = datetime.now(timezone.utc).isoformat()
    return info


def check_disk(checkout: Path, estimate_gb: float) -> tuple[bool, str]:
    info = probe()
    free = info["disk"]["free_gb"]
    need = estimate_gb * 2.0
    if free < need:
        return False, (
            f"preflight REFUSED: free disk {free:.1f} GB < 2x estimate ({need:.1f} GB) "
            f"for checkout at {checkout}. Refusing rather than simulating checkout state."
        )
    return True, f"preflight OK: free disk {free:.1f} GB >= {need:.1f} GB"


def main() -> None:
    parser = argparse.ArgumentParser(prog="buildsys/preflight.py",
                                     description="Host capacity probe; refuses under-provisioned hosts.")
    parser.add_argument("--checkout", help="intended checkout dir (for the refusal message)")
    parser.add_argument("--estimate-gb", type=float, default=DEFAULT_ESTIMATE_GB,
                        help="estimated checkout+out size in GB (default: 120)")
    parser.add_argument("--write", help="also write probe JSON to this path")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        checkout = Path(args.checkout).resolve() if args.checkout else repo_root() / "chromium"
        info = probe()
        ok, msg = check_disk(checkout, args.estimate_gb)
        result = {"tool": "preflight", "probe": info, "message": msg}
        if args.write:
            Path(args.write).parent.mkdir(parents=True, exist_ok=True)
            Path(args.write).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return emit(args.json, result, failures=[] if ok else [msg])

    main_with_guard(run)


if __name__ == "__main__":
    main()
