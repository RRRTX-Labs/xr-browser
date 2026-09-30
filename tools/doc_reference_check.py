#!/usr/bin/env python3
"""tools/doc_reference_check.py — a cited path must exist (P13-C-P0.5b).

Why this exists. A `NOT-RUN (method: <path>)` row is the honest way to say "this
was not measured, and here is how it would be" — but a method whose path dangles
is not a method. It is a claim with a decorative citation, and it is
*unfalsifiable*: the reader cannot run the method, cannot see the instrument,
and cannot tell a deliberate deferral from a typo or a wish. `evidence/P13/
human-gates.md` cited `docs/panel/breakage-report.md` twice before this file
existed (verified: `ls docs/panel` → no such directory), which is how the class
was found.

The law: **every `docs/…`, `evidence/…`, `build/…` path cited in an evidence
bundle, a `human-gates.md`, or a `report.md` must exist in the tree.** The scan
is deliberately literal: no prefix fallback, no "close enough". A citation that
names a directory must resolve to a directory; brace citations
(`evidence/P13/{evidence.json,report.md,…}`) are expanded and each member is
checked, because that shorthand is exactly how a bundle lists the four things it
claims to be complete — and one of them was missing when this was written.

Scope: the law binds from P13 — the phase that introduces it. Older bundles cite
prose shapes (`docs/plans/..._v2.md`, `docs/adr/0001`, `evidence/P`) that were
never literal paths, and prior-phase evidence is append-only besides: silently
rewriting P1's citations to satisfy a checker written four phases later would be
a worse act than leaving them. So pre-law bundles are grandfathered exactly the
way `evidence_finality.FINALITY_MIN_PHASE` grandfathers them, and the count of
what was skipped is printed rather than hidden.

What it does NOT scan: prose in `docs/**` (a doc may cite a future file on
purpose, and the reader is a human with the path in front of them), and `tools/`
paths (a tool citation is normally an instruction to run something, already
covered by the tool's own gate). Named here so the boundary is a decision rather
than an oversight.

Modes: `--repo <dir>` (default `.`), `--json`, `--check` (default behaviour;
the flag exists so a caller can be explicit). Exit 0 clean, 1 findings, 2 usage.
Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Path-ish tokens rooted at the three trees this law covers. The `{...}` group
# is part of the token so brace citations survive extraction.
CITE_RE = re.compile(r"(?<![\w/.-])((?:docs|evidence|build)/(?:[A-Za-z0-9_.@{},+~-]+/?)+)")
# Trailing punctuation that belongs to the sentence, not the path.
TRIM = ".,;:!?)]}'\"»”"

# The phase that introduces this law; earlier bundles are grandfathered.
REFERENCE_MIN_PHASE = 13
PHASE_DIR_RE = re.compile(r"^P(\d{1,3})(?:-CLOSE)?$")


def _phase_of(path: Path) -> int | None:
    for part in path.parts:
        m = PHASE_DIR_RE.fullmatch(part)
        if m:
            return int(m.group(1))
    return None


# Bundles, human gates and reports. A bundle's rows carry most citations
# (evidence: [...], and prose in dod/source), so the whole JSON is scanned as
# text — simple, and it cannot miss a key it did not think of.
TARGETS = ("evidence/*/evidence.json", "evidence/*/human-gates.md",
           "evidence/*/report.md", "evidence/*/*/human-gates.md",
           "evidence/*/*/report.md")


def _expand(token: str) -> list[str]:
    """`a/{x,y}/z` -> ['a/x/z', 'a/y/z']; a plain path -> [itself]."""
    m = re.search(r"\{([^{}]*)\}", token)
    if not m:
        return [token]
    out: list[str] = []
    for part in m.group(1).split(","):
        out.extend(_expand(token[:m.start()] + part.strip() + token[m.end():]))
    return out


def citations(text: str) -> list[str]:
    """Every cited path in `text`, brace-expanded, punctuation-trimmed."""
    found: list[str] = []
    for m in CITE_RE.finditer(text):
        token = m.group(1).strip()
        # A citation broken across a line (`evidence/P12/\nreport.md` in a
        # wrapped markdown line) is not something to guess at: the token simply
        # ends there, and it will be reported if the truncated path is missing.
        for path in _expand(token):
            # Trailing punctuation belongs to the sentence, not the path — and
            # it is trimmed AFTER brace expansion, because `{a,b,c}` ends in a
            # brace that is part of the citation.
            path = path.rstrip(TRIM)
            # An ellipsis is prose (`docs/plans/..._v2.md`), not a citation, and
            # an unterminated brace means the extractor caught the middle of a
            # sentence — neither is a claim about a file that exists.
            if not path or path in found or "..." in path:
                continue
            if path.count("{") != path.count("}"):
                continue
            found.append(path)
    return found


def check(repo: Path, patterns=TARGETS,
          min_phase: int = REFERENCE_MIN_PHASE) -> tuple[list[dict], int, int]:
    """Findings for every citation that does not resolve.

    Returns (findings, files_scanned, files_grandfathered). A file whose phase is
    below `min_phase`, or whose phase cannot be read at all, is skipped — and
    COUNTED, because a scoping rule that hides its own scope is how a selective
    gate becomes a decorative one.
    """
    findings: list[dict] = []
    all_files = sorted({p for pat in patterns for p in repo.glob(pat)})
    files, skipped = [], 0
    for f in all_files:
        n = _phase_of(f.relative_to(repo))
        if n is None or n < min_phase:
            skipped += 1
        else:
            files.append(f)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover
            findings.append({"file": str(f.relative_to(repo)), "path": "-",
                             "why": f"unreadable: {exc}"})
            continue
        for path in citations(text):
            target = repo / path
            if target.is_dir():
                continue
            if target.is_file():
                continue
            findings.append({
                "file": str(f.relative_to(repo)), "path": path,
                "why": "no such file or directory — a cited method/target that "
                       "does not exist is an unfalsifiable claim, not a method",
            })
    return findings, len(files), skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="explicit form of the default behaviour")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"doc_reference_check: no such repo: {repo}", file=sys.stderr)
        return 2
    findings, files, skipped = check(repo)
    if args.json:
        print(json.dumps({"tool": "doc_reference_check", "repo": str(repo),
                          "files_scanned": files,
                          "files_grandfathered": skipped,
                          "findings": findings}, indent=1))
    else:
        for f in findings:
            print(f"FAIL: {f['file']} cites {f['path']} — {f['why']}")
    if findings:
        print(f"FAIL: doc_reference_check ({len(findings)} dangling citation(s) "
              f"across {files} file(s) at or above P{REFERENCE_MIN_PHASE}; "
              f"{skipped} pre-law file(s) grandfathered)")
        return 1
    print(f"PASS: doc_reference_check ({files} file(s) scanned at or above "
          f"P{REFERENCE_MIN_PHASE}, {skipped} pre-law file(s) grandfathered, "
          f"0 dangling citation(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
