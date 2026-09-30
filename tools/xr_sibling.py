#!/usr/bin/env python3
"""tools/xr_sibling.py — the ONE place a sibling xr-core checkout is resolved.

Why this module exists (P13-C-P0.1 introduces it; P13-C-P0.2 governs it).
Measured at e503f9e, 2026-09-30: `tools/coverage_check.py:31` guessed the
layout with `Path(__file__).resolve().parents[1].parent / "xr-core"`, then
`sys.path.insert(0, XR_CORE / "fakes")` + `import commands`. Two failure modes,
both silent in the direction that matters:

  * no sibling  -> `ModuleNotFoundError: No module named 'commands'` (Python
    then falls through to a long-dead stdlib name). The error reads as a broken
    environment, so an agent re-runs it and moves on;
  * a sibling at an OLDER commit -> a vacuous PASS. That is what happened to
    the P13-T1 predecessor: the local `../xr-core` predated the panel files, so
    the "landed surface" scan found nothing to bite and every local run was
    green while the hosted run was red.

A verdict computed from a sibling checkout is meaningless unless the sibling is
at the pin, so the rule (docs/process/cross-repo-pin.md) is: the gate proves it
or says BLOCKED-LAYOUT. Never an ImportError, never a silent pass.

Typed failures (all exit 2, "usage", because a gate that cannot see its inputs
has not rendered a verdict):

  BLOCKED-LAYOUT (no xr-core at <path>)            — absent sibling
  STALE-SIBLING  (have <sha>, want <pin>)          — wrong commit
  DIRTY-SIBLING  (uncommitted changes at <path>)   — clean-tree law

Stdlib only. No imports from the rest of tools/ (this is the bottom of that
stack — everything else is allowed to import it, never the reverse).
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

EXIT_USAGE = 2

PIN_RE = re.compile(r'^\s*xr_core_rev:\s*"?([0-9a-f]{40})"?', re.MULTILINE)
DEPS_REL = "DEPS"


class SiblingError(Exception):
    """A typed, actionable refusal. `code` is the machine-readable half."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Sibling:
    """A verified sibling checkout: path + the head it is actually at."""

    path: Path
    head: str | None
    pin: str | None

    @property
    def fakes(self) -> Path:
        return self.path / "fakes"

    def sub(self, *parts: str) -> Path:
        return self.path.joinpath(*parts)


def _git(repo: Path, *args: str) -> str | None:
    """`git -C repo args`, or None when git/repo cannot answer. Never raises."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def deps_pin(repo: Path) -> str | None:
    """The DEPS-recorded xr-core commit, or None when it cannot be read.

    None is honest: a checkout with no DEPS (a fixture tree, an unpacked
    tarball) has no pin to compare against, and the caller decides whether that
    is legal for it.
    """
    deps = Path(repo) / DEPS_REL
    if not deps.is_file():
        return None
    m = PIN_RE.search(deps.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def sibling_head(path: Path) -> str | None:
    """The sibling's HEAD sha, or None when it is not a readable git worktree."""
    return _git(path, "rev-parse", "HEAD")


def is_clean(path: Path) -> bool:
    """True when the worktree has no tracked modifications/untracked files.

    A dirty sibling is not a verdict input either: `git rev-parse HEAD` would
    agree with the pin while the files on disk are something else.
    """
    out = _git(path, "status", "--porcelain")
    return out is not None and out == ""


def check(repo: Path, *, override: str | None = None,
          require_clean: bool = True, require_pin: bool = True) -> Sibling:
    """Resolve `repo`'s xr-core sibling and PROVE it is usable, or raise.

    `override` is the caller's `--xr-core` flag: a nonstandard layout is a
    flag, never a silent skip (the flag path still gets every check — an
    override is not an exemption).
    """
    repo = Path(repo).resolve()
    path = Path(override).resolve() if override else (repo.parent / "xr-core")
    if not path.is_dir():
        raise SiblingError(
            "BLOCKED-LAYOUT",
            f"no xr-core at {path} — this gate computes its verdict from the "
            f"sibling checkout, so an absent sibling is BLOCKED, not a pass "
            f"(pass --xr-core <path> for a nonstandard layout)")
    head = sibling_head(path)
    if head is None:
        raise SiblingError(
            "BLOCKED-LAYOUT",
            f"{path} is not a readable git worktree (git rev-parse HEAD failed) "
            f"— a gate cannot compare an unknown tree against the pin")
    pin = deps_pin(repo)
    if require_pin and pin is not None and head != pin:
        raise SiblingError(
            "STALE-SIBLING",
            f"have {head}, want {pin} — the sibling is not at DEPS.xr_core_rev, "
            f"so any verdict computed from it is meaningless "
            f"(docs/process/cross-repo-pin.md)")
    if require_clean and not is_clean(path):
        raise SiblingError(
            "DIRTY-SIBLING",
            f"uncommitted changes at {path} — HEAD agrees with the pin but the "
            f"tree does not, so the files read are not the pinned files")
    return Sibling(path=path, head=head, pin=pin)


def resolve_or_exit(repo: Path, *, override: str | None = None,
                    tool: str = "tool") -> Sibling:
    """`check()` for a command-line tool: on failure print the typed line to
    stderr and exit 2, never raise a traceback and never return a guess.

    Every routed tool calls this with its own name so the message names the
    reader, not just the reader's symptom.
    """
    try:
        return check(repo, override=override)
    except SiblingError as err:
        print(f"{tool}: {format_error(err)}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE) from None


def format_error(err: SiblingError) -> str:
    """One line, greppable, with the code first: what a failure condition wants."""
    return f"{err.code}: {err.message}"


def main(argv: list[str]) -> int:
    """`python3 tools/xr_sibling.py [--repo .] [--xr-core PATH] [--json]`

    A human-runnable probe, so "which sibling is this check actually reading?"
    has a one-line answer instead of a debugging session.
    """
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="xr_sibling", description=__doc__)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        sib = check(repo, override=args.xr_core)
    except SiblingError as err:
        if args.json:
            print(json.dumps({"tool": "xr_sibling", "status": "blocked",
                              "code": err.code, "message": err.message}, indent=1))
        else:
            print(format_error(err))
        return EXIT_USAGE
    print(json.dumps({"tool": "xr_sibling", "status": "ok",
                      "path": str(sib.path), "head": sib.head,
                      "pin": sib.pin}, indent=1) if args.json else
          f"xr_sibling: OK {sib.path} at {sib.head} (DEPS pin {sib.pin})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
