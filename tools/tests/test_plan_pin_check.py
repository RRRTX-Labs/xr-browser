"""plan_pin_check.py: SHA-256 pin of the committed Master Plan."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
PIN = "a74b2aa4e8fd6f427c71cadfe932489249afe208a10413bf78c04734fd343e1b"


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "plan_pin_check.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def make_repo(tmp_path: Path, plan_body: str = "# plan\nline\n") -> Path:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md").write_text(plan_body, encoding="utf-8")
    (tmp_path / "docs/master-plan.sha256").write_text(
        "0" * 64 + "\n", encoding="utf-8"
    )
    import hashlib

    real = hashlib.sha256(plan_body.encode()).hexdigest()
    (tmp_path / "docs/master-plan.sha256").write_text(real + "\n", encoding="utf-8")
    return tmp_path


def test_real_repo_pin_passes() -> None:
    proc = run_tool()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = run_tool("--json")
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["pinned_sha256"] == PIN
    assert data["actual_sha256"] == PIN
    assert data["plan_bytes"] == 298080


def test_tampered_plan_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    p = tmp_path / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
    p.write_text(p.read_text() + "tampered\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "pin mismatch" in proc.stdout


def test_compare_against_independent_copy(tmp_path: Path) -> None:
    make_repo(tmp_path)
    other = tmp_path / "original.md"
    other.write_text((tmp_path / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md").read_text(), encoding="utf-8")
    proc = run_tool("--repo", ".", "--compare-against", str(other), cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    other.write_text("different\n", encoding="utf-8")
    proc = run_tool("--repo", ".", "--compare-against", str(other), cwd=tmp_path)
    assert proc.returncode == 1
    assert "comparison copy" in proc.stdout


def test_missing_pin_file_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs/master-plan.sha256").unlink()
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "missing pin file" in (proc.stdout + proc.stderr)


def test_bad_pin_format_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs/master-plan.sha256").write_text("not-a-hash\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "not a 64-hex" in (proc.stdout + proc.stderr)
