"""build/tests/test_file_size_law.py — the LOC house law, enforced.

Every module under build/ and tools/ is written by hand and read by hand; the
law exists so a file never becomes a place nobody looks. It was previously a
convention restated in docstrings ("split from X to keep files under the
400-LOC law") with nothing checking it, which is how build/patching/apply.py
reached 418 lines unnoticed in P4. This test is the check.

P11-T0-e adds the TOUCHED-FILE law: every .py/.sh under the same roots that
the current phase touched (base_commit..HEAD, base recorded in
docs/state/phase-base.json) must be <=380 lines — stricter than the
whole-tree 400 ceiling, because a file this phase is actively editing must
leave headroom for the next reader. CLI:

    python3 build/tests/test_file_size_law.py --touched [RANGE] [--repo R]

RANGE defaults to the phase-base file; an explicit RANGE (e.g. a negative
fixture's A..B) overrides it. Exit: 0 pass / 1 offenders / 2 usage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

LIMIT = 400
TOUCHED_LIMIT = 380                       # P11-T0-e: touched-file law
PHASE_BASE_RELPATH = "docs/state/phase-base.json"
ROOTS = ("build", "tools", "release")  # P10-T0-d: release/ joins the law as it lands
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


def _candidates() -> list[Path]:
    repo = Path(__file__).resolve().parent.parent.parent
    out: list[Path] = []
    for root in ROOTS:
        base = repo / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in {".py", ".sh"}:
                continue
            out.append(path)
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def touched_files(repo: Path, range_spec: str) -> list[Path]:
    """.py/.sh files under the law roots that RANGE touched (git diff
    --name-only), filtered to files that still exist (deletions are not
    offenders)."""
    r = subprocess.run(["git", "-C", str(repo), "diff", "--name-only",
                        range_spec], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"error: git diff --name-only {range_spec!r} failed: "
                         f"{r.stderr.strip()[:200]}")
    out: list[Path] = []
    for name in r.stdout.split():
        if not name.endswith((".py", ".sh")):
            continue
        if not name.startswith(ROOTS):
            continue
        if any(part in SKIP_DIRS for part in Path(name).parts):
            continue
        p = repo / name
        if p.is_file():
            out.append(p)
    return out


def touched_offenders(repo: Path, range_spec: str) -> list[tuple[int, str]]:
    out = []
    for path in touched_files(repo, range_spec):
        lines = len(path.read_text(encoding="utf-8",
                                   errors="replace").splitlines())
        if lines > TOUCHED_LIMIT:
            out.append((lines, str(path.relative_to(repo))))
    return sorted(out, reverse=True)


def phase_range(repo: Path) -> str:
    base_doc = repo / PHASE_BASE_RELPATH
    if not base_doc.is_file():
        raise SystemExit(f"error: no {PHASE_BASE_RELPATH} under {repo} and no "
                         "explicit RANGE given — the touched-file law needs "
                         "the phase base commit (usage: --touched A..B)")
    base = json.loads(base_doc.read_text(encoding="utf-8"))["base_commit"]
    return f"{base}..HEAD"


def _touched_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="test_file_size_law", description="the touched-file size law")
    ap.add_argument("--touched", nargs="?", const="", default=None,
                    metavar="RANGE",
                    help="check files touched in RANGE (default: the "
                         "phase-base file's base_commit..HEAD)")
    ap.add_argument("--repo", default=None, help="repository root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.touched is None:
        ap.error("--touched is the CLI mode of this law (the whole-tree "
                 "400-law runs under pytest)")
    repo = Path(a.repo).resolve() if a.repo else _repo_root()
    range_spec = a.touched or phase_range(repo)
    files = touched_files(repo, range_spec)
    offenders = touched_offenders(repo, range_spec)
    if a.json:
        print(json.dumps({"range": range_spec, "touched": len(files),
                          "limit": TOUCHED_LIMIT,
                          "offenders": [{"lines": n, "path": p}
                                        for n, p in offenders],
                          "status": "fail" if offenders else "pass"},
                         indent=2))
    else:
        for n, path in offenders:
            print(f"  OVER: {path} at {n} lines (touched-file limit "
                  f"{TOUCHED_LIMIT})")
        if offenders:
            print(f"FAIL: touched-file size law ({len(offenders)} offender(s) "
                  f"in {range_spec}, limit {TOUCHED_LIMIT})")
        else:
            print(f"PASS: touched-file size law ({len(files)} touched .py/.sh "
                  f"in {range_spec}, all <= {TOUCHED_LIMIT} lines"
                  + ("; nothing touched — vacuously green" if not files else "")
                  + ")")
    return 1 if offenders else 0


def test_touched_files_are_under_380():
    """pytest mirror of the CLI law, from the recorded phase base."""
    repo = _repo_root()
    base_doc = repo / PHASE_BASE_RELPATH
    if not base_doc.is_file():
        pytest.skip(f"SKIP (no {PHASE_BASE_RELPATH}) — touched-file law has "
                    "no phase base to judge against; visible, never silent")
    range_spec = phase_range(repo)
    base = range_spec.split("..")[0]
    probe = subprocess.run(["git", "-C", str(repo), "cat-file", "-e",
                            base + "^{commit}"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"SKIP (phase base {base[:9]} not in this clone — "
                    "shallow/fresh checkout); the CI clone is full-depth")
    offenders = touched_offenders(repo, range_spec)
    assert not offenders, (
        f"over the {TOUCHED_LIMIT}-line touched-file law (P11-T0-e): "
        + ", ".join(f"{n} lines in {p}" for n, p in offenders))


def test_every_file_is_under_the_loc_limit():
    # conftest.py is not in build/ or tools/, so the sys.path shim the other
    # build tests rely on is not automatic here.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    offenders = []
    for path in _candidates():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > LIMIT:
            offenders.append((lines, str(path.relative_to(Path(__file__).resolve().parent.parent.parent))))
    assert not offenders, "over the 400-LOC law: " + ", ".join(
        f"{n} lines in {p}" for n, p in sorted(offenders, reverse=True))


@pytest.mark.parametrize("path", _candidates(), ids=lambda p: str(p))
def test_files_are_not_empty(path: Path):
    assert path.read_text(encoding="utf-8").strip(), f"{path} is empty"


if __name__ == "__main__":
    raise SystemExit(_touched_main(sys.argv[1:]))
