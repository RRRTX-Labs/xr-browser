"""tools/tests/test_p9_perf.py — P9-T5 perf budget service laws."""
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


def bench_file(tmp_path: Path, rows: list[dict], rig_class: str = "trend",
               name: str = "syn") -> Path:
    p = tmp_path / "bench.json"
    p.write_text(json.dumps({"name": name, "rig_class": rig_class,
                             "rows": rows}), encoding="utf-8")
    return p


def core_row(value_us: float, budget_us: float = 200.0) -> dict:
    return {"metric": "resolve_cold_us", "value_us": value_us,
            "budget_us": budget_us}


def test_generator_check_is_diff_clean() -> None:
    r = subprocess.run([sys.executable, str(REPO / "build/qa/perf/gen_perf_budgets.py"),
                        "--repo", str(REPO), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_met_within_budget(tmp_path: Path) -> None:
    b = bench_file(tmp_path, [core_row(100.0)])
    r = run_tool("perf_gate.py", "--repo", str(REPO), "--bench", str(b))
    assert r.returncode == 0, r.stdout
    assert "MET" in r.stdout


def test_within_noise_band_is_neutral_not_met(tmp_path: Path) -> None:
    # 1.5% over budget => inside the 2% noise band => NEUTRAL (never MET).
    b = bench_file(tmp_path, [core_row(200.0 * 1.015)])
    r = run_tool("perf_gate.py", "--repo", str(REPO), "--bench", str(b))
    assert r.returncode == 0
    assert "NEUTRAL" in r.stdout and "MET" not in r.stdout


def test_ten_percent_regression_trips(tmp_path: Path) -> None:
    b = bench_file(tmp_path, [core_row(200.0 * 1.10)])
    r = run_tool("perf_gate.py", "--repo", str(REPO), "--bench", str(b))
    assert r.returncode == 1
    assert "MISSED" in r.stdout


def test_trend_rig_refused_on_browser_side_row(tmp_path: Path) -> None:
    b = bench_file(tmp_path, [{"metric": "ntp_interactive_ms",
                               "value_us": 100, "budget_us": 300}],
                   rig_class="trend")
    r = run_tool("perf_gate.py", "--repo", str(REPO), "--bench", str(b))
    assert r.returncode == 1
    assert "rig-class law" in r.stdout


def test_empty_input_fails(tmp_path: Path) -> None:
    b = bench_file(tmp_path, [])
    r = run_tool("perf_gate.py", "--repo", str(REPO), "--bench", str(b))
    assert r.returncode == 1
    assert "required minimum" in r.stdout or "no value" in r.stdout


def test_real_benches_pass_on_trend_rig() -> None:
    r = run_tool("perf_gate.py", "--repo", str(REPO),
                 "--bench", str(REPO / "../xr-core/policy/tests/build/bench-results.json"),
                 "--bench", str(REPO / "../xr-core/themes/tests/bench-results.json"))
    assert r.returncode == 0, r.stdout
    assert "rig trend" in r.stdout
