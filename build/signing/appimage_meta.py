#!/usr/bin/env python3
"""build/signing/appimage_meta.py — AppImage embedded update-metadata
writer + reader (P10-T4). PURE DATA (no crypto, fully testable here):
appends a fixed-magic trailer to an AppImage-shaped file carrying the
update channel + version + digest the AppImageUpdate family reads; the
--check reader round-trips it byte-for-byte.

Trailer layout (documented, stable):
  [original bytes] XRUPDMETA1 <u32le len> <json bytes>
where json = canonical {channel, version, size, sha256 (of the ORIGINAL
bytes), signature: TEST-ONLY stub over the canonical json}.

Exit: 0 · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

MAGIC = b"XRUPDMETA1"


def canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def stub_sig(material: str, message: str) -> str:
    # the shared TEST-ONLY stub scheme (client fixture parity)
    return "sig:" + hashlib.sha256(
        (material + "|" + message).encode()).hexdigest()[:16]


def read_meta(path: Path) -> tuple[bytes, dict | None]:
    """Returns (original bytes, meta-or-None)."""
    raw = path.read_bytes()
    idx = raw.find(MAGIC)
    if idx < 0:
        return raw, None
    # take the LAST trailer (a re-write replaces the tail)
    idx = raw.rfind(MAGIC)
    (ln,) = struct.unpack_from("<I", raw, idx + len(MAGIC))
    blob = raw[idx + len(MAGIC) + 4: idx + len(MAGIC) + 4 + ln]
    meta = json.loads(blob.decode())
    original = raw[:idx]
    meta["_trailer_offset"] = idx
    return original, meta


def cmd_write(a: argparse.Namespace) -> int:
    src = Path(a.appimage)
    raw, existing = read_meta(src)
    if existing is not None:
        raw = raw[: existing["_trailer_offset"]]  # replace the trailer
    sha = hashlib.sha256(raw).hexdigest()
    meta = {"channel": a.channel, "sha256": sha, "signature": "",
            "size": len(raw), "version": a.version}
    meta["signature"] = stub_sig("SIGNING-PUB", canonical(meta))
    blob = canonical(meta).encode()
    with open(src, "ab") as fh:
        fh.write(MAGIC)
        fh.write(struct.pack("<I", len(blob)))
        fh.write(blob)
    print(f"PASS: update metadata embedded ({src.name}: {a.channel} "
          f"{a.version}, {len(raw)}B payload, stub-signed)")
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    src = Path(a.appimage)
    raw, meta = read_meta(src)
    if meta is None:
        print(f"FAIL: {src.name}: no XRUPDMETA1 trailer")
        return 1
    meta.pop("_trailer_offset")
    expect_sig = meta["signature"]
    probe = dict(meta)
    probe["signature"] = ""
    if stub_sig("SIGNING-PUB", canonical(probe)) != expect_sig:
        print(f"FAIL: {src.name}: metadata signature invalid")
        return 1
    if meta["sha256"] != hashlib.sha256(raw).hexdigest() or \
            meta["size"] != len(raw):
        print(f"FAIL: {src.name}: payload digest/size mismatch (the image "
              "was modified after embedding)")
        return 1
    print(f"PASS: appimage-meta round-trip ({src.name}: {meta['channel']} "
          f"{meta['version']}, digest ok, stub sig ok)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="appimage-meta",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--appimage", required=True)
    w.add_argument("--channel", required=True)
    w.add_argument("--version", required=True)
    w.add_argument("--json", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--appimage", required=True)
    c.add_argument("--json", action="store_true")
    a = ap.parse_args()
    return {"write": cmd_write, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
