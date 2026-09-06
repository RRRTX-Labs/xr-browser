"""license_audit.py — license gate (Plan P1-T13; Plan §13, P1 "Tests").

Two checks, honestly scoped (L5 — no overclaiming):

1. **Canonical MPL-2.0 check.** `LICENSE` must byte-for-byte be the
   verbatim MPL-2.0 text (sha256 below). Source of the known-good
   copy: brave/adblock-rust LICENSE, fetched and verified 2026-09-07
   (mozilla.org/hg.mozilla.org/spdx.org were unusable live sources at
   the time — see docs/state/research-log-P1.md).

2. **Copyleft marker scan.** Walks the repo for GPL/AGPL/SSPL marker
   strings.
   * A marker in a *code/vendored* path (source extensions, or
     third_party/, vendor/, patches/) is a **failure** (Plan §1.12-4:
     "no GPL/AGPL code linked into any shipped binary"; ADR-0001:
     "GPL tools are separate processes or absent").
   * A marker in a *doc/data* path is legitimate only if the path is
     allowlisted in docs/state/license-allowlist.yaml (path-level,
     with a written justification — unlike vocab_lint's line-precise
     entries: dependency evals and ADRs are refreshed over time, so the
     review unit is the file, and the justification must say why the
     file cites copyleft terms).

This is a header/inventory-level audit. Full dependency-graph license
resolution and advisory scanning are P9-T9 (threat model T11 states
this explicitly); this tool does not pretend otherwise.

Scan exclusions (each documented, each minimal):
  * the allowlist file (names the markers it audits),
  * this tool's own source (defines the marker regexes),
  * tools/tests/fixtures/ (intentional negative corpus — see its README),
  * LICENSE, when check 1 proved it byte-for-byte canonical (the
    standard MPL-2.0 text itself names example licenses at line 69).

Exit codes: 0 = pass, 1 = fail, 2 = usage.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from _common import ToolError, add_common_flags, emit, main_with_usage_guard, sha256_file

LICENSE_FILE = "LICENSE"
ALLOWLIST_FILE = "docs/state/license-allowlist.yaml"

# Verbatim MPL-2.0 text (16,726 B). Known-good source: brave/adblock-rust
# LICENSE, fetched 2026-09-07 (primary mozilla sources unusable at the time).
CANONICAL_MPL20_SHA256 = "3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04"

# Copyleft markers: (name, compiled regex). Case-insensitive.
MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("GNU General Public License text", re.compile(r"GNU GENERAL PUBLIC LICENSE", re.IGNORECASE)),
    ("AGPL", re.compile(r"\bAGPL\b|GNU Affero", re.IGNORECASE)),
    ("GPL-2.0", re.compile(r"GPL-?2\.0(?:-(?:only|or-later))?", re.IGNORECASE)),
    ("GPL-3.0", re.compile(r"GPL-?3\.0(?:-(?:only|or-later))?", re.IGNORECASE)),
    ("GPLv2", re.compile(r"\bGPLv2\b", re.IGNORECASE)),
    ("GPLv3", re.compile(r"\bGPLv3\b", re.IGNORECASE)),
    ("SSPL", re.compile(r"\bSSPL\b")),
]

CODE_EXTS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".py", ".rs", ".go",
    ".gn", ".gni", ".java", ".kt", ".ts", ".js", ".m", ".mm", ".swift", ".sh",
}
CODE_DIRS = {"third_party", "vendor", "patches"}
SKIP_DIRS = {".git"}


def is_code_path(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in CODE_DIRS or any(p in CODE_DIRS for p in parts):
        return True
    return Path(rel).suffix in CODE_EXTS


def iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        out.append(p)
    return out


def load_allowlist(root: Path) -> tuple[set[str], list[str]]:
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
    allowed: set[str] = set()
    for i, e in enumerate(data["allowlist"]):
        if not isinstance(e, dict) or not (isinstance(e.get("path"), str) and e["path"].strip()):
            fails.append(f"license allowlist[{i}]: missing 'path'")
            continue
        if not (isinstance(e.get("justification"), str) and e["justification"].strip()):
            fails.append(f"license allowlist[{i}]: justification must be a non-empty string")
        allowed.add(e["path"].strip())
    return allowed, fails


def run(args: argparse.Namespace) -> int:
    root = Path(args.repo or ".").resolve()
    fails: list[str] = []
    info: dict[str, Any] = {"tool": "license_audit"}

    # 1. Canonical MPL-2.0.
    lic = root / LICENSE_FILE
    if not lic.exists():
        fails.append(f"missing {LICENSE_FILE}")
        info["license_check"] = "missing"
    else:
        actual = sha256_file(lic)
        info["license_sha256"] = actual
        if actual != CANONICAL_MPL20_SHA256:
            fails.append(
                f"{LICENSE_FILE} hashes {actual} != canonical MPL-2.0 {CANONICAL_MPL20_SHA256} "
                "(byte-for-byte verbatim required)"
            )
            info["license_check"] = "mismatch"
        else:
            info["license_check"] = "canonical"

    # 2. Copyleft marker scan.
    allowed, a_fails = load_allowlist(root)
    fails.extend(a_fails)

    code_hits: list[str] = []
    doc_hits: list[str] = []
    scanned = 0
    license_ok = info.get("license_check") == "canonical"
    self_rel = "tools/license_audit.py"
    for f in iter_files(root):
        rel = str(f.relative_to(root))
        if f.resolve() == (root / ALLOWLIST_FILE).resolve():
            continue  # meta-record: names the markers it audits (documented)
        if rel == self_rel:
            continue  # the linter's own source defines the marker regexes;
            # scanning it would be self-noise (S0-reviewed tool, not
            # vendored code). Every OTHER file, incl. all of tools/, is
            # still scanned.
        if rel.startswith("tools/tests/fixtures/"):
            continue  # intentional negative test corpus (see its README):
            # a scanner does not scan the samples it is proven against.
        if rel == LICENSE_FILE and license_ok:
            continue  # canonical MPL-2.0 verified byte-for-byte in check 1;
            # the standard text itself names example licenses (line 69:
            # "…GNU Affero General…") — scanning it would be self-noise.
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary: no text markers possible
        scanned += 1
        for i, line in enumerate(text.splitlines(), start=1):
            for name, rx in MARKERS:
                if rx.search(line):
                    entry = f"{rel}:{i}: {name}"
                    (code_hits if is_code_path(rel) else doc_hits).append(entry)

    info["files_scanned"] = scanned
    info["code_hits"] = len(code_hits)
    info["doc_hits_total"] = len(doc_hits)
    info["doc_hits_allowlisted"] = sum(1 for h in doc_hits if h.split(":")[0] in allowed)

    fails.extend(code_hits)  # every code hit fails, unconditionally
    for h in doc_hits:
        if h.split(":")[0] not in allowed:
            fails.append(f"{h} — doc hit without path allowlist entry")

    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="license_audit.py",
        description="MPL-2.0 canonical check + copyleft marker scan (header/inventory level).",
    )
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
