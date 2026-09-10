"""tools/tests/test_p9_isolation.py — P9-T2 isolation matrix + ledger law."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOLS / name), *args],
        capture_output=True, text=True)


def test_matrix_executes_fake_cells_and_reports_counts() -> None:
    r = run_tool("isolation_matrix.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fake cells executed" in r.stdout
    assert "cells total" in r.stdout
    assert "adversarial" in r.stdout


def test_matrix_is_deterministic_same_as_of() -> None:
    a = run_tool("isolation_matrix.py", "--repo", str(REPO), "--as-of",
                 "2026-09-10", "--json")
    b = run_tool("isolation_matrix.py", "--repo", str(REPO), "--as-of",
                 "2026-09-10", "--json")
    assert a.stdout == b.stdout, "two runs with the same --as-of must be byte-identical"


def test_matrix_check_is_diff_clean() -> None:
    r = run_tool("isolation_matrix.py", "--repo", str(REPO), "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_matrix_empty_fake_set_fails(tmp_path: Path) -> None:
    # A matrix whose only mechanism is browser-mode executes zero fake cells:
    # the empty-run law must fail it.
    m = tmp_path / "matrix.yaml"
    m.write_text(
        "schema_version: 1\n"
        "identities:\n"
        "  - {id: a, vid: 'xr:00000000-0000-4000-8000-000000000001'}\n"
        "identity_pairs:\n  - [a, a]\n"
        "mechanisms:\n"
        "  - {id: cookies-1p, mode: browser, question: q}\n"
        "adversarial: {rounds: 1, seed: 1}\n", encoding="utf-8")
    r = run_tool("isolation_matrix.py", "--repo", str(REPO),
                 "--matrix", str(m))
    assert r.returncode == 1
    assert "required minimum" in r.stdout


def test_ledger_happy_path() -> None:
    r = run_tool("exception_ledger_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr


def test_ledger_missing_row_fails(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limitations.md").write_text(
        "## §1.13 exception ledger rows\n"
        "| mechanism | owner | expiry | note |\n|---|---|---|---|\n"
        "| dns-cache-observable | owner | 2027-01-01 | n |\n",
        encoding="utf-8")
    mj = tmp_path / "matrix.json"
    mj.write_text(json.dumps({"cells": [
        {"mechanism": "gpu-texture-side-channel", "verdict": "EXCEPTION"}]}),
        encoding="utf-8")
    r = run_tool("exception_ledger_check.py", "--repo", str(tmp_path),
                 "--matrix-json", str(mj))
    assert r.returncode == 1
    assert "no §1.13 ledger row" in r.stdout


def test_ledger_orphan_row_fails(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limitations.md").write_text(
        "## §1.13 exception ledger rows\n"
        "| mechanism | owner | expiry | note |\n|---|---|---|---|\n"
        "| stale-mech | owner | 2027-01-01 | n |\n", encoding="utf-8")
    mj = tmp_path / "matrix.json"
    mj.write_text(json.dumps({"cells": []}), encoding="utf-8")
    r = run_tool("exception_ledger_check.py", "--repo", str(tmp_path),
                 "--matrix-json", str(mj))
    assert r.returncode == 1
    assert "orphan" in r.stdout


def test_ledger_expired_row_fails(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "limitations.md").write_text(
        "## §1.13 exception ledger rows\n"
        "| mechanism | owner | expiry | note |\n|---|---|---|---|\n"
        "| gpu-texture-side-channel | owner | 2020-01-01 | n |\n",
        encoding="utf-8")
    mj = tmp_path / "matrix.json"
    mj.write_text(json.dumps({"cells": [
        {"mechanism": "gpu-texture-side-channel", "verdict": "EXCEPTION"}]}),
        encoding="utf-8")
    r = run_tool("exception_ledger_check.py", "--repo", str(tmp_path),
                 "--matrix-json", str(mj))
    assert r.returncode == 1
    assert "past" in r.stdout
