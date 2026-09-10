"""tools/tests/test_p9_leaktest.py — P9-T3 leaktest harness self-verification."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "leaktest.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), "--repo", str(REPO),
                           *args], capture_output=True, text=True)


def test_self_test_passes() -> None:
    r = run("--self-test")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "planted egress detected" in r.stdout


def test_loopback_run_clean_and_counts_cells() -> None:
    r = run("--mode", "loopback")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "30 probe x state cells executed" in r.stdout


def test_loopback_is_deterministic_same_as_of() -> None:
    a = run("--mode", "loopback", "--as-of", "2026-09-10", "--json")
    b = run("--mode", "loopback", "--as-of", "2026-09-10", "--json")
    assert a.stdout == b.stdout


def test_capture_lane_skips_visibly_off_farm() -> None:
    r = run("--mode", "capture")
    # capture is a farm-only lane (docs/qa/leaktest.md: "automatable: no").
    # Off-farm it must SKIP (exit 77) with a visible reason — never a
    # fabricated capture, and never a spurious FAIL: GitHub's ubuntu-latest
    # image ships tcpdump, and a host that merely has tcpdump (without the
    # browser + CAP_NET_RAW farm harness) must not flip this lane to red.
    # The reason names the missing part: tcpdump when absent, farm when present.
    assert r.returncode == 77, r.stdout + r.stderr
    if shutil.which("tcpdump") is None:
        assert "tcpdump" in r.stdout
    else:
        assert "farm" in r.stdout


def test_engine_flags_planted_egress() -> None:
    sys.path.insert(0, str(REPO))
    from build.qa.leaktest import engine
    probes = [engine.Probe(id="p", documented_targets=[])]
    res = engine.run_loopback(probes, ["fresh-profile"],
                              planted={"p": engine.CANARY_HOST})
    assert res["leak_count"] == 1
    assert engine.CANARY_HOST in res["results"][0]["leaks"]


def test_engine_blind_harness_reproduces_clean_lie() -> None:
    sys.path.insert(0, str(REPO))
    from build.qa.leaktest import engine
    probes = [engine.Probe(id="p", documented_targets=[])]
    res = engine.run_loopback(probes, ["fresh-profile"],
                              planted={"p": engine.CANARY_HOST}, blind=True)
    # The blind harness ignores the planted egress => a clean "lie"; the
    # self-test's check 2 is what turns this state into a non-zero exit.
    assert res["ok"] is True
