"""build/upstream/gen_budget_config.py — transcribe Plan §1.2's budget table
into build/upstream/budget-config.json (P3-T3).

Budget enforcement must be data-driven from the PINNED plan (phase prompt:
"transcribe §1.2's table (total ≤150 + per-category caps) from the pinned
plan into a generated config; cross-check P2's build/patching/categories.py
against it and correct if drifted (say which in evidence)").

This generator parses the markdown table in the pinned plan file directly, so
the transcription is mechanically verifiable:

    python3 build/upstream/gen_budget_config.py            # write the config
    python3 build/upstream/gen_budget_config.py --check    # CI: committed file
                                                           # matches the plan

It then cross-checks build/patching/categories.py (PLAN_CAPS/TOTAL_CAP) and
fails on drift — the two cap sources may never diverge silently.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard, repo_root  # noqa: E402

CONFIG_PATH = Path("build/upstream/budget-config.json")

# Plan §1.2 row label (fuzzy prefix) -> manifest category key
ROW_MAP = [
    ("branding/defaults", "branding"),
    ("hook points", "hook_points"),
    ("blink seams", "blink_seams"),
    ("content/ seam uses", "content_seams"),
    ("networkservice seam", "network_seams"),
    ("ui (", "ui"),
    ("extension function chokepoint", "extension_chokepoint"),
]


def parse_plan_table(plan_text: str) -> dict[str, int | None]:
    """Extract the §1.2 budget table: category -> cap (None = unlimited-ish)."""
    section = re.search(
        r"## 1\.2 Chromium strategy.*?\| Patch class \| Budget \| Rules \|.*?\n(.*?)\n\n",
        plan_text, re.S)
    if not section:
        raise ToolError("could not locate the §1.2 patch-budget table in the plan")
    caps: dict[str, int | None] = {}
    for line in section.group(1).splitlines():
        if not line.startswith("|") or "never patched" in line.lower():
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        label, budget = cells[0].lower(), cells[1]
        for prefix, key in ROW_MAP:
            if label.startswith(prefix):
                if "unlimited" in budget.lower():
                    caps[key] = None
                else:
                    m = re.search(r"\d+", budget.replace(",", ""))
                    if not m:
                        raise ToolError(f"§1.2 row {label!r}: no cap in {budget!r}")
                    caps[key] = int(m.group(0))
                break
    if len(caps) != len(ROW_MAP):
        raise ToolError(f"§1.2 parse incomplete: got {caps}")
    return caps


def parse_total_cap(plan_text: str) -> int:
    m = re.search(r"\*\*Total upstream-touched files\*\* \| \*\*≤(\d+),", plan_text)
    if not m:
        m = re.search(r"Total upstream-touched files.*?≤\s*(\d+)", plan_text)
    if not m:
        raise ToolError("could not parse the §1.2 total cap")
    return int(m.group(1))


def build_config(root: Path) -> dict:
    plan = (root / "docs" / "plans" / "XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md").read_text(encoding="utf-8")
    caps = parse_plan_table(plan)
    total = parse_total_cap(plan)
    return {
        "schema_version": 1,
        "source": "docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md §1.2 (pinned, sha-checked by tools/plan_pin_check.py)",
        "total_cap": total,
        "caps": caps,
        "rules": {
            "unregistered_diff": "any diff in src/ outside src/xr not registered in the manifest fails CI (Plan §12.2)",
            "count_published": "patch count published in every release note (Plan §12.2)",
            "exceeding_budget": "exceeding budget = architecture review, never silent scope (Plan §1.2)",
        },
    }


def cross_check_categories(config: dict) -> list[str]:
    """The §1.2 caps must equal build/patching/categories.py — drift fails."""
    sys.path.insert(0, str(repo_root() / "build" / "patching"))
    from categories import PLAN_CAPS, TOTAL_CAP  # noqa: E402
    drift: list[str] = []
    if TOTAL_CAP != config["total_cap"]:
        drift.append(f"total cap: categories.py={TOTAL_CAP} plan={config['total_cap']}")
    for key, cap in config["caps"].items():
        if PLAN_CAPS.get(key) != cap:
            drift.append(f"category {key}: categories.py={PLAN_CAPS.get(key)!r} plan={cap!r}")
    for key in PLAN_CAPS:
        if key not in config["caps"]:
            drift.append(f"category {key} exists in categories.py but not in the plan table")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gen-budget-config",
        description="Transcribe the pinned plan §1.2 budget table into "
                    "build/upstream/budget-config.json and cross-check categories.py.")
    parser.add_argument("--check", action="store_true",
                        help="verify the committed config matches the plan + categories.py (CI)")
    args = parser.parse_args()

    root = repo_root()
    config = build_config(root)
    drift = cross_check_categories(config)
    if drift:
        for d in drift:
            print(f"FAIL: budget drift — {d}")
        print("FAIL: build/patching/categories.py diverges from the pinned plan §1.2")
        return 1

    out = root / CONFIG_PATH
    if args.check:
        committed = json.loads(out.read_text(encoding="utf-8"))
        if committed != config:
            print("FAIL: committed build/upstream/budget-config.json is stale vs the pinned plan")
            print("      regenerate: python3 build/upstream/gen_budget_config.py")
            return 1
        print("PASS: budget config matches the pinned plan §1.2 and categories.py")
        return 0

    out.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CONFIG_PATH} (total {config['total_cap']}, "
          f"{len(config['caps'])} categories; categories.py cross-check clean)")
    return 0


if __name__ == "__main__":
    main_with_guard(lambda: main())
