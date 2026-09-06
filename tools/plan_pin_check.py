"""plan_pin_check.py — Master Plan integrity pin (Plan P1-T11).

The Master Plan is the single source of truth for this project. A single
byte of drift (silent edit, bad merge, re-wrap) is a deviation the
project must not carry silently, so the committed copy
docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md is pinned by SHA-256 in
docs/master-plan.sha256 and verified here on every CI run.

Checks:
  * docs/master-plan.sha256 exists and holds one 64-hex-digit digest,
  * docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md exists,
  * actual sha256 == pinned sha256,
  * optional --compare-against <path>: an independent copy (e.g. the
    original uploaded spec) must hash identically.

Amendments do NOT edit the pinned file: see docs/process/plan-amendment.md.
Exit codes: 0 = pass, 1 = fail, 2 = usage.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from _common import (
    PLAN_FILE,
    PLAN_SHA_FILE,
    ToolError,
    add_common_flags,
    emit,
    main_with_usage_guard,
    sha256_file,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def read_pin(root: Path) -> str:
    sha_file = root / PLAN_SHA_FILE
    if not sha_file.exists():
        raise ToolError(f"missing pin file: {PLAN_SHA_FILE}")
    lines = [ln.strip() for ln in sha_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) != 1:
        raise ToolError(f"{PLAN_SHA_FILE}: expected exactly one line, found {len(lines)}")
    pin = lines[0].split()[0]
    if not HEX64.match(pin):
        raise ToolError(f"{PLAN_SHA_FILE}: first token {pin!r} is not a 64-hex-digit sha256")
    return pin


def run(args: argparse.Namespace) -> int:
    # Pure file check — no git required (consistent with owners_sync).
    root = Path(args.repo or ".").resolve()
    fails: list[str] = []
    info: dict[str, Any] = {"tool": "plan_pin_check"}

    pinned = read_pin(root)
    info["pinned_sha256"] = pinned

    plan = root / PLAN_FILE
    if not plan.exists():
        fails.append(f"missing pinned plan file: {PLAN_FILE}")
        return emit(args.json, info, fail_messages=fails)

    actual = sha256_file(plan)
    info["actual_sha256"] = actual
    info["plan_bytes"] = plan.stat().st_size
    if actual != pinned:
        fails.append(
            f"plan pin mismatch: {PLAN_FILE} hashes {actual} but {PLAN_SHA_FILE} pins {pinned} "
            "(plan is pinned; see docs/process/plan-amendment.md)"
        )

    if args.compare_against:
        other = Path(args.compare_against)
        if not other.exists():
            fails.append(f"--compare-against path does not exist: {other}")
        else:
            other_sha = sha256_file(other)
            info[f"compare_{other.name}"] = other_sha
            if other_sha != actual:
                fails.append(f"comparison copy {other} hashes {other_sha} != pinned {pinned}")

    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="plan_pin_check.py",
        description="Verify the committed Master Plan matches its SHA-256 pin.",
    )
    parser.add_argument(
        "--compare-against",
        default=None,
        help="optional independent copy of the plan that must hash identically",
    )
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
