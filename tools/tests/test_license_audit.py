"""license_audit.py: canonical MPL-2.0 + copyleft marker gate.

Banned-marker samples are loaded from tools/tests/fixtures/ (the
negative corpus) so this test source itself contains no marker
strings — otherwise the scanner would trip on its own test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "license_audit.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def make_repo(tmp_path: Path) -> Path:
    # copy the canonical LICENSE from the real repo (it IS the canonical text)
    shutil.copyfile(REPO / "LICENSE", tmp_path / "LICENSE")
    (tmp_path / "docs" / "state").mkdir(parents=True)
    (tmp_path / "docs/state/license-allowlist.yaml").write_text(
        "schema_version: 1\nallowlist: []\n", encoding="utf-8"
    )
    return tmp_path


def test_real_repo_passes() -> None:
    proc = run_tool("--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["license_check"] == "canonical"
    assert data["code_hits"] == 0
    assert data["doc_hits_allowlisted"] == data["doc_hits_total"]
    assert data["doc_hits_total"] >= 10  # ADRs, evals, plan, threat model


def test_tampered_license_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "LICENSE").write_text("tampered\n", encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "canonical MPL-2.0" in proc.stdout


def test_injected_gpl_sample_in_code_fails(tmp_path: Path) -> None:
    """Plan P1 DoD: 'license-scan fails on an injected GPL sample'."""
    make_repo(tmp_path)
    (tmp_path / "src").mkdir()
    shutil.copyfile(FIXTURES / "gpl-sample.py", tmp_path / "src" / "injected.py")
    proc = run_tool("--repo", ".", "--json", cwd=tmp_path)
    data = json.loads(proc.stdout)
    assert data["status"] == "fail"
    assert data["code_hits"] >= 1
    assert any("src/injected.py" in f for f in data["failures"])
    # the flagged marker is the GPL license-text pattern
    assert any("General Public License" in f for f in data["failures"])


def test_copyleft_in_vendor_dir_fails_even_without_ext(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "third_party" / "lib").mkdir(parents=True)
    shutil.copyfile(FIXTURES / "copyleft-vendor-note.txt", tmp_path / "third_party" / "lib" / "blob")
    proc = run_tool("--repo", ".", "--json", cwd=tmp_path)
    data = json.loads(proc.stdout)
    assert data["status"] == "fail"
    assert any("third_party/lib/blob" in f for f in data["failures"])


def test_unallowlisted_doc_hit_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs" / "note.md").write_text(
        (FIXTURES / "gpl-doc-note.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "docs/note.md" in proc.stdout
    assert "allowlist" in proc.stdout


def test_allowlisted_doc_hit_passes(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs" / "note.md").write_text(
        (FIXTURES / "gpl-doc-note.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "docs/state/license-allowlist.yaml").write_text(
        "schema_version: 1\nallowlist:\n"
        "  - path: docs/note.md\n    justification: data-only, sidecar license\n",
        encoding="utf-8",
    )
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_allowlist_entry_without_justification_fails(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs/state/license-allowlist.yaml").write_text(
        "schema_version: 1\nallowlist:\n  - path: docs/x.md\n", encoding="utf-8"
    )
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "justification" in proc.stdout


def test_missing_allowlist_fails_closed(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "docs/state/license-allowlist.yaml").unlink()
    proc = run_tool("--repo", ".", cwd=tmp_path)
    assert proc.returncode == 1
    assert "missing allowlist" in (proc.stdout + proc.stderr)
