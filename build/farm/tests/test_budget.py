"""build/farm/tests/test_budget.py — the patch-budget meter (P12-CLOSE T0-U3).

The meter's unit is FILES, derived from each patch dir's *.patch diff headers;
the patch-entry count is a second reported column, never a budget unit. This
file proves both the legacy shape (totals/caps) and the T0-U3 wire shape: a
30-file patch is red, the same 30 files split across 2 patches is STILL red
(so it is not counting entries), 24 files is green, and an underivable file
set is a failure, never a silent zero.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
METER = HERE.parent / "budget_meter.py"


def _run(m: Path, *extra) -> tuple[int, dict]:
    r = subprocess.run([sys.executable, str(METER), "budget",
                        "--manifest", str(m), "--json", *extra],
                       capture_output=True, text=True)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else {})


def _manifest(tmp_path: Path, n: int, split: int = 1) -> Path:
    """A synthetic blink_seams manifest whose `split` patches together touch
    `n` DISTINCT files (the T0-U3 wire shape)."""
    root = tmp_path / f"m{n}-{split}"
    root.mkdir(exist_ok=True)
    rows = []
    per = n // split
    for s in range(split):
        d = root / "p" / str(s)
        d.mkdir(parents=True, exist_ok=True)
        lo = s * per
        hi = lo + (n - lo if s == split - 1 else per)
        lines = []
        ids = []
        for i in range(lo, hi):
            ids.append(f"f{i}.cc")
            lines += [f"diff --git a/f{i}.cc b/f{i}.cc",
                      "index 1111111..2222222 100644",
                      f"--- a/f{i}.cc", f"+++ b/f{i}.cc",
                      "@@ -1 +1 @@", "-x", "+y"]
        (d / f"{s}.patch").write_text("\n".join(lines) + "\n")
        rows.append(f'  - id: "b-{s}"\n    owner: "@xr/platform"\n'
                    f"    category: blink_seams\n"
                    f"    files: [{', '.join(ids)}]\n    dir: p/{s}")
    m = root / "manifest.yaml"
    m.write_text("schema_version: 1\ntotal_cap: 150\ncategories:\n"
                 "  blink_seams: { cap: 25 }\npatches:\n"
                 + "\n".join(rows) + "\n")
    return m


def test_budget_reports_total_and_caps():
    from categories import PLAN_CAPS, TOTAL_CAP
    assert TOTAL_CAP == 150
    assert PLAN_CAPS["hook_points"] == 45
    assert PLAN_CAPS["branding"] is None


def test_budget_meter_reports(tmp_path):
    """Legacy shape, now file-counted: a 2-file manifest reports total=2."""
    rc, d = _run(_manifest(tmp_path, 2))
    assert rc == 0
    assert d["total"] == 2 and d["cap"] == 150 and d["total_entries"] == 1
    assert d["per_category"]["blink_seams"] == 2


def test_t0u3_thirty_file_patch_is_red(tmp_path):
    rc, d = _run(_manifest(tmp_path, 30), "--gate")
    assert rc == 1 and d["per_category"]["blink_seams"] == 30
    assert d["total_entries"] == 1  # ONE patch, 30 files — the old bug shape


def test_t0u3_split_across_two_patches_still_red(tmp_path):
    """The same 30 files split across 2 patches is STILL red: proves the meter
    counts FILES, not entries (2 entries would have been green before)."""
    rc, d = _run(_manifest(tmp_path, 30, split=2), "--gate")
    assert rc == 1
    assert d["total_entries"] == 2 and d["per_category"]["blink_seams"] == 30


def test_t0u3_twenty_four_files_are_green(tmp_path):
    rc, d = _run(_manifest(tmp_path, 24), "--gate")
    assert rc == 0
    assert d["per_category"]["blink_seams"] == 24


def test_t0u3_underivable_file_set_is_a_failure(tmp_path):
    """Failure-condition 4: a patch with no *.patch is never a silent zero."""
    m = _manifest(tmp_path, 1)
    for pf in m.parent.glob("p/*/*.patch"):
        pf.unlink()
    rc, d = _run(m)
    assert rc == 1
    assert any("underivable" in f for f in d.get("failures", []))


def test_t0u3_diff_headers_are_truth_not_metadata(tmp_path):
    """The `files:` metadata list is NOT the count — the diff headers are."""
    m = _manifest(tmp_path, 4)
    txt = m.read_text().replace(
        "files: [f0.cc, f1.cc, f2.cc, f3.cc]",
        "files: [f0.cc, f1.cc, f2.cc, f3.cc, extra.cc]")
    m.write_text(txt)
    rc, d = _run(m)
    assert rc == 0
    assert d["per_category"]["blink_seams"] == 4
