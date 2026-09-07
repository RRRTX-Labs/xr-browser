#!/usr/bin/env python3
"""tools/amend_guard.py — contract-amendment RFC trailer gate (P5-T10, L14).

Mirrors the Register-Change trailer machinery (tools/dr_parse.py). After a
contract is stamped in docs/contracts/FROZEN.yaml, any commit in the given
range that touches a GUARDED file MUST:
  * carry the trailer `Contract-Amendment: RFC-<n>`, AND
  * have `docs/rfcs/RFC-<n>.md` present with `status: APPROVED`.

Guarded files (per-file, as this gate's law states — "a listed frozen
contract doc"; the freeze unit is per-contract, not per-directory):
  * `xr-core/mojom/**` (always), and
  * every contract file LISTED in the freeze registers: the `packet:` rows
    of FROZEN.yaml and the file columns of the INDEX.md mapping table, and
    the register files themselves (FROZEN.yaml, INDEX.md) — editing what is
    frozen, or the record of what is frozen, is an amendment.
Unlisted files under docs/contracts/ are post-freeze DRAFTING (new contracts
being born, pre-stamp by definition): warn-only, never a silent pass.

Pre-stamp (before FROZEN.yaml exists at all): warn-only (drafting during
the freeze itself is free). Approval is a human act; an agent never
self-approves. A commit that touches FROZEN.yaml is a registry/stamp
commit and is exempt ONLY if it touches no frozen-listed contract file
and no mojom file (a stamp must never smuggle an amendment).

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
GUARDED_SUFFIXES = (".mojom", ".md", ".schema.json")
REGISTER_FILES = ("docs/contracts/FROZEN.yaml", "docs/contracts/INDEX.md")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return r.stdout


def _frozen_present(repo: Path) -> bool:
    return (repo / "docs/contracts/FROZEN.yaml").exists()


def _listed_contract_files(repo: Path) -> set[str]:
    """Files bound by the freeze registers: FROZEN.yaml packet rows + the
    INDEX.md mapping-table file columns (resolved repo-root-relative for
    xr-core paths, docs/contracts-relative otherwise)."""
    listed: set[str] = set()
    frozen = repo / "docs/contracts/FROZEN.yaml"
    if frozen.exists():
        for m in re.finditer(r"packet:\s*(\S+)", frozen.read_text()):
            listed.add("docs/contracts/" + m.group(1).strip("`"))
    index = repo / "docs/contracts/INDEX.md"
    if index.exists():
        for line in index.read_text().splitlines():
            if not line.startswith("|"):
                continue
            for m in _BACKTICK_RE.finditer(line):
                p = m.group(1)
                if not p.endswith(GUARDED_SUFFIXES):
                    continue
                listed.add(p if p.startswith("xr-core/") else "docs/contracts/" + p)
    return listed


def _rfc_approved(repo: Path, n: str) -> bool:
    p = repo / "docs/rfcs" / f"RFC-{n}.md"
    if not p.exists():
        return False
    return re.search(r"status:\s*APPROVED", p.read_text(), re.IGNORECASE) is not None


def check_range(repo: Path, rng: str) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    warns: list[str] = []
    stamped = _frozen_present(repo)
    listed = _listed_contract_files(repo)
    shas = _git(repo, "rev-list", rng).split()
    for sha in shas:
        files = _git(repo, "show", "--name-only", "--format=", sha).split()
        mojom = [f for f in files if f.startswith(GUARDED_PREFIXES)]
        frozen_listed = [f for f in files if f in listed]
        registry = [f for f in files if f in REGISTER_FILES]
        # A commit that itself re-stamps the register (FROZEN.yaml) is a
        # baseline/stamp commit and is exempt ONLY when it carries no
        # amendment payload (no frozen-listed file, no mojom file): a stamp
        # must never smuggle an amendment past the gate.
        if "docs/contracts/FROZEN.yaml" in files and not mojom and not frozen_listed:
            continue
        guarded = mojom + frozen_listed + registry
        drafting = [f for f in files
                    if f.startswith(GUARDED_DOCS_DIR)
                    and f.endswith(GUARDED_SUFFIXES)
                    and f not in listed and f not in REGISTER_FILES]
        if not guarded and not drafting:
            continue
        body = _git(repo, "show", "-s", "--format=%B", sha)
        m = TRAILER_RE.search(body)
        subject = _git(repo, "show", "-s", "--format=%s", sha).strip()
        if not stamped:
            if guarded or drafting:
                warns.append(f"{sha[:8]} touches contracts pre-stamp (warn-only): {subject}")
            continue
        if drafting and not guarded:
            warns.append(f"{sha[:8]} drafts unlisted post-freeze contract file(s) "
                         f"{drafting} (warn-only; stamp them in a registry to freeze): "
                         f"{subject}")
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
