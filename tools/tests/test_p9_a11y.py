"""tools/tests/test_p9_a11y.py — P9-T7 a11y lane: copy lint, allowlist, AXTree."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True)


def test_npm_allowlist_green_on_real_lockfile() -> None:
    r = run_tool("npm_allowlist_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout


def test_npm_allowlist_flags_unknown_package(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"packages": {
        "": {"name": "x"},
        "node_modules/evil-pkg": {"version": "1.0.0"},
        "node_modules/lit": {"version": "3.3.3"}}}), encoding="utf-8")
    allow = tmp_path / "npm-allowlist.json"
    allow.write_text(json.dumps({"schema_version": 1, "packages": [
        {"name": "lit", "match": "exact", "version": "3.3.3",
         "license": "BSD", "role": "r", "docs": "d"}]}), encoding="utf-8")
    r = run_tool("npm_allowlist_check.py", "--repo", str(REPO),
                 "--lockfile", str(lock), "--allowlist", str(allow))
    assert r.returncode == 1
    assert "evil-pkg" in r.stdout


def test_copy_lint_green_on_real_grdp() -> None:
    r = run_tool("copy_lint.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout


def test_copy_lint_flags_score_looking_number(tmp_path: Path) -> None:
    # a score-looking number must be caught; a unit-bearing number must not
    (tmp_path / "xr_strings.grdp").write_text(
        '<message name="M1" xr-id="a">Protection score is 9/10</message>\n'
        '<message name="M2" xr-id="b">Border is 2 px</message>\n',
        encoding="utf-8")
    r = run_tool("copy_lint.py", "--repo", str(REPO),
                 "--grdp", str(tmp_path / "xr_strings.grdp"))
    assert r.returncode == 1
    assert "9/10" in r.stdout and "2 px" not in r.stdout


def test_a11y_tree_golden_diff_clean() -> None:
    r = run_tool("a11y_tree.py", "--repo", str(REPO), "--check")
    assert r.returncode == 0, r.stdout


def test_a11y_tree_self_test() -> None:
    r = run_tool("a11y_tree.py", "--repo", str(REPO), "--self-test")
    assert r.returncode == 0, r.stdout


def test_keyboard_tasks_gate() -> None:
    r = run_tool("keyboard_tasks_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout
    assert "12 task(s)" in r.stdout
