"""vocab_lint.py: banned-claims vocabulary + line-precise allowlist."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]

ALLOWLIST = """schema_version: 1
allowlist:
  - path: {path}
    line: {line}
    pattern: {pattern}
    justification: {just}
"""


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "vocab_lint.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def make_repo(tmp_path: Path, allowlist: str) -> Path:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/state").mkdir()
    (tmp_path / "docs/state/vocab-allowlist.yaml").write_text(allowlist, encoding="utf-8")
    return tmp_path


def test_real_repo_passes_all_allowlisted() -> None:
    proc = run_tool("--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["unallowlisted_hits"] == 0
    assert data["allowlisted_hits"] == data["total_hits"]
    assert data["total_hits"] >= 19  # plan cites the bans; registry quotes the DROP row
    assert any("intent" in r for r in data["human_enforced_rules"])


def test_banned_word_fails(tmp_path: Path) -> None:
    make_repo(tmp_path, "schema_version: 1\nallowlist: []\n")
    (tmp_path / "docs" / "copy.md").write_text("Our stealth mode is unbreakable.\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "stealth" in proc.stdout
    assert "unbreakable" in proc.stdout
    assert "docs/copy.md:1" in proc.stdout


def test_allowlist_entry_suppresses(tmp_path: Path) -> None:
    allow = ALLOWLIST.format(path="docs/copy.md", line=1, pattern="anonymous", just='"quoted in a ban"')
    make_repo(tmp_path, allow)
    (tmp_path / "docs" / "copy.md").write_text("cite the word: anonymous\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_allowlist_wrong_line_does_not_suppress(tmp_path: Path) -> None:
    allow = ALLOWLIST.format(path="docs/copy.md", line=1, pattern="stealth", just='"stale entry"')
    make_repo(tmp_path, allow)
    (tmp_path / "docs" / "copy.md").write_text("clean first line\nline two: stealth\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "copy.md:2" in proc.stdout


def test_allowlist_missing_justification_fails(tmp_path: Path) -> None:
    make_repo(tmp_path, "schema_version: 1\nallowlist:\n  - path: docs/copy.md\n    line: 1\n    pattern: stealth\n")
    (tmp_path / "docs" / "copy.md").write_text("stealth\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "justification" in proc.stdout


def test_score_and_percent_variants(tmp_path: Path) -> None:
    make_repo(tmp_path, "schema_version: 1\nallowlist: []\n")
    (tmp_path / "docs" / "notes.md").write_text(
        "get 99% protected now, a security score of A+\n", encoding="utf-8"
    )
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "% protected" in proc.stdout
    assert "protection/security score" in proc.stdout


def test_military_grade_spelling_variants(tmp_path: Path) -> None:
    make_repo(tmp_path, "schema_version: 1\nallowlist: []\n")
    (tmp_path / "docs" / "x.md").write_text("military grade encryption\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "military-grade" in proc.stdout


def test_suggest_lists_hits(tmp_path: Path) -> None:
    make_repo(tmp_path, "schema_version: 1\nallowlist: []\n")
    (tmp_path / "docs" / "y.md").write_text("anonymous\n", encoding="utf-8")
    proc = run_tool("--repo", ".", "--suggest", cwd=tmp_path)
    assert proc.returncode == 0
    assert "docs/y.md" in proc.stdout
    assert "anonymous" in proc.stdout
    assert "justification: TODO" in proc.stdout


def test_no_anonymity_false_positive(tmp_path: Path) -> None:
    # "anonymity" (correct usage: pointing users to Tor Browser) must NOT trip the "anonymous" ban
    make_repo(tmp_path, "schema_version: 1\nallowlist: []\n")
    (tmp_path / "docs" / "z.md").write_text(
        "Disposable is not network anonymity; anonymity-critical users are directed to Tor Browser.\n",
        encoding="utf-8",
    )
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
