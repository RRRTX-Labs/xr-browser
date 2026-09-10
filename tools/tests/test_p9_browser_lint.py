"""tools/tests/test_p9_browser_lint.py — P9-T1 browser-test fixture law.

Proves browser_test_lint turns red on each law it enforces: a test that
skips, a test that uses no fixture, a test with no owner, and an empty tree
(the empty-run law). The real xr-core/test/browser tree must stay green.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "browser_test_lint.py"


def run_lint(browser_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--repo", str(browser_dir.parent),
         "--browser-dir", str(browser_dir)],
        capture_output=True, text=True)


def make_tree(tmp_path: Path, test_body: str = "", *, with_owners: bool = True,
              fixture_include: bool = True) -> Path:
    root = tmp_path / "browser"
    fx = root / "fixtures"
    fx.mkdir(parents=True)
    (fx / "xr_browser_test_base.h").write_text("#pragma once\n", encoding="utf-8")
    inc = '#include "test/browser/fixtures/xr_browser_test_base.h"\n' \
        if fixture_include else ""
    src = (f"{inc}"
           f"XR_IN_PROC_BROWSER_TEST(Demo, Name) {{\n{test_body}}}\n")
    (root / "demo_test.cc").write_text(src, encoding="utf-8")
    if with_owners:
        (root / "OWNERS.yaml").write_text(
            "default:\n  owner: \"QA lead\"\npaths: []\n", encoding="utf-8")
    return root


def test_clean_tree_passes(tmp_path: Path) -> None:
    r = run_lint(make_tree(tmp_path, test_body="  ASSERT_TRUE(true);\n"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 violation(s) (PASS)" in r.stdout


def test_gtest_skip_is_forbidden(tmp_path: Path) -> None:
    r = run_lint(make_tree(tmp_path, test_body="  GTEST_SKIP() << \"no\";\n"))
    assert r.returncode == 1
    assert "GTEST_SKIP" in r.stdout


def test_test_without_fixture_include_fails(tmp_path: Path) -> None:
    r = run_lint(make_tree(tmp_path, test_body="  ASSERT_TRUE(true);\n",
                           fixture_include=False))
    assert r.returncode == 1
    assert "no test/browser/fixtures/ header" in r.stdout


def test_test_without_owner_fails(tmp_path: Path) -> None:
    r = run_lint(make_tree(tmp_path, test_body="  ASSERT_TRUE(true);\n",
                           with_owners=False))
    assert r.returncode == 1
    assert "OWNERS.yaml" in r.stdout


def test_empty_tree_fails_empty_run_law(tmp_path: Path) -> None:
    root = tmp_path / "browser"
    root.mkdir()
    r = run_lint(root)
    assert r.returncode == 1
    assert "empty-run law" in r.stdout


def test_real_tree_is_green() -> None:
    repo = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, str(TOOL), "--repo", str(repo)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
