"""dr_parse.py: schema validation + Register-Change trailer protection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "dr_parse.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def make_register(entries: list[dict]) -> str:
    import yaml

    return yaml.safe_dump(
        {
            "schema_version": 1,
            "plan_sha256": "a" * 64,
            "decisions": entries,
        },
        sort_keys=False,
    )


def full_entries(**over: dict) -> list[dict]:
    base = []
    for n in range(1, 31):
        base.append(
            {
                "id": f"DR-{n:02d}",
                "title": f"decision {n}",
                "status": "RATIFIED",
                "rationale": f"rationale {n}",
                "linked_lg": [],
                "reopen_condition": "written new evidence + recorded reversal",
                "phase_anchor": "P1",
            }
        )
    base[0].update(over.get("dr01", {}))
    return base


@pytest.fixture()
def reg_repo(tmp_path: Path) -> Path:
    """A git repo with a valid register, like the real one (minus plan pin)."""
    (tmp_path / "docs" / "register").mkdir(parents=True)
    (tmp_path / "docs" / "register" / "decisions.yaml").write_text(
        make_register(full_entries()), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True
    )
    return tmp_path


def git(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True)


def test_valid_register_passes(reg_repo: Path) -> None:
    proc = run_tool("--repo", ".", cwd=reg_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = run_tool("--repo", ".", "--json", cwd=reg_repo)
    import json

    data = json.loads(proc.stdout)
    assert data["entries"] == 30
    assert data["expected"] == 30


def test_bad_enum_fails(reg_repo: Path) -> None:
    entries = full_entries()
    entries[5]["status"] = "APPROVED"
    (reg_repo / "docs/register/decisions.yaml").write_text(make_register(entries), encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=reg_repo)
    assert proc.returncode == 1
    assert "status" in proc.stdout


def test_missing_and_duplicate_ids_fail(reg_repo: Path) -> None:
    entries = full_entries()
    del entries[9]  # drop DR-10
    entries.append(dict(entries[0]))  # duplicate DR-01
    (reg_repo / "docs/register/decisions.yaml").write_text(make_register(entries), encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=reg_repo)
    assert proc.returncode == 1
    assert "missing DR id DR-10" in proc.stdout
    assert "duplicate id DR-01" in proc.stdout


def test_malformed_yaml_fails_closed(reg_repo: Path) -> None:
    (reg_repo / "docs/register/decisions.yaml").write_text("decisions: [unclosed\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=reg_repo)
    assert proc.returncode == 1
    assert "fail-closed" in (proc.stdout + proc.stderr).lower() or "YAML parse failure" in (proc.stdout + proc.stderr)


def test_trailer_required_on_register_commits(reg_repo: Path) -> None:
    # baseline commit that does NOT touch the register is fine
    (reg_repo / "README.md").write_text("t\n", encoding="utf-8")
    git(reg_repo, "add", "README.md")
    git(reg_repo, "commit", "-q", "-m", "chore: init")
    # first commit that adds the register: WITH trailer -> fine
    git(reg_repo, "add", "docs/register/decisions.yaml")
    git(reg_repo, "commit", "-q", "-m", "governance: add register", "--trailer", "Register-Change: ADR-0001")
    proc = run_tool("--check-trailers", "--repo", ".", cwd=reg_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # commit touching the register WITHOUT trailer -> must fail
    p = reg_repo / "docs/register/decisions.yaml"
    p.write_text(p.read_text().replace("decision 2", "decision 2 (amended)"), encoding="utf-8")
    git(reg_repo, "commit", "-q", "-am", "governance: amend register")
    proc = run_tool("--check-trailers", "--repo", ".", cwd=reg_repo)
    assert proc.returncode == 1
    assert "Register-Change" in proc.stdout
    # WITH trailer -> must pass
    p.write_text(p.read_text().replace("(amended)", "(amended again)"), encoding="utf-8")
    git(reg_repo, "commit", "-q", "--amend", "--no-edit", "--trailer", "Register-Change: ADR-0002")
    proc = run_tool("--check-trailers", "--repo", ".", cwd=reg_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_json_output(reg_repo: Path) -> None:
    import json

    proc = run_tool("--repo", ".", "--json", cwd=reg_repo)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["entries"] == 30
    assert data["statuses"].get("RATIFIED") == 30
