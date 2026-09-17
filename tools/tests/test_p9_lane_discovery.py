"""P9-T0-c lane-discovery tests: drift law, broken-suite red, new-lane pickup."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"

def _core_copy_ignore(_dir: str, names: list[str]) -> set[str]:
    """Skip build outputs when mirroring the real xr-core into a tmp tree.

    P12-T0-d: these tests copied the whole sibling checkout — including
    */tests/build/*.o and test binaries, ~64 MB per test — into a tmp_path on
    the 993 MiB /tmp tmpfs. Four such tests filled the filesystem and every
    later test in the run died with ENOSPC, which reads as "25 tests failed"
    rather than "the fixture is too fat". A lane-discovery test needs the
    tests/Makefile files and nothing else.
    """
    # ui/ (43 MB of toolchain + node_modules) and third_party/ (30 MB of
    # vendored Rust) carry no tests/Makefile, so a lane-discovery fixture has
    # no use for them. Excluding them takes the copy from 64 MB to ~2 MB.
    if _dir == str(XR_CORE):
        return {"ui", "third_party", ".git"}
    return {n for n in names
            if n in {"build", "out", "__pycache__", ".git", "node_modules"}}


TOOL = TOOLS / "ci_lane_discovery.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, timeout=600)


def _mini_xr(repo2: Path) -> Path:
    """Temp xr-browser tree (tool + manifest) with a sibling xr-core."""
    xr2 = repo2.parent / "xr-core"
    (repo2 / "tools").mkdir(parents=True, exist_ok=True)
    (repo2 / "docs" / "state").mkdir(parents=True, exist_ok=True)
    shutil.copy(TOOL, repo2 / "tools" / "ci_lane_discovery.py")
    shutil.copy(REPO / "docs" / "state" / "ci-lanes.json",
                repo2 / "docs" / "state" / "ci-lanes.json")
    return xr2


def test_lane_drift_detected(tmp_path: Path) -> None:
    repo2 = tmp_path / "xb"
    _mini_xr(repo2)
    xr2 = repo2.parent / "xr-core"
    shutil.copytree(XR_CORE, xr2, ignore=_core_copy_ignore)
    # Drift: remove a lane from the committed manifest; the gate must FAIL
    # even though the Makefile still exists (recorded vs discovered drift).
    man = json.loads((repo2 / "docs" / "state" / "ci-lanes.json").read_text())
    man["lanes"] = [x for x in man["lanes"] if x != "themes"]
    (repo2 / "docs" / "state" / "ci-lanes.json").write_text(json.dumps(man))
    r = _run("--repo", str(repo2))
    assert r.returncode == 1
    assert "drifted" in r.stdout


def test_new_lane_picked_up_without_hand_listing(tmp_path: Path) -> None:
    # The T0-c blind-spot proof: a NEW suite dir is discovered automatically
    # (no hand-written list to forget) — here its addition shows as drift
    # against the stale record, i.e. it is SEEN, never silently skipped.
    repo2 = tmp_path / "xb"
    _mini_xr(repo2)
    xr2 = repo2.parent / "xr-core"
    shutil.copytree(XR_CORE, xr2, ignore=_core_copy_ignore)
    new = xr2 / "futurephase" / "tests"
    new.mkdir(parents=True, exist_ok=True)
    (new / "Makefile").write_text("test:\n\t@echo ok\n")
    r = _run("--repo", str(repo2))
    assert r.returncode == 1
    assert "futurephase" in r.stdout and "drifted" in r.stdout


def test_broken_discovered_suite_reddens_gate(tmp_path: Path) -> None:
    # Sabotage a discovered suite (the settings one) in a temp copy: the gate
    # must go RED — today's run_checks.sh would have stayed green.
    repo2 = tmp_path / "xb"
    _mini_xr(repo2)
    xr2 = repo2.parent / "xr-core"
    shutil.copytree(XR_CORE, xr2, ignore=_core_copy_ignore)
    mk = xr2 / "settings" / "tests" / "Makefile"
    mk.write_text("test:\n\t@echo 'ALL C++ SETTINGS TESTS PASSED'\n\t@exit 1\n")
    r = _run("--repo", str(repo2))
    assert r.returncode == 1
    assert "settings" in r.stdout
