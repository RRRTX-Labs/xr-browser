"""buildsys/branding/brand_check.py — post-build brand verifier + endpoint scan.

Two honest, scoped checks (the browser-process scan proper is P16):

1. `--binary PATH`: extract ASCII strings from a produced binary and assert
   (a) no "Google Chrome" branding string, (b) XR marks present. Fixture mode
   (`--fixture DIR`) writes synthetic ELF/PE/Mach-O-shaped files so the check
   is exercised without a real build (L1).

2. `--scan`: endpoint-deny scan over THIS repo's build surface only
   (buildsys/, ci/, DEPS, .github/workflows) — NOT docs/ (which legitimately
   quote endpoint strings in the threat model / limitations; P16 covers the
   browser). `tests/` dirs and `__pycache__` are skipped: negative fixtures
   legitimately contain deny-strings (same convention as the governance
   negative corpus). The deny list is the endpoint-shaped regex set below,
   compiled from escaped fragments so the tool's own source does not trip it.

Zero network. Exit 0 = clean, 1 = hit.
"""

from __future__ import annotations

import argparse
import re
import string
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root  # noqa: E402

DENY_ENDPOINTS = [
    re.compile(r"update\.googleapis\.com"),
    re.compile(r"[a-z0-9.-]+\.gvt1\.com"),
    re.compile(r"update\.chromium\.org"),
    re.compile(r"dl\.google\.com"),
    re.compile(r"clients[0-9]*\.google\.com"),
]
BAD_BRAND = ["google chrome", "Google Chrome"]
GOOD_BRAND = ["XR Browser"]
SCAN_DIRS = ["buildsys", "ci", "DEPS", ".github/workflows"]
PRINTABLE = set(bytes(string.printable, "ascii"))


def extract_strings(data: bytes, minlen: int = 5) -> list[str]:
    out: list[str] = []
    cur = bytearray()
    for b in data:
        if b in PRINTABLE:
            cur.append(b)
        else:
            if len(cur) >= minlen:
                out.append(cur.decode("ascii", "replace"))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append(cur.decode("ascii", "replace"))
    return out


def check_binary(path: Path) -> tuple[list[str], list[str]]:
    data = path.read_bytes()
    strs = extract_strings(data)
    blob = "\n".join(strs)
    bad = [p for p in BAD_BRAND if p in blob]
    missing = [g for g in GOOD_BRAND if g not in blob]
    return bad, missing


def scan_repo(root: Path) -> list[str]:
    hits: list[str] = []
    for rel in SCAN_DIRS:
        p = root / rel
        if p.is_file():
            candidates = [p]
        elif p.is_dir():
            candidates = [
                f for f in p.rglob("*")
                if f.is_file()
                and ".git" not in f.parts
                and "__pycache__" not in f.parts
                and "tests" not in f.parts
            ]
        else:
            continue
        for f in candidates:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pat in DENY_ENDPOINTS:
                    m = pat.search(line)
                    if m:
                        hits.append(f"{f.relative_to(root)}:{lineno}: {m.group(0)}")
    return hits


def write_fixture(d: Path) -> dict[str, str]:
    d.mkdir(parents=True, exist_ok=True)
    files = {
        "good.elf": b"\x7fELF" + b"\x00" * 32 + b"XR Browser\0" + b"\x00" * 16,
        "bad.elf": b"\x7fELF" + b"\x00" * 32 + b"Google Chrome\0" + b"\x00" * 16,
        "good.macho": b"\xcf\xfa\xed\xfe" + b"\x00" * 32 + b"XR Browser\0",
        "good.pe": b"MZ" + b"\x00" * 64 + b"XR Browser\0",
    }
    for name, data in files.items():
        (d / name).write_bytes(data)
    return {name: str(d / name) for name in files}


def main() -> None:
    parser = argparse.ArgumentParser(prog="buildsys/branding/brand_check.py",
                                     description="Verify de-branding on produced binaries; endpoint-deny scan.")
    parser.add_argument("--binary", help="path to a produced binary")
    parser.add_argument("--scan", action="store_true", help="endpoint-deny scan over the repo build surface")
    parser.add_argument("--fixture", help="write synthetic ELF/PE/Mach-O fixtures to this dir (then re-run with --binary)")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        if args.fixture:
            wrote = write_fixture(Path(args.fixture))
            return emit(args.json, {"tool": "brand_check", "mode": "fixture-write", "files": wrote})

        failures: list[str] = []
        if args.binary:
            bad, missing = check_binary(Path(args.binary))
            if bad:
                failures.append(f"branding leak in {args.binary}: {bad}")
            if missing:
                failures.append(f"XR marks missing in {args.binary}: {missing}")
            return emit(args.json, {"tool": "brand_check", "mode": "binary", "binary": args.binary,
                                    "bad_brand": bad, "missing_marks": missing}, failures=failures)

        if args.scan:
            hits = scan_repo(repo_root())
            return emit(args.json, {"tool": "brand_check", "mode": "scan", "hits": hits},
                        failures=[f"endpoint deny-hit: {h}" for h in hits])

        parser.error("one of --binary / --scan / --fixture is required")

    main_with_guard(run)


if __name__ == "__main__":
    main()
