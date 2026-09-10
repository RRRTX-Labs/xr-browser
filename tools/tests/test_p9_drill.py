"""tools/tests/test_p9_drill.py — P9-T10/T11: kill matrix + update drill data."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True)


def test_drill_check_green() -> None:
    r = run_tool("drill_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout


def test_kill_matrix_names_all_eight_processes() -> None:
    doc = yaml.safe_load(
        (REPO / "build/qa/drill/kill-matrix.yaml").read_text())
    procs = [r["process"] for r in doc["rows"]]
    assert procs == ["browser", "renderer", "network", "vaultd", "tord",
                     "wgd", "inspect", "gpu"]
    for r in doc["rows"]:
        assert r["assertions"], r


def test_update_drill_names_all_three_os() -> None:
    doc = yaml.safe_load(
        (REPO / "build/qa/drill/update-drill.yaml").read_text())
    assert [r["os"] for r in doc["rows"]] == ["linux", "macos", "windows"]
    for r in doc["rows"]:
        assert r["assertions"] and r["kill_point"], r


def test_kill_matrix_canary_bites(tmp_path: Path) -> None:
    # a matrix with a missing assertion must fail the gate (empty-run canary)
    empty = tmp_path / "kill-empty.yaml"
    empty.write_text("schema_version: 1\nrows:\n"
                     "  - process: browser\n    kill: SIGKILL\n"
                     "    assertions: []\n", encoding="utf-8")
    r = run_tool("drill_check.py", "--repo", str(REPO),
                 "--kill-matrix", str(empty))
    assert r.returncode == 1
    assert "no assertions" in r.stdout


def test_drill_runner_skip_visible() -> None:
    r = subprocess.run(["bash", str(REPO / "build/qa/drill/drill_run.sh"),
                        "kill-matrix"], capture_output=True, text=True)
    assert r.returncode == 77
    assert "SKIP" in (r.stdout + r.stderr)
