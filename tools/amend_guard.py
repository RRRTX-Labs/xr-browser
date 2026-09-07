#!/usr/bin/env python3
"""tools/amend_guard.py — contract-amendment RFC trailer gate (P5-T10, L14).

Mirrors the Register-Change trailer machinery (tools/dr_parse.py). After a
contract is stamped in docs/contracts/FROZEN.yaml, any commit in the given
range that touches `xr-core/mojom/**` or a listed frozen contract doc MUST:
  * carry the trailer `Contract-Amendment: RFC-<n>`, AND
  * have `docs/rfcs/RFC-<n>.md` present with `status: APPROVED`.

Pre-stamp (before a file is in FROZEN.yaml): warn-only (drafting during the
freeze itself is free). Approval is a human act; an agent never self-approves.

Exit: 0 pass (or warn-only) · 1 violation · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

TRAILER_RE = re.compile(r"^Contract-Amendment:\s*RFC-(\d+)\s*$", re.MULTILINE)
GUARDED_PREFIXES = ("xr-core/mojom/",)
GUARDED_DOCS_DIR = "docs/contracts/"


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return r.stdout


def _frozen_present(repo: Path) -> bool:
    return (repo / "docs/contracts/FROZEN.yaml").exists()


def _rfc_approved(repo: Path, n: str) -> bool:
    p = repo / "docs/rfcs" / f"RFC-{n}.md"
    if not p.exists():
        return False
    return re.search(r"status:\s*APPROVED", p.read_text(), re.IGNORECASE) is not None


def check_range(repo: Path, rng: str) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    warns: list[str] = []
    stamped = _frozen_present(repo)
    shas = _git(repo, "rev-list", rng).split()
    for sha in shas:
        files = _git(repo, "show", "--name-only", "--format=", sha).split()
        # A commit that itself adds/modifies FROZEN.yaml is a freeze/baseline
        # commit (it establishes or re-stamps the register); it is exempt —
        # amendments are the commits that come AFTER the baseline.
        if any(f == "docs/contracts/FROZEN.yaml" for f in files):
            continue
        touched = [f for f in files
                   if f.startswith(GUARDED_PREFIXES)
                   or (f.startswith(GUARDED_DOCS_DIR) and f.endswith((".mojom", ".md", ".schema.json")))]
        if not touched:
            continue
        body = _git(repo, "show", "-s", "--format=%B", sha)
        m = TRAILER_RE.search(body)
        subject = _git(repo, "show", "-s", "--format=%s", sha).strip()
        if not stamped:
            warns.append(f"{sha[:8]} touches contracts pre-stamp (warn-only): {subject}")
            continue
        if not m:
            fails.append(f"{sha[:8]} touches frozen contracts without "
                         f"'Contract-Amendment: RFC-<n>' trailer: {subject}")
            continue
        n = m.group(1)
        if not _rfc_approved(repo, n):
            fails.append(f"{sha[:8]} cites RFC-{n} which is missing or not APPROVED")
    return fails, warns


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="amend_guard", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--range", dest="rng", default="HEAD~1..HEAD")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    fails, warns = check_range(repo, args.rng)
    if args.json:
        import json
        print(json.dumps({"tool": "amend_guard",
                          "stamped": _frozen_present(repo),
                          "status": "pass" if not fails else "fail",
                          "warnings": warns, "failures": fails}, indent=2))
    else:
        for w in warns:
            print(f"WARN: {w}")
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: amend_guard (stamped={_frozen_present(repo)})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
