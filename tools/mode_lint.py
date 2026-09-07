#!/usr/bin/env python3
"""tools/mode_lint.py — the L3 "one brain" static gate (Plan §4 P6, Manual row).

L3: "one policy resolver; unknown/absent policy => deny, never guess." This
lint bans subsystem-private mode/trust logic OUTSIDE the resolver: any code
reading trust-context / dial-position / trust-tier tokens to make its own
decisions is a second brain and fails the build, citing file:line.

What it enforces
  1. MODE-LOGIC BAN: files under the scanned xr-core tree, outside the
     exemption baseline (xr-core/policy/mode_lint.cfg), may not reference
     resolver-input patterns: TrustContext/trust_context, tier tokens
     (kStandard/kShield/kFortress), dial positions, or tier-ladder helpers.
     This is the static equivalent of the plan's Manual row ("grep for rogue
     mode checks fails the build").
  2. INTENT HEADERS (L13): every C++ file under policy/ must carry an
     `// Intent:` one-liner in its header block — S0 review anchor.

Enforcement bites from P7 adoption (plan: mode_lint "introduced with P7/P8
adoption"); the P6 baseline is green and CI-wired today. Exemptions live in
xr-core/policy/mode_lint.cfg with rationales (S0 review surface).

This gate must never be weakened to pass (P6 stop-condition #6): if it
fires, fix the code or argue the exemption in review — not the lint.

Stdlib only. Exit: 0 pass · 1 violations · 2 usage. --json for CI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

DEFAULT_XR_CORE = "../xr-core"
SCAN_EXTENSIONS = {".cc", ".h", ".py", ".mojom", ".gn"}
INTENT_EXTENSIONS = {".cc", ".h"}

# Resolver-input patterns (the decision INPUTS — consuming an EffectivePolicy
# OUTPUT is fine and NOT listed). Word-ish boundaries to avoid identifier
# false positives; `dial` as a whole word (dialect etc. must not match).
MODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("TrustContext", re.compile(r"\bTrustContext\b")),
    ("trust_context", re.compile(r"\btrust_context\b")),
    ("tier kStandard", re.compile(r"\bkStandard\b")),
    ("tier kShield", re.compile(r"\bkShield\b")),
    ("tier kFortress", re.compile(r"\bkFortress\b")),
    ("dial position", re.compile(r"\bdial\b(?![a-z_])")),
    ("trust tier ladder", re.compile(r"\bTrustTierIndex\b|\btrust_floor\b")),
    ("resolver bypass (direct tier compare)", re.compile(r"\btrust_tier\b|\bmode_check\b")),
]

INTENT_RE = re.compile(r"^\s*//\s*Intent:", re.MULTILINE)


def parse_config(path: Path) -> list[str]:
    """Returns exempted path prefixes (repo-root-relative, e.g. /policy/)."""
    prefixes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("exempt:"):
            prefixes.append(line[len("exempt:"):].strip())
    return prefixes


def is_exempt(rel_posix: str, prefixes: list[str]) -> bool:
    return any(rel_posix.startswith(p) for p in prefixes)


def scan_file(path: Path, rel_posix: str, prefixes: list[str],
              findings: list[dict[str, Any]]) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:  # unreadable: report, never skip silently
        findings.append({"kind": "unreadable", "path": rel_posix, "line": 0,
                         "detail": str(e), "pattern": None})
        return
    exempt = is_exempt(rel_posix, prefixes)
    lines = text.splitlines()
    if not exempt:
        for lineno, line in enumerate(lines, start=1):
            # Skip comment-only lines: the ban is on decision LOGIC; prose
            # mentioning tiers in comments is documentation, not a second
            # brain. (String literals still count — data driving decisions.)
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("#"):
                continue
            for name, pat in MODE_PATTERNS:
                if pat.search(line):
                    findings.append({
                        "kind": "mode-logic", "path": rel_posix, "line": lineno,
                        "detail": f"{name}: {stripped[:120]}", "pattern": name,
                    })
    # Intent headers apply to policy/ C++ files regardless of exemptions
    # (the exemption is about mode tokens; the header law is L13 for all
    # S0 policy files — tests included).
    if rel_posix.startswith("/policy/") and path.suffix in INTENT_EXTENSIONS:
        if not INTENT_RE.search(text[:4000]):
            findings.append({"kind": "missing-intent-header", "path": rel_posix,
                             "line": 1, "detail": "no '// Intent:' line in header (L13)",
                             "pattern": None})


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mode_lint", description=__doc__.split("\n")[0])
    p.add_argument("--root", default=DEFAULT_XR_CORE,
                   help="xr-core tree to scan (default: ../xr-core)")
    p.add_argument("--config", default=None,
                   help="mode_lint.cfg path (default: <root>/policy/mode_lint.cfg)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: scan root not found: {root}", file=sys.stderr)
        return EXIT_USAGE
    cfg = Path(args.config).resolve() if args.config else root / "policy" / "mode_lint.cfg"
    if not cfg.is_file():
        print(f"error: config not found: {cfg}", file=sys.stderr)
        return EXIT_USAGE
    prefixes = parse_config(cfg)

    findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
            continue
        rel = "/" + path.relative_to(root).as_posix()
        if "/__pycache__/" in rel or "/build/" in rel or "/.git/" in rel:
            continue
        scan_file(path, rel, prefixes, findings)

    if args.json:
        print(json.dumps({
            "root": str(root), "config": str(cfg),
            "exemptions": prefixes, "scanned_patterns": [n for n, _ in MODE_PATTERNS],
            "violations": findings, "count": len(findings),
        }, sort_keys=True, indent=1))
    else:
        for f in findings:
            print(f"FAIL {f['path']}:{f['line']}: [{f['kind']}] {f['detail']}")
        print(f"mode_lint: {len(findings)} violation(s)"
              f" ({'PASS' if not findings else 'FAIL'})")
    return EXIT_PASS if not findings else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
