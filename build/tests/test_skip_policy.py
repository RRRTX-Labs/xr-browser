"""build/tests/test_skip_policy.py — the optional-external-tool policy (P4-T0.1).

The debt this closes: `./scripts/build test` on a bare clone FAILED
(test_fastlane_drills -> FileNotFoundError: 'minisign'), which turned every
hosted CI run red. The fix is NOT deleting the test and NOT faking the
signature: it is a SKIP that is visible in the run summary (L6).

Cases proven here:
  * absent tool  -> pytest.skip with "SKIP (tool absent: X)" (never PASS)
  * present tool -> no skip, the real round-trip runs (git is the probe)
  * the summary/CLI surfaces agree with the guard
  * the drill test itself: skip when minisign is absent, full run when present
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_absent_tool_is_a_visible_skip(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    import skip_policy
    with pytest.raises(pytest.skip.Exception) as exc:
        skip_policy.pytest_skip_if_absent("minisign")
    msg = str(exc.value)
    assert msg.startswith("SKIP (tool absent: minisign)")
    assert "needed for:" in msg and "install hint:" in msg


def test_absent_tool_skip_is_not_a_pass(monkeypatch):
    """The SKIP row carries status SKIP — never PASS, never FAIL."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    import skip_policy
    row = skip_policy.skip_record("minisign")
    assert row is not None
    assert row["status"] == "SKIP"
    assert row["tool"] == "minisign"
    assert skip_policy.summary_line(row).startswith("SKIP: SKIP (tool absent: minisign)")


def test_present_tool_does_not_skip():
    """A tool that IS installed must not be skipped (git is everywhere here)."""
    import skip_policy
    assert shutil.which("git"), "git must be installed for this test to mean anything"
    skip_policy.pytest_skip_if_absent("git")          # must not raise
    assert skip_policy.skip_record("git") is None
    # ...and the real round-trip actually runs:
    out = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
    assert out.stdout.startswith("git version")


def test_require_tool_errors_with_install_hint(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    import skip_policy
    sys_path = None
    import sys
    sys.path.insert(0, str(Path(skip_policy.__file__).resolve().parent))
    from _common import ToolError
    with pytest.raises(ToolError) as exc:
        skip_policy.require_tool("minisign")
    assert "not installed" in str(exc.value)
    del sys_path


def test_collect_skips_reports_every_missing_tool(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    import skip_policy
    rows = skip_policy.collect_skips()
    names = {r["tool"] for r in rows}
    assert names == set(skip_policy.EXTERNAL_TOOLS)
    assert all(r["status"] == "SKIP" and r["reason"] for r in rows)


def test_registered_tools_declare_used_for_and_install():
    import skip_policy
    for name, meta in skip_policy.EXTERNAL_TOOLS.items():
        assert meta.get("used_for"), f"{name} has no used_for"
        assert meta.get("install"), f"{name} has no install hint"


def test_helper_tools_doc_lists_every_registered_tool():
    """docs/dependencies/helper-tools.yaml is the rationale home; keep in sync."""
    import yaml
    import skip_policy
    doc = yaml.safe_load(Path("docs/dependencies/helper-tools.yaml").read_text())
    documented = {row["name"] for row in doc.get("tools", [])}
    for name in skip_policy.EXTERNAL_TOOLS:
        assert name in documented, f"{name} used in code but not documented"


def test_fastlane_drill_either_runs_or_skips_visibly(tmp_path, monkeypatch):
    """The drill: full round-trip when minisign exists, visible SKIP otherwise.

    This is the regression test for the P3 debt (bare-clone failure): the
    outcome on any host must be green-and-honest, never red, never silent.
    """
    import rebase_bot
    import fastlane_drills
    xr_root = Path(rebase_bot.__file__).resolve().parents[2]

    if shutil.which("minisign") is None:
        with pytest.raises(pytest.skip.Exception) as exc:
            fastlane_drills.run_drill(out_dir=tmp_path / "drill-skip", root=xr_root,
                                      label="absent-tool", published_hours_ago=30.0,
                                      expect_breach=False, guard=True)
        assert str(exc.value).startswith("SKIP (tool absent: minisign)")
        return

    ok = fastlane_drills.run_drill(out_dir=tmp_path / "drill1", root=xr_root,
                                   label="in-window", published_hours_ago=30.0,
                                   expect_breach=False, guard=True)
    assert ok["verdict"] == "PASS"
    assert ok["source"] == "fixture" and ok["simulated"] is True
