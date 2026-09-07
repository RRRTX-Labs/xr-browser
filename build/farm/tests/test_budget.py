import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
METER = HERE.parent / "budget_meter.py"


def test_budget_reports_total_and_caps():
    from categories import PLAN_CAPS, TOTAL_CAP
    assert TOTAL_CAP == 150
    assert PLAN_CAPS["hook_points"] == 45
    assert PLAN_CAPS["branding"] is None


def test_budget_meter_reports(tmp_path):
    # a manifest with 2 patches in two categories
    m = tmp_path / "manifest.yaml"
    m.write_text(
        "schema_version: 1\ntotal_cap: 150\n"
        "categories:\n  branding: { cap: null }\n  hook_points: { cap: 45 }\n"
        "patches:\n  - {id: a, owner: o, category: branding, files: [f], dir: d}\n"
        "  - {id: b, owner: o, category: hook_points, files: [f], dir: d}\n")
    r = subprocess.run([sys.executable, str(METER), "--manifest", str(m), "--json",
                        "--report-dir", str(tmp_path / "report")],
                       capture_output=True, text=True)
    assert r.returncode == 0
    import json
    d = json.loads(r.stdout)
    assert d["total"] == 2 and d["cap"] == 150
    assert d["per_category"]["branding"] == 1 and d["per_category"]["hook_points"] == 1
    assert (tmp_path / "report" / "budget-report.json").exists()
