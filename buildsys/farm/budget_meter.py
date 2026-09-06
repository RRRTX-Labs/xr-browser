"""buildsys/farm/budget_meter.py — the patch-budget meter (Plan P2-T10).

Counts xr-core patch-manifest entries, prints {total, per_category, cap: 150}
as JSON + a markdown table, and writes budget-report.{json,md} artifacts.

REPORT-ONLY this phase (P2): it exits 0 and records `over_budget`, it does NOT
block. P3-T3 turns it into a hard CI gate. The *data-level* rejection (entry
count > 150, per-category overflow) is already enforced today by
`xr-patch lint` (buildsys/patching/apply.py) — see docs/contracts/patch-manifest-v1.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patching"))

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root  # noqa: E402
from categories import PLAN_CAPS, TOTAL_CAP  # noqa: E402

DEFAULT_MANIFEST = "../xr-core/patches/manifest.yaml"  # relative to meta repo root


def main() -> None:
    parser = argparse.ArgumentParser(prog="buildsys/farm/budget_meter.py",
                                     description="Count patch-manifest entries vs the §1.2 budget (report-only).")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="path to xr-core patches/manifest.yaml")
    parser.add_argument("--report-dir", default=None, help="write budget-report.{json,md} into this dir")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        root = repo_root()
        mpath = (root / args.manifest).resolve()
        if not mpath.exists():
            raise ToolError(f"manifest not found: {mpath}")
        import yaml
        manifest = yaml.safe_load(mpath.read_text(encoding="utf-8"))
        patches = manifest.get("patches") or []
        per: dict[str, int] = {c: 0 for c in PLAN_CAPS}
        for p in patches:
            cat = p.get("category")
            if cat in per:
                per[cat] += 1
        total = len(patches)
        report = {
            "tool": "budget_meter",
            "total": total,
            "per_category": per,
            "cap": TOTAL_CAP,
            "category_caps": {c: (cap if cap is not None else "unlimited") for c, cap in PLAN_CAPS.items()},
            "over_budget": total > TOTAL_CAP,
            "report_only": True,
        }
        md = ["| category | patches | cap |", "|---|---|---|"]
        for c, n in sorted(per.items()):
            cap = PLAN_CAPS[c]
            md.append(f"| {c} | {n} | {cap if cap is not None else 'unlimited'} |")
        md.append(f"| **total** | **{total}** | **{TOTAL_CAP}** |")
        table = "\n".join(md) + "\n"

        if args.report_dir:
            d = Path(args.report_dir)
            d.mkdir(parents=True, exist_ok=True)
            (d / "budget-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            (d / "budget-report.md").write_text(f"# Patch-budget report (report-only, P2)\n\n{table}", encoding="utf-8")
            report["report_dir"] = str(d)

        if not args.json:
            print(table.rstrip())
        return emit(args.json, report)

    main_with_guard(run)


if __name__ == "__main__":
    main()
