"""tools/tests/test_p9_surfaces.py — P9-T12: §11 surface-completeness gate."""
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


def test_surfaces_check_green() -> None:
    r = run_tool("surfaces_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout


def test_all_fifteen_surfaces_present() -> None:
    doc = yaml.safe_load(
        (REPO / "docs/qa/surfaces.yaml").read_text(encoding="utf-8"))
    ids = [s["id"] for s in doc["surfaces"]]
    assert ids == [f"11.{i}" for i in range(1, 16)]
    for s in doc["surfaces"]:
        assert s.get("green"), f"{s['id']} has no green clause"


def test_every_tool_home_resolves() -> None:
    doc = yaml.safe_load(
        (REPO / "docs/qa/surfaces.yaml").read_text(encoding="utf-8"))
    for s in doc["surfaces"]:
        if s["home"] == "tool":
            for t in s["tools"]:
                assert (REPO / t).exists(), f"{s['id']}: {t} missing"


def test_manual_surface_rows_owned_and_scheduled() -> None:
    doc = yaml.safe_load(
        (REPO / "docs/qa/surfaces.yaml").read_text(encoding="utf-8"))
    manual = [s for s in doc["surfaces"] if s["home"] == "manual"]
    assert manual
    for s in manual:
        for r in s["rows"]:
            assert r.get("owner") and r.get("cadence"), r


def test_surface_without_home_is_red(tmp_path: Path) -> None:
    # the plan's stop-condition: a surface with no home must fail the gate
    (tmp_path / "surfaces.yaml").write_text(
        "schema_version: 1\nsurfaces:\n"
        "  - id: \"11.1\"\n    name: unit\n    green: \"x\"\n",
        encoding="utf-8")
    r = run_tool("surfaces_check.py", "--repo", str(REPO),
                 "--surfaces", str(tmp_path / "surfaces.yaml"))
    assert r.returncode == 1
    assert "no home" in r.stdout
