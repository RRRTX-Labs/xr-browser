"""build/toolchain/provenance.py — record + verify toolchain digests (R0).

--verify: validate pins.json against the pinned tree (schema + every digest is
  a 64-hex sha256 sourced from build/linux/sysroot_scripts/sysroots.json; the
  clang linux-artifact sha256 may be PENDING-CAPTURE until an L2+ checkout).
--record: on a synced checkout (L2+), fetch the actual clang tarball and the
  amd64 sysroot tarball, compute their sha256, and write them into pins.json
  (replacing PENDING-CAPTURE). Digests are recorded from fetched artifacts —
  never typed (Plan P2-T5 / R0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256_url(url: str) -> str:
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (pinned https URL)
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(pins: dict) -> list[str]:
    fails: list[str] = []
    if pins.get("schema_version") != 1:
        fails.append("pins.json: schema_version must be 1")
    clang = pins.get("clang")
    if not isinstance(clang, dict) or not clang.get("version"):
        fails.append("pins.json: clang.version required")
    sha = clang.get("linux_artifact_sha256") if isinstance(clang, dict) else None
    if sha and sha != "PENDING-CAPTURE" and not HEX64.match(str(sha)):
        fails.append(f"pins.json: clang.linux_artifact_sha256 not a 64-hex sha256: {sha!r}")
    roots = pins.get("sysroot")
    if not isinstance(roots, list) or not roots:
        fails.append("pins.json: sysroot list required")
    else:
        for e in roots:
            if not HEX64.match(str(e.get("sha256", ""))):
                fails.append(f"pins.json: sysroot entry {e.get('arch')!r} sha256 not 64-hex")
    if not isinstance(pins.get("mac"), dict) or not pins["mac"].get("sdk_version"):
        fails.append("pins.json: mac.sdk_version required")
    if not isinstance(pins.get("win"), dict) or not pins["win"].get("sdk"):
        fails.append("pins.json: win.sdk required")
    return fails


def main() -> None:
    parser = argparse.ArgumentParser(prog="build/toolchain/provenance.py",
                                     description="Record/verify toolchain digests (R0 provenance).")
    parser.add_argument("--verify", action="store_true", help="validate pins.json (schema + digests)")
    parser.add_argument("--record", action="store_true", help="fetch artifacts and record digests into pins.json (L2+ checkout)")
    parser.add_argument("--pins", default="build/toolchain/pins.json", help="pins.json path (repo-relative)")
    add_common_flags(parser)
    args = parser.parse_args()
    if args.verify == args.record:
        parser.error("exactly one of --verify / --record required")

    def run() -> int:
        root = repo_root()
        path = root / args.pins
        pins = json.loads(path.read_text(encoding="utf-8"))

        if args.verify:
            fails = verify(pins)
            pending = pins["clang"].get("linux_artifact_sha256") == "PENDING-CAPTURE"
            result = {"tool": "provenance", "mode": "verify", "pin": pins.get("chromium_rev"),
                      "sysroot_digests": len(pins.get("sysroot", [])),
                      "clang_sha256_pending_capture": pending}
            return emit(args.json, result, failures=fails)

        # --record: fetch the real artifacts (network is expected HERE — this
        # is the one build-system tool that fetches, and only on demand).
        clang_url = pins["clang"]["linux_artifact_url"]
        clang_sha = sha256_url(clang_url)
        amd64 = next(e for e in pins["sysroot"] if e["arch"] == "amd64")
        # Content-addressed per install-sysroot.py: url = URL + '/' + Sha256Sum
        sysroot_url = pins["sysroot_url_base"] + "/" + amd64["sha256"]
        sysroot_sha = sha256_url(sysroot_url)
        if sysroot_sha != amd64["sha256"]:
            return emit(args.json, {"tool": "provenance", "mode": "record"},
                        failures=[f"amd64 sysroot sha256 mismatch: fetched {sysroot_sha} != pinned {amd64['sha256']}"])
        pins["clang"]["linux_artifact_sha256"] = clang_sha
        pins["clang"]["capture_cmd"] = f"sha256sum <(curl -L {clang_url})"
        path.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
        return emit(args.json, {"tool": "provenance", "mode": "record",
                                "clang_linux_sha256": clang_sha,
                                "sysroot_amd64_verified": True})

    main_with_guard(run)


if __name__ == "__main__":
    main()
