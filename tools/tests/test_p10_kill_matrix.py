"""tools/tests/test_p10_kill_matrix.py — the hosts-local drill runner (T0-b).

Canaries for tools/kill_matrix.py: discovery is real (finds the four hosts),
the zero-case law bites (an xr-core with no hosts fails closed), the runner
is deterministic under a fixed seed, and the honest not-run split is printed.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"

_spec = importlib.util.spec_from_file_location(
    "kill_matrix", REPO / "tools" / "kill_matrix.py")
km = importlib.util.module_from_spec(_spec)
sys.modules["kill_matrix"] = km
_spec.loader.exec_module(km)


@pytest.mark.skipif(not XR_CORE.exists(), reason="sibling xr-core checkout absent")
def test_discovery_finds_the_four_shipped_hosts():
    hosts = km.discover_hosts(XR_CORE)
    names = {h["name"] for h in hosts}
    assert {"policy", "commands", "settings", "themes"} <= names, names
    for h in hosts:
        assert h["bin"].name.endswith("_host")


def test_discovery_fails_closed_on_an_empty_core(tmp_path):
    with pytest.raises(km.RunnerError, match="certify nothing"):
        km.discover_hosts(tmp_path)


@pytest.mark.skipif(not XR_CORE.exists(), reason="sibling xr-core checkout absent")
def test_drill_executes_cells_and_prints_the_split(capsys):
    km.XR_CORE = XR_CORE
    import random
    km.XR_CORE = XR_CORE
    rng = random.Random("20260910")
    hosts = km.discover_hosts(XR_CORE)
    result = km.run_host_matrix(hosts, rng, iterations=1)
    executed = [c for c in result["cells"] if c["status"] == "executed"]
    notrun = [c for c in result["cells"] if c["status"] == "not-run"]
    assert executed, "0 executed cells — the drill certified nothing"
    assert notrun, "the farm rows must stay visible in the not-run split"
    # the policy host honestly reports its missing binary write mode
    policy_write = [c for c in notrun if c["host"] == "policy" and c["phase"] == "mid-write"]
    assert policy_write and "no binary write mode" in policy_write[0]["reason"]


@pytest.mark.skipif(not XR_CORE.exists(), reason="sibling xr-core checkout absent")
def test_zero_case_law_bites():
    with pytest.raises(km.RunnerError, match="certifies nothing"):
        km.require_cases(0, "kill-matrix")


def test_runner_file_under_loc_law():
    loc = (REPO / "tools" / "kill_matrix.py").read_text(encoding="utf-8").count("\n")
    assert loc < 400, f"kill_matrix.py at {loc} LOC — the 400 ceiling is law"
