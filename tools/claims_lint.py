#!/usr/bin/env python3
"""tools/claims_lint.py — the announcement-voice gate (P10-T6): a release
note may not contain an unsupported superlative or security promise.
"Announcement links evidence, not adjectives" (plan). Scans
release/notes/**.md for the banned-claims list (committed HERE — the P7
pattern-vs-secret lesson: say exactly what matches).

Banned (case-insensitive, word-boundary): best, fastest, most secure,
safest, unbreakable, military-grade, bulletproof, hack-proof,
"100% secure", guaranteed, invisible, anonymous, untraceable, zero-risk.
Allowed: factual comparatives WITH an evidence link on the same line
(e.g. "smaller attack surface (evidence: ...)") — enforced as: a line
containing a banned term FAILS unless it also contains `evidence:`
AND is a comparative (-er/-est forms of measurable adjectives only).
Exit: 0 clean · 1 FAIL · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BANNED = [
    r"\bbest\b", r"\bfastest\b", r"\bmost secure\b", r"\bsafest\b",
    r"\bunbreakable\b", r"\bmilitary[- ]grade\b", r"\bbulletproof\b",
    r"\bhack[- ]proof\b", r"\b100% secure\b", r"\bguaranteed\b",
    r"\binvisible\b", r"\banonymous\b", r"\buntraceable\b",
    r"\bzero[- ]risk\b", r"\bperfect(ly safe)?\b",
]


def scan(path: Path) -> list[str]:
    fails: list[str] = []
    for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        for pat in BANNED:
            if re.search(pat, line, re.IGNORECASE):
                if re.search(r"\bevidence:", line, re.IGNORECASE) and \
                        re.search(r"\b(smaller|fewer|lower|reduced)\b", line,
                                  re.IGNORECASE):
                    continue  # factual comparative WITH its evidence link
                fails.append(f"{path.name}:{lineno}: banned claim "
                             f"({pat}) — state the fact + link evidence")
                break
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(prog="claims-lint",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--notes-dir", default=None)
    ap.add_argument("--file", default=None,
                    help="scan one file (negative fixtures)")
    a = ap.parse_args()
    targets = [Path(a.file).resolve()] if a.file else \
        sorted((Path(a.notes_dir).resolve() if a.notes_dir
                else REPO / "release" / "notes").rglob("*.md"))
    targets = [t for t in targets if t.exists()]
    if not targets:
        print("FAIL: no release notes found (a voice gate over zero files "
              "certifies nothing)")
        return 1
    fails: list[str] = []
    for t in targets:
        fails.extend(scan(t))
    if fails:
        for f in fails[:15]:
            print(f"FAIL: {f}")
        print(f"FAIL: claims-lint ({len(fails)} banned claim(s) in "
              f"{len(targets)} file(s))")
        return 1
    print(f"PASS: claims-lint ({len(targets)} note file(s); no unsupported "
          "superlatives; evidence links, not adjectives)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
