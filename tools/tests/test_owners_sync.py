"""owners_sync.py: drift detection, generation, fail-closed shape checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]


def run_tool(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "owners_sync.py"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def meta_tree(tmp_path: Path) -> Path:
    """Minimal two-repo layout mirroring s0-paths.yaml expectations."""
    (tmp_path / "xr-core").mkdir()
    (tmp_path / ".github").mkdir(parents=True)
    (tmp_path / "docs" / "process").mkdir(parents=True)
    (tmp_path / "docs" / "process" / "s0-paths.yaml").write_text(
        """
schema_version: 1
owner_groups:
  s0: ["@t/alpha", "@t/omega"]
  s1: ["@t/alpha"]
  default: ["@t/alpha"]
repos:
  xr-core:
    path: "xr-core"
    codeowners_file: "CODEOWNERS"
    s0_paths: ["/policy/", "/vault/"]
    s1_paths: []
  xr-browser:
    path: "."
    codeowners_file: ".github/CODEOWNERS"
    s0_paths: ["/tools/", "/docs/register/"]
    s1_paths: []
""",
        encoding="utf-8",
    )
    return tmp_path


def test_check_fails_when_codeowners_missing(meta_tree: Path) -> None:
    proc = run_tool("--check", "--repo", ".", cwd=meta_tree)
    assert proc.returncode == 1
    assert "missing" in proc.stdout


def test_write_then_check_in_sync(meta_tree: Path) -> None:
    assert run_tool("--write", "--repo", ".", cwd=meta_tree).returncode == 0
    core = (meta_tree / "xr-core" / "CODEOWNERS").read_text()
    meta = (meta_tree / ".github" / "CODEOWNERS").read_text()
    assert "/policy/ @t/alpha @t/omega" in core
    assert "/tools/ @t/alpha @t/omega" in meta
    proc = run_tool("--check", "--repo", ".", cwd=meta_tree)
    assert proc.returncode == 0
    assert "PASS" in proc.stdout
    # json mode exposes per-repo status
    proc_json = run_tool("--check", "--repo", ".", "--json", cwd=meta_tree)
    import json

    data = json.loads(proc_json.stdout)
    assert all(r["status"] == "in-sync" for r in data["repos"])


def test_check_detects_drift(meta_tree: Path) -> None:
    run_tool("--write", "--repo", ".", cwd=meta_tree)
    target = meta_tree / "xr-core" / "CODEOWNERS"
    target.write_text(target.read_text() + "/identity/ @t/alpha\n", encoding="utf-8")
    proc = run_tool("--check", "--repo", ".", cwd=meta_tree)
    assert proc.returncode == 1
    assert "drift" in proc.stdout


def test_duplicate_path_fails_closed(meta_tree: Path) -> None:
    src = meta_tree / "docs" / "process" / "s0-paths.yaml"
    src.write_text(src.read_text().replace('s0_paths: ["/policy/", "/vault/"]', 's0_paths: ["/policy/", "/policy/"]'), encoding="utf-8")
    proc = run_tool("--check", "--repo", ".", cwd=meta_tree)
    assert proc.returncode == 1
    # fail-closed shape error goes to stderr
    assert "duplicate" in (proc.stdout + proc.stderr).lower()


def test_json_output(meta_tree: Path) -> None:
    run_tool("--write", "--repo", ".", cwd=meta_tree)
    proc = run_tool("--check", "--repo", ".", "--json", cwd=meta_tree)
    assert proc.returncode == 0
    import json

    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert {r["repo"] for r in data["repos"]} == {"xr-core", "xr-browser"}
