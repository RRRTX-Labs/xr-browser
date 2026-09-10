"""tools/tests/test_p9_compat.py — P9-T4 compat corpus + WPT delta bot."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"


def run_tool(name: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    import os
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True, env=e)


def test_corpus_validate_and_replay_pass() -> None:
    assert run_tool("compat.py", "--repo", str(REPO), "validate").returncode == 0
    assert run_tool("compat.py", "--repo", str(REPO), "replay").returncode == 0


def test_live_mode_refused_without_env() -> None:
    r = run_tool("compat.py", "--repo", str(REPO), "live", "https://example.com")
    assert r.returncode == 77
    assert "XR_LIVE_NET" in r.stdout


def test_live_mode_refused_for_unallowlisted_host_with_env() -> None:
    r = run_tool("compat.py", "--repo", str(REPO), "live", "https://example.com",
                 env={"XR_LIVE_NET": "1"})
    assert r.returncode == 1
    assert "not on the fetch allowlist" in r.stdout


def test_corpus_empty_entries_fails(tmp_path: Path) -> None:
    sys.path.insert(0, str(TOOLS))
    import compat
    fails = compat.validate(tmp_path, {"schema_version": 1, "entries": []})
    assert any("empty-run law" in f for f in fails)


def test_replay_fixture_that_does_not_exercise_class_fails(tmp_path: Path) -> None:
    # compat.py resolves fixtures at <repo>/../xr-core/test/corpus/replay-fixtures
    browser = tmp_path / "xr-browser"
    browser.mkdir()
    fx = tmp_path / "xr-core" / "test" / "corpus" / "replay-fixtures"
    fx.mkdir(parents=True)
    (fx / "login.html").write_text("<html><body><p>nothing</p></body></html>",
                                   encoding="utf-8")
    sys.path.insert(0, str(TOOLS))
    import compat
    corpus = {"schema_version": 1, "entries": [
        {"id": "x", "class": "hardapp", "url_class": "login-flow",
         "flows": [], "expectations": {"console": "clean"}, "owner": "o",
         "provenance": "p", "mode": "expectations-only", "replay": "login.html"}]}
    fails = compat.replay(browser, corpus)
    assert any("does not exercise class" in f for f in fails)


def test_wpt_delta_within_tolerance() -> None:
    r = run_tool("wpt_delta.py",
                 str(REPO / "docs/qa/wpt-fixtures/baseline.json"),
                 str(REPO / "docs/qa/wpt-fixtures/within-tolerance.json"))
    assert r.returncode == 0
    assert "WITHIN-TOLERANCE" in r.stdout


def test_wpt_delta_regression_exceeds_threshold() -> None:
    r = run_tool("wpt_delta.py",
                 str(REPO / "docs/qa/wpt-fixtures/baseline.json"),
                 str(REPO / "docs/qa/wpt-fixtures/regression.json"))
    assert r.returncode == 1
    assert "REGRESSION" in r.stdout


def test_wpt_delta_empty_input_fails(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"name": "a", "tests": {}}), encoding="utf-8")
    r = run_tool("wpt_delta.py", str(a), str(a))
    assert r.returncode == 1
    assert "empty-run law" in r.stdout


def test_wpt_delta_flaky_excluded_by_rule() -> None:
    base = {"name": "b", "tests": {"p/t1": "PASS", "p/flaky1": "FLAKY"}}
    cand = {"name": "c", "tests": {"p/t1": "PASS", "p/flaky1": "FAIL"}}
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        b = Path(td) / "b.json"
        c = Path(td) / "c.json"
        b.write_text(json.dumps(base), encoding="utf-8")
        c.write_text(json.dumps(cand), encoding="utf-8")
        r = run_tool("wpt_delta.py", str(b), str(c))
    assert r.returncode == 0
    assert "WITHIN-TOLERANCE" in r.stdout
