"""build/branding/gen_version.py — version string builder (P2-T6).

Builds the XR version string: milestone + build + channel. Embeds XR_CHANNEL
(dev|beta|stable) and the per-channel update endpoint. Endpoint URLs are RFC
2606 placeholders (`https://update.xr.example/`) — PENDING-OPS: replaced by the
real update-server host at P10 deploy.

Determinism: any date emitted honors SOURCE_DATE_EPOCH (default fixed epoch,
never `now()`). No timestamps leak into build metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root  # noqa: E402

CHANNELS = ("dev", "beta", "stable")
# RFC 2606 placeholders — PENDING-OPS (real host lands at P10 deploy).
UPDATE_URLS = {c: "https://update.xr.example/" for c in CHANNELS}
DEFAULT_EPOCH = 0  # SOURCE_DATE_EPOCH honored; default fixed


def build_version(milestone: str, build: str, channel: str) -> dict:
    if channel not in CHANNELS:
        raise ToolError(f"channel must be one of {CHANNELS} (got {channel!r})")
    epoch = os.environ.get("SOURCE_DATE_EPOCH", str(DEFAULT_EPOCH))
    return {
        "version": f"{milestone}.{build}",
        "full": f"{milestone}.{build}",
        "channel": channel,
        "milestone": milestone,
        "build": build,
        "update_url": UPDATE_URLS[channel],
        "source_date_epoch": int(epoch),
        "pending_ops": "update_url is an RFC 2606 placeholder until P10",
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="build/branding/gen_version.py",
                                     description="Build the XR version string (milestone+build+channel).")
    parser.add_argument("--milestone", default=None, help="e.g. 152 (default: DEPS chromium_milestone)")
    parser.add_argument("--build", default=None, help="e.g. 0.7977.82 (default: DEPS chromium_version minus milestone)")
    parser.add_argument("--channel", default=None, help="dev|beta|stable (default: env XR_CHANNEL, else dev)")
    parser.add_argument("--out", help="write version.json to this path")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        root = repo_root()
        channel = args.channel or os.environ.get("XR_CHANNEL") or "dev"
        if args.milestone and args.build:
            milestone, build = args.milestone, args.build
        else:
            from _common import load_deps
            deps = load_deps(root)
            milestone = str(deps.get("chromium_milestone", ""))
            ver = str(deps.get("chromium_version", ""))
            build = ver[len(milestone) + 1:] if ver.startswith(milestone + ".") else ver
        v = build_version(milestone, build, channel)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
        return emit(args.json, {"tool": "gen_version", **v})

    main_with_guard(run)


if __name__ == "__main__":
    main()
