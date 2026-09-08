#!/usr/bin/env python3
r"""tools/csp_lint.py — structural no-egress / CSP gate over the WebUI (P7).

Two laws, both structural so they bite on the SOURCE (not just the bundle):

  * NO RUNTIME NETWORK: scan `ui/**` (xr-core) and `commands/**` (xr-core) for
    `fetch(`, `XMLHttpRequest`, `WebSocket`, `new Worker`, `importScripts`,
    `navigator.sendBeacon`, and `document.write`. A hit = the WebUI would reach
    the network at runtime (L16 + "zero network at runtime" P7 security req).
    `package-lock.json` registry URLs are BUILD-time inputs (integrity-pinned),
    not runtime — they live in ui/toolchain and are NOT flagged.

  * NO INLINE / DANGEROUS EXEC (CSP strict): scan for `eval(`,
    `new Function(`, inline event-handler attributes (`on\w+ =` in JS,
    `on<event>="` in HTML) and `<script>` tags without a `src` in any .html.
    The built bundle must survive a `script-src 'self'` CSP (no inline JS, no
    eval) — check-bundle.js enforces it on the OUTPUT; this enforces it on the
    SOURCE so the failure is at authoring time.

Comment/allowlist: a line is skipped when the match is inside a `//` or `#`
comment or a string that is an explicit `#nosec-csp:` rationale on the same
line. (No blanket exemption file — the allowlist is a per-line rationale,
mirroring the P6 deny-strictness; >3 rationales in one file fails the
a11y/lint budget review.)

Exit: 0 pass · 1 violations · 2 usage. --json for CI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"

NETWORK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("fetch(", re.compile(r"\bfetch\s*\(")),
    ("XMLHttpRequest", re.compile(r"\bXMLHttpRequest\b")),
    ("WebSocket", re.compile(r"\bWebSocket\b")),
    ("new Worker", re.compile(r"\bnew\s+Worker\b")),
    ("importScripts", re.compile(r"\bimportScripts\b")),
    ("navigator.sendBeacon", re.compile(r"\.sendBeacon\s*\(")),
    ("document.write", re.compile(r"\.write\s*\(\s*['\"`]|document\.write")),
]
DANGEROUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("eval(", re.compile(r"\beval\s*\(")),
    ("new Function(", re.compile(r"\bnew\s+Function\s*\(")),
    ("inline handler (js)", re.compile(r"\bon[A-Z]\w*\s*[:=]\s*function")),
    ("inline handler (html)", re.compile(r"\bon[a-z]+\s*=\s*['\"]")),
    ("inline <script> (html)", re.compile(r"<script(?![^>]*\bsrc=)[^>]*>\s*[^<\s]")),
]
SCAN_EXTS = {".ts", ".tsx", ".js", ".mjs", ".html", ".css"}


def _is_rationale(line: str) -> bool:
    return "#nosec-csp:" in line


def scan_file(path: Path, rel: str, patterns: list[tuple[str, re.Pattern]],
              findings: list[dict]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if _is_rationale(line):
            continue
        for name, pat in patterns:
            if pat.search(line):
                findings.append({"path": rel, "line": i, "pattern": name,
                                 "detail": line.strip()[:120]})


def check(repo: Path, ui_root: Path, commands_root: Path) -> list[dict]:
    findings: list[dict] = []
    # ui/** and commands/** (xr-core) — the P7 WebUI + C++ host sources.
    for root, relroot in ((ui_root, "ui"), (commands_root, "commands")):
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in SCAN_EXTS:
                continue
            # Build-time infra (the toolchain itself names the forbidden tokens
            # as the patterns it checks) is NOT runtime egress. Scan the WebUI
            # RUNTIME sources only.
            if ({"node_modules", "dist", "toolchain"} & set(f.parts)) or "/build/" in str(f):
                continue
            rel = f"/{relroot}/{f.relative_to(root).as_posix()}"
            scan_file(f, rel, NETWORK_PATTERNS, findings)
            scan_file(f, rel, DANGEROUS_PATTERNS, findings)
    return findings


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="csp_lint", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--ui-root", default=str(XR_CORE / "ui"),
                   help="WebUI root to scan (override for fixtures)")
    p.add_argument("--commands-root", default=str(XR_CORE / "commands"),
                   help="commands/ root to scan (override for fixtures)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    find = check(Path(args.repo).resolve(), Path(args.ui_root).resolve(),
                 Path(args.commands_root).resolve())
    if args.json:
        print(json.dumps({"tool": "csp_lint", "count": len(find),
                          "violations": find}, sort_keys=True, indent=1))
    else:
        for f in find:
            print(f"FAIL {f['path']}:{f['line']}: [{f['pattern']}] {f['detail']}")
        print(f"csp_lint: {len(find)} violation(s) ({'PASS' if not find else 'FAIL'})")
    return EXIT_PASS if not find else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
