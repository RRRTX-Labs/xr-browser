#!/usr/bin/env python3
"""tools/evidence_presence_check.py — a phase that exists must have a bundle
(P12-T0-b).

Root cause this closes: ``evidence_check.py`` validates the bundles that are
PRESENT. Its own docstring says a "phase is gated the moment its bundle
lands" — which means a phase that shipped **no bundle at all** was invisible
by design, not exempt. P11 closed with ``evidence/P11/`` containing ``logs``
only: 15 DoD rows existed as commit-message prose and ``docs/qa/*`` narrative,
with no contract-valid artifact, and ``--strict`` passed because there was
nothing to be strict about. That is how four phases in a row ended with "no
summary", and the validator could not see any of it.

Law (derived, never hand-listed — the P11-T0-a lesson):

  For every phase label that appears as a ``P<n>:`` prefix in
  ``git log --format=%s``, ``evidence/P<n>/`` MUST contain BOTH
  ``evidence.json`` and ``human-gates.md``. A ``logs/`` directory with no
  bundle is a hard FAIL — that is P11's exact shape.

  Exemptions: P1/P2 keep the documented tolerant legacy path (HG-25), so
  ``n <= LEGACY_EXEMPT_MAX_PHASE`` is only required to have *something*.
  Every phase from P3 up is required in full.

This module is imported by ``evidence_check.py`` (which is at the
touched-file size ceiling) and is also runnable standalone.

Usage:  python3 tools/evidence_presence_check.py [--repo .] [--json]
            [--evidence-dir evidence]
Exit: 0 pass · 1 fail · 2 usage. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# Must stay in step with evidence_check.LEGACY_EXEMPT_MAX_PHASE (HG-25).
LEGACY_EXEMPT_MAX_PHASE = 2
# Phase references in a commit SUBJECT. Deliberately broad, and the breadth is
# the point: the measured shapes in this repo's history are `P10:`, `P6-T5:`,
# `p9:`, `evidence(P5):`, `P11-T7:`, `P10-T1:`. A `^P<n>:` prefix rule — the
# obvious reading — discovers only 3 of the 11 phases that have evidence
# directories, so it would have let 8 phases skip the bundle requirement
# entirely. Under-inclusive discovery is the same invisibility class as
# over-inclusive silence, so this matches a phase token anywhere in the
# subject, case-insensitively.
_PHASE_TOKEN_RE = re.compile(r"\bP(\d{1,3})\b", re.IGNORECASE)
REQUIRED_FILES = ("evidence.json", "human-gates.md")


def _subjects(repo: Path) -> list[str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), "log", "--format=%s"],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    return r.stdout.splitlines() if r.returncode == 0 else []


def phases_in_history(repo: Path, extra_repos: tuple[Path, ...] = ()) -> list[int]:
    """Phase numbers referenced anywhere in commit subjects.

    Derived from the tree, never from a manifest: a phase that produced
    commits but no bundle is exactly the case this gate exists to catch, so
    the phase list cannot come from the evidence directory itself (circular —
    it would only ever list phases that already complied).

    `extra_repos` lets the caller include the sibling repo (xr-core), whose
    history references the same phase numbers for work that lands there.
    """
    out: set[int] = set()
    for r in (repo, *extra_repos):
        for line in _subjects(r):
            for m in _PHASE_TOKEN_RE.finditer(line):
                out.add(int(m.group(1)))
    return sorted(out)


def check(repo: Path, evidence_dir: str = "evidence",
          extra_repos: tuple[Path, ...] = ()) -> tuple[list[str], list[str]]:
    """(failures, info). Deterministic, offline."""
    root = repo / evidence_dir
    phases = phases_in_history(repo, extra_repos)
    fails: list[str] = []
    info: list[str] = []

    if not phases:
        # A repo with no phase commits certifies nothing; say so loudly rather
        # than printing a green that means "I looked at nothing".
        fails.append("no `P<n>:` subjects found in git log — the phase list "
                     "could not be derived (is this a git checkout?)")
        return fails, info

    for n in phases:
        d = root / f"P{n}"
        if not d.is_dir():
            fails.append(f"P{n}: appears in git history but evidence/P{n}/ "
                         f"does not exist — no bundle, no human-gates")
            continue
        present = [f for f in REQUIRED_FILES if (d / f).is_file()]
        missing = [f for f in REQUIRED_FILES if f not in present]
        if missing:
            shape = "logs/-only" if (d / "logs").is_dir() and not present \
                else "incomplete"
            fails.append(f"P{n}: evidence bundle {shape} — missing "
                         f"{missing}; a logs/ directory without a bundle is "
                         f"not evidence (P11's shape, P12-T0-b)")
            continue
        try:
            doc = json.loads((d / "evidence.json").read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            fails.append(f"P{n}: evidence.json unreadable ({exc})")
            continue
        rows = doc.get("dod_rows")
        n_rows = len(rows) if isinstance(rows, (list, dict)) else 0
        if n_rows == 0:
            fails.append(f"P{n}: evidence.json has zero dod_rows — a bundle "
                         f"with nothing in it is not evidence")
            continue
        hg = (d / "human-gates.md").read_text(encoding="utf-8")
        if len(hg.strip()) < 40:
            fails.append(f"P{n}: human-gates.md is empty or near-empty "
                         f"({len(hg.strip())} chars)")
            continue
        exempt = " (legacy tolerant path, HG-25)" if n <= \
            LEGACY_EXEMPT_MAX_PHASE else ""
        info.append(f"ok: P{n} — {n_rows} dod row(s), human-gates.md "
                    f"present{exempt}")
    return fails, info


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="evidence_presence_check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--evidence-dir", default="evidence")
    ap.add_argument("--also-repo", default="",
                    help="comma-separated extra repo roots whose commit "
                         "subjects also name phases (e.g. ../xr-core)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    if not repo.is_dir():
        print(f"usage: {repo} is not a directory", file=sys.stderr)
        return EXIT_USAGE
    extra = tuple(Path(x.strip()).resolve() for x in a.also_repo.split(",")
                  if x.strip())
    fails, info = check(repo, a.evidence_dir, extra)
    if a.json:
        print(json.dumps({"tool": "evidence_presence_check",
                          "phases_in_history": phases_in_history(repo, extra),
                          "count": len(fails), "violations": fails},
                         sort_keys=True, indent=2))
    for line in info:
        print(line)
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: evidence_presence_check ({len(fails)} violation(s))")
        return EXIT_FAIL
    print(f"PASS: evidence_presence_check ({len(info)} phase(s) from git "
          f"history all carry evidence.json + human-gates.md with rows)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
