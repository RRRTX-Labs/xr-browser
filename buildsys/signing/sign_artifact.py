"""buildsys/signing/sign_artifact.py — test-cert signing scaffold (P2-T8).

Abstract interface over per-OS signers, TEST-ONLY:
  linux  -> minisign signature + sha256sums.txt
  mac    -> codesign --options runtime (identity) [+ notarytool passthrough]
  win    -> signtool sign /a /fd SHA256 (passthrough)

Guard: it ERRORS if asked to sign a release-channel artifact — only
`dev` / `nightly-test` channels are accepted until real HSM certs land (P10).
Real keys do not exist in this repo (ADR-0004); the absence is honest, not a gap.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, mock_enabled  # noqa: E402

ALLOWED_CHANNELS = ("dev", "nightly-test")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_linux(artifact: Path, key: Path, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sig = out_dir / (artifact.name + ".minisig")
    r = subprocess.run(["minisign", "-S", "-s", str(key), "-m", str(artifact), "-x", str(sig)],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise ToolError(f"minisign failed: {r.stderr.strip()}")
    sums = out_dir / "sha256sums.txt"
    sums.write_text(f"{sha256_file(artifact)}  {artifact.name}\n", encoding="utf-8")
    return [str(sig), str(sums)]


def sign_mac(artifact: Path, identity: str) -> list[str]:
    r = subprocess.run(["codesign", "--options", "runtime", "--sign", identity, str(artifact)],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise ToolError(f"codesign failed: {r.stderr.strip()}")
    return [str(artifact)]  # notarytool submission is a documented follow-up (P10)


def sign_win(artifact: Path) -> list[str]:
    r = subprocess.run(["signtool", "sign", "/a", "/fd", "SHA256", str(artifact)],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise ToolError(f"signtool failed: {r.stderr.strip()}")
    return [str(artifact)]


def main() -> None:
    parser = argparse.ArgumentParser(prog="buildsys/signing/sign_artifact.py",
                                     description="TEST-ONLY artifact signing scaffold (real HSM certs land P10).")
    parser.add_argument("--artifact", required=True, help="artifact to sign")
    parser.add_argument("--channel", required=True, help="dev | nightly-test (release/stable refused until P10)")
    parser.add_argument("--os", required=True, choices=["linux", "mac", "win"])
    parser.add_argument("--key", help="minisign secret key (linux)")
    parser.add_argument("--identity", help="codesign identity (mac)")
    parser.add_argument("--out", default="out/sign", help="output dir (linux)")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        if args.channel not in ALLOWED_CHANNELS:
            raise ToolError(
                f"channel {args.channel!r} refused: only {ALLOWED_CHANNELS} are signable "
                "until real HSM certs land in P10 — a release-channel signature is impossible here"
            )
        artifact = Path(args.artifact)
        if mock_enabled():
            print(f"MOCK MODE — not a build: would sign {artifact} ({args.os}, {args.channel})")
            return emit(args.json, {"tool": "sign_artifact", "mode": "mock", "artifact": str(artifact),
                                    "channel": args.channel, "os": args.os})
        if not artifact.exists():
            raise ToolError(f"artifact not found: {artifact}")

        if args.os == "linux":
            if not args.key:
                raise ToolError("--key (minisign secret key) required for linux")
            outs = sign_linux(artifact, Path(args.key), Path(args.out))
        elif args.os == "mac":
            if not args.identity:
                raise ToolError("--identity required for mac codesign")
            outs = sign_mac(artifact, args.identity)
        else:
            outs = sign_win(artifact)
        return emit(args.json, {"tool": "sign_artifact", "artifact": str(artifact),
                                "channel": args.channel, "os": args.os, "outputs": outs})

    main_with_guard(run)


if __name__ == "__main__":
    main()
