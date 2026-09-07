"""build/tests/test_file_size_law.py — the 400-LOC house law, enforced.

Every module under build/ and tools/ is written by hand and read by hand; the
law exists so a file never becomes a place nobody looks. It was previously a
convention restated in docstrings ("split from X to keep files under the
400-LOC law") with nothing checking it, which is how build/patching/apply.py
reached 418 lines unnoticed in P4. This test is the check.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIMIT = 400
ROOTS = ("build", "tools")
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
