"""dco_check.py: DCO signoff gate (Plan P1 DoD: 'DCO bot blocks unsigned PR')."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "dco_check.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def git(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True)


@pytest.fixture()
def dco_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    git(tmp_path, "config", "user.name", "Alice A")
    git(tmp_path, "config", "user.email", "alice@example.invalid")
    (tmp_path / "f.txt").write_text("1\n", encoding="utf-8")
    git(tmp_path, "add", "f.txt")
    git(tmp_path, "commit", "-q", "--signoff", "-m", "chore: first (signed)")
    return tmp_path


def test_real_repo_all_signed() -> None:
    proc = run_tool("--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["commits_checked"] >= 8


def test_unsigned_commit_fails(dco_repo: Path) -> None:
    """Plan P1 DoD negative: an unsigned commit must be blocked."""
    (dco_repo / "f.txt").write_text("1\n2\n", encoding="utf-8")
    git(dco_repo, "commit", "-q", "-am", "chore: unsigned change")
    proc = run_tool("--repo", ".", cwd=dco_repo)
    assert proc.returncode == 1
    assert "missing Signed-off-by" in proc.stdout


def test_range_scoping(dco_repo: Path) -> None:
    (dco_repo / "f.txt").write_text("1\n2\n", encoding="utf-8")
    git(dco_repo, "commit", "-q", "-am", "chore: unsigned")
    # full history now fails…
    proc = run_tool("--repo", ".", cwd=dco_repo)
    assert proc.returncode == 1
    # …but the range containing only the signed root commit passes
    proc = run_tool("--range", "HEAD~1..HEAD~0", "--repo", ".", cwd=dco_repo)
    # HEAD~1..HEAD~0 is the last commit (the unsigned one) -> must fail
    assert proc.returncode == 1
    # root-only range passes
    proc = run_tool("--range", "HEAD~1", "--repo", ".", cwd=dco_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_signoff_email_mismatch_fails(dco_repo: Path) -> None:
    (dco_repo / "f.txt").write_text("1\n2\n", encoding="utf-8")
    git(dco_repo, "add", "f.txt")
    git(dco_repo, "commit", "-q", "-m", "chore: borrowed signoff")
    git(dco_repo, "commit", "-q", "--amend", "--no-edit", "--trailer",
        "Signed-off-by: Bob B <bob@example.invalid>")
    proc = run_tool("--repo", ".", cwd=dco_repo)
    assert proc.returncode == 1
    assert "does not match committer email" in proc.stdout


def test_json_failure_listing(dco_repo: Path) -> None:
    (dco_repo / "f.txt").write_text("1\n2\n", encoding="utf-8")
    git(dco_repo, "commit", "-q", "-am", "chore: unsigned again")
    proc = run_tool("--repo", ".", "--json", cwd=dco_repo)
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["status"] == "fail"
    assert len(data["failures"]) == 1
    assert "missing Signed-off-by" in data["failures"][0]
