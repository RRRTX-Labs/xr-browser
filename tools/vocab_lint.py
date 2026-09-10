"""vocab_lint.py — banned-claims vocabulary lint (Plan P1-T12).

Enforces the plan's rhetoric rules (§0.3 "Rhetoric rules", §1.12-9
Honesty, §1.12-11 No intent claims, §9.11 Claims discipline) against
project copy: docs, release-note material, evidence, CI config, READMEs.

Machine-checked banned families (regexes, case-insensitive):

  anonymous          plan §0.3 / §1.12-9 / §9.11
  unbreakable        plan §0.3 / §1.12-9 / §9.11
  military-grade     plan §9.11 (inherited spec rhetoric)
  invisible          plan §9.11
  % protected        plan §9.11
  protection/security
  score(s)           plan §0.3 ("protection score") / §2.9 DROP / §9.11
  stealth            plan §9.11 ("stealth mode")

Human-enforced (NOT machine-checked — recorded here so nobody mistakes
the lint for full §9.11 coverage): the §1.12-11 no-intent-claims rule
("Guard and Observatory emit observations only"; copy review enforces,
e.g. "XR can see where an extension connects, not what it intends.").
Intent claims are a human copy-review gate at release time; this tool
says so in --json output instead of pretending a regex can catch prose.

Allowlist: docs/state/vocab-allowlist.yaml. The plan and its generated
derivatives *cite* banned words as prohibitions (the DROP row
"Security scores / % protected", the §9.11 list itself, §0.3's "XR never
says …"). Those citations are legitimate and are allowlisted with a
written justification per (path, line, pattern). An allowlist entry is
line-precise: it stops being valid if the line moves or its text changes
(enough to drop the match), so a future edit that *adds* a new banned
use is caught, not grandfathered.

Scanned scope (P1): *.md / *.yaml / *.json / *.txt under
.github/, ci/, docs/, evidence/ plus top-level *.md — i.e. everything a
user or auditor could read. tools/ (code) and .git/ are out of scope.

Exit codes: 0 = pass, 1 = banned hit without allowlist, 2 = usage.
--suggest prints allowlist-entry YAML for the current hits (to be
adopted WITH justifications).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import importlib.util as _ilu
import sys as _sys

# tools/_common.py is one of three `_common` modules in this tree
# (tools/_common.py, build/_common.py, build/qa/_common.py). A bare
# `from _common import ...` is order-dependent when tests import tools
# in-process: whichever `_common` landed in sys.modules first wins. Load our
# own sibling under an unambiguous name so the import never collides.
_TOOLS_COMMON = str(Path(__file__).resolve().parent / "_common.py")
_TC_SPEC = _ilu.spec_from_file_location("tools_common", _TOOLS_COMMON)
_TC = _ilu.module_from_spec(_TC_SPEC)
_sys.modules["tools_common"] = _TC
_TC_SPEC.loader.exec_module(_TC)

ToolError = _TC.ToolError
add_common_flags = _TC.add_common_flags
emit = _TC.emit
main_with_usage_guard = _TC.main_with_usage_guard

ALLOWLIST_FILE = "docs/state/vocab-allowlist.yaml"

# Banned families: (name, compiled regex). Case-insensitive.
BANNED: list[tuple[str, re.Pattern[str]]] = [
    ("anonymous", re.compile(r"\banonymous\b", re.IGNORECASE)),
    ("unbreakable", re.compile(r"\bunbreakable\b", re.IGNORECASE)),
    ("military-grade", re.compile(r"military[-\s]?grade", re.IGNORECASE)),
    ("invisible", re.compile(r"\binvisible\b", re.IGNORECASE)),
    ("% protected", re.compile(r"%\s*protected", re.IGNORECASE)),
    ("protection/security score", re.compile(r"(?:protection|security)[-\s]?scores?\b", re.IGNORECASE)),
    ("stealth", re.compile(r"\bstealth\b", re.IGNORECASE)),
]

SCAN_DIR_GLOBS = (".github", "ci", "docs", "evidence")
SCAN_EXTS = {".md", ".yaml", ".yml", ".json", ".txt"}
TOPLEVEL_MD = ("README.md", "SECURITY.md", "CONTRIBUTING.md")


def iter_scanned_files(root: Path) -> list[Path]:
    """Scanned files. The allowlist file itself is excluded: it is the
    lint's meta-record and must name the banned terms to enumerate them
    (same reason a spell-checker does not scan its own dictionary)."""
    skip = (root / ALLOWLIST_FILE).resolve()
    files: list[Path] = []
    for d in SCAN_DIR_GLOBS:
        base = root / d
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix in SCAN_EXTS and p.resolve() != skip:
                    files.append(p)
    for name in TOPLEVEL_MD:
        p = root / name
        if p.is_file():
            files.append(p)
    return files


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return (line_no, pattern_name, matched_text) hits."""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ToolError(f"cannot read {path}: {exc}")
    for i, line in enumerate(text.splitlines(), start=1):
        for name, rx in BANNED:
            for m in rx.finditer(line):
                hits.append((i, name, m.group(0)))
    return hits


def load_allowlist(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / ALLOWLIST_FILE
    fails: list[str] = []
    if not path.exists():
        raise ToolError(f"missing allowlist: {ALLOWLIST_FILE}")
    try:
        import yaml
    except ImportError as exc:
        raise ToolError(f"PyYAML not importable ({exc})") from exc
    with open(path, encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except Exception as exc:
            raise ToolError(f"YAML parse failure in {ALLOWLIST_FILE}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("allowlist"), list):
        raise ToolError(f"{ALLOWLIST_FILE}: expected mapping with an 'allowlist' list")
    for i, e in enumerate(data["allowlist"]):
        if not isinstance(e, dict):
            fails.append(f"allowlist[{i}]: not a mapping")
            continue
        for field in ("path", "line", "pattern", "justification"):
            if field not in e:
                fails.append(f"allowlist[{i}]: missing field {field!r}")
        if not (isinstance(e.get("justification"), str) and e["justification"].strip()):
            fails.append(f"allowlist[{i}]: justification must be a non-empty string")
    return data, fails


def run(args: argparse.Namespace) -> int:
    root = Path(args.repo or ".").resolve()
    fails: list[str] = []
    info: dict[str, Any] = {"tool": "vocab_lint"}

    allowlist_data, a_fails = load_allowlist(root)
    fails.extend(a_fails)
    allowed = {
        f"{e.get('path')}|{e.get('line')}|{e.get('pattern')}"
        for e in allowlist_data.get("allowlist", [])
        if isinstance(e, dict)
    } if not a_fails else set()

    if args.suggest:
        out_lines = ["# Suggested allowlist entries (add justifications; review each).", "allowlist:"]
        n = 0
        for f in iter_scanned_files(root):
            rel = str(f.relative_to(root))
            for line_no, name, _m in scan_file(f):
                out_lines.append(f"  - path: {rel}\n    line: {line_no}\n    pattern: {name}\n    justification: TODO")
                n += 1
        if n == 0:
            out_lines[-1:] = ["allowlist: []"]
        print("\n".join(out_lines))
        return 0

    total_hits = 0
    allowlisted = 0
    for f in iter_scanned_files(root):
        rel = str(f.relative_to(root))
        for line_no, name, matched in scan_file(f):
            total_hits += 1
            if f"{rel}|{line_no}|{name}" in allowed:
                allowlisted += 1
            else:
                fails.append(f"{rel}:{line_no}: banned pattern {name!r} ({matched!r}) — no allowlist entry")

    info.update(
        {
            "files_scanned": len(iter_scanned_files(root)),
            "total_hits": total_hits,
            "allowlisted_hits": allowlisted,
            "unallowlisted_hits": total_hits - allowlisted,
            "human_enforced_rules": [
                "§1.12-11 no-intent-claims (human copy review; not machine-checked)"
            ],
        }
    )
    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vocab_lint.py",
        description="Banned-claims vocabulary lint (plan §0.3 / §1.12-9 / §9.11).",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="print allowlist-entry YAML for current hits (adopt with justifications)",
    )
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
