#!/usr/bin/env python3
"""tools/rtl_lint.py — RTL-safe (logical-properties-only) CSS gate (P7).

RTL law (UX req): layout must flip for right-to-left scripts, which CSS logical
properties (`inset-inline-start/end`, `margin-inline`, `padding-inline`,
`text-align: start/end`, `start`/`end`) give for free. Physical horizontal
properties hard-code an LTR direction and break RTL, so they are BANNED in
`ui/**/*.css`:

  left / right (as properties), margin-left/right, padding-left/right,
  border-left/right, inset-left/right, and text-align/clear/float: left|right.

`top`/`bottom` are vertical (not LTR/RTL-flipped) and are allowed. Fixtures
(tools/tests) prove one bad rule fails. Exit: 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"

RULES: list[tuple[str, re.Pattern]] = [
    ("left/right property", re.compile(r"(?m)^[ \t]*(left|right)[ \t]*:")),
    ("margin-left/right", re.compile(r"\bmargin-(left|right)\b")),
    ("padding-left/right", re.compile(r"\bpadding-(left|right)\b")),
    ("border-left/right", re.compile(r"\bborder-(left|right)\b")),
    ("inset-left/right", re.compile(r"\binset-(left|right)\b")),
    ("text-align left/right", re.compile(r"\btext-align[ \t]*:[ \t]*(left|right)\b")),
    ("clear left/right", re.compile(r"\bclear[ \t]*:[ \t]*(left|right)\b")),
    ("float left/right", re.compile(r"\bfloat[ \t]*:[ \t]*(left|right)\b")),
]


def check(repo: Path, ui_dir: Path) -> list[dict]:
    findings: list[dict] = []
    for f in sorted(ui_dir.rglob("*.css")):
        if "node_modules" in f.parts:
            continue
        rel = f"/ui/{f.relative_to(ui_dir).as_posix()}"
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            s = line.strip()
            if s.startswith("/*") or s == "":
                continue
            for name, pat in RULES:
                if pat.search(line):
                    findings.append({"path": rel, "line": i, "rule": name,
                                     "detail": s[:100]})
    return findings


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="rtl_lint", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--ui-dir", default=str(XR_CORE / "ui"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    ui_dir = Path(args.ui_dir)
    find = check(Path(args.repo).resolve(), ui_dir)
    if args.json:
        print(json.dumps({"tool": "rtl_lint", "count": len(find),
                          "violations": find}, sort_keys=True, indent=1))
    else:
        for f in find:
            print(f"FAIL {f['path']}:{f['line']}: [{f['rule']}] {f['detail']}")
        print(f"rtl_lint: {len(find)} violation(s) ({'PASS' if not find else 'FAIL'})")
    return EXIT_PASS if not find else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
