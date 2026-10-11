"""P15-CLOSE C11: a mutant that makes a suite hang is a kill, not a harness crash.

The full settings matrix at xr-core c9c51d8 found a mutant that sent
test_settings_search into a loop. run_suites() let subprocess.TimeoutExpired
escape, which aborted the whole run with no report. The suite timeout now
counts as killed and is labelled killed(timeout). The real tests below run a
hanging suite and a passing suite through run_suites() itself.
"""
from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "mutation_test.py"


def _load():
    spec = importlib.util.spec_from_file_location("mutation_test_c11", TOOL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _suite(tmp: Path, name: str, body: str) -> None:
    build = tmp / "core1" / "tests" / "build"
    build.mkdir(parents=True, exist_ok=True)
    exe = build / name
    exe.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)


def test_hanging_suite_is_killed_not_a_crash(tmp_path: Path) -> None:
    mt = _load()
    mt.SUITE_TIMEOUT_S = 1
    _suite(tmp_path, "hang", "sleep 30")
    killed, log = mt.run_suites(tmp_path, "core1", ["hang"], "")
    assert killed is True
    assert "[hang] TIMEOUT after 1 s" in log


def test_passing_suite_still_survives(tmp_path: Path) -> None:
    """Control: the timeout path does not turn a clean suite into a kill."""
    mt = _load()
    mt.SUITE_TIMEOUT_S = 5
    _suite(tmp_path, "ok", "exit 0")
    killed, log = mt.run_suites(tmp_path, "core1", ["ok"], "")
    assert killed is False
    assert "TIMEOUT" not in log
