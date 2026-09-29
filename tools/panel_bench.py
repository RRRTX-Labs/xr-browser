#!/usr/bin/env python3
"""tools/panel_bench.py — the P13-T7 panel bench driver (surrogate, trend only).

It bundles xr-core/ui/panel/focus-trap.ts with the PINNED toolchain into a
scratch directory outside both repos, runs the panel's bench harness
(xr-core/ui/panel/tests/panel-bench.mjs) under node, and emits the normalized
tools/perf_gate.py row shape.

What it measures, and what it refuses to claim:

  * ``panel_open_core_ms`` — the FRAME'S PURE CORE on the open path, over a
    4096-focusable synthetic document. This is a SUBSET of the plan's browser
    budget (§4 P13 Perf: "open ≤150 ms"): no layout, no style, no paint. The
    budget row for it is emitted by build/qa/perf/gen_perf_budgets.py from the
    plan text, carries ``assert_class: trend``, and the comparator's rig-class
    law means a trend rig may never read MET (a planted bench keeps that
    refusal red: tools/negatives/p13_t7.sh).
  * ``panel_open_subtree_scans`` — a deterministic COUNT (how many subtree
    reads the open path performs). This is the "lazy tabs" property measured
    without a clock: the frame reads its own subtree and never walks the
    document. A count cannot flake, so the claim does not depend on the box it
    ran on. No budget row exists for it on purpose — a cap would be invented,
    and the comparator shows it as RECORD-ONLY.
  * The browser-side halves — real open latency, ring scroll frame time,
    geometry at 360 px — are NOT-RUN here with their method recorded in
    docs/qa/browser-harness.md (#panel-open-150ms). A surrogate never dresses
    itself as the real rig.

Modes: no flag = measure; --merge-trend = fold the measured rows into
docs/state/bench-trend.json (the committed trend input the P9-T5 lane reads);
--check = verify that file already carries these rows (no re-measurement, so
the gate stays deterministic); --json = machine output.

Exit: 0 pass · 1 fail · 2 usage · 77 visible skip (node/toolchain absent).
Stdlib only; no wall clock in any verdict.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77
REPO = Path(__file__).resolve().parents[1]
TREND = REPO / "docs" / "state" / "bench-trend.json"
# The naming convention this repo already uses (cosmetic_*): `value_us`
# carries the number in the BUDGET'S unit, so a ms budget compares against a
# ms value with no conversion hiding in the comparator.
METRICS = ("panel_open_core_ms", "panel_open_subtree_scans")
BENCH_NAME = "panel frame core (surrogate, trend only)"


def core_dir(repo: Path) -> Path:
    return repo.parent / "xr-core"


def bundle_core(core: Path, scratch: Path) -> Path | None:
    """Bundle focus-trap.ts with the pinned toolchain; None when unavailable."""
    toolchain = core / "ui" / "toolchain"
    esbuild = toolchain / "node_modules" / ".bin" / "esbuild"
    src = core / "ui" / "panel" / "focus-trap.ts"
    if not esbuild.exists() or not src.is_file():
        return None
    out = scratch / "focus-trap.mjs"
    r = subprocess.run(
        [str(esbuild), str(src), "--bundle", "--format=esm", "--platform=neutral",
         "--target=es2022", f"--outfile={out}", "--log-level=warning"],
        capture_output=True, text=True, cwd=str(toolchain), timeout=300)
    if r.returncode != 0 or not out.is_file():
        return None
    return out


def measure(repo: Path) -> dict | None:
    core = core_dir(repo)
    harness = core / "ui" / "panel" / "tests" / "panel-bench.mjs"
    if not harness.is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="xr-panel-bench.") as tmp:
        scratch = Path(tmp)
        bundle = bundle_core(core, scratch)
        if bundle is None:
            return None
        r = subprocess.run(["node", str(harness)], capture_output=True,
                           text=True, timeout=600,
                           env={"XR_PANEL_TRAP_BUNDLE": str(bundle),
                                "PATH": "/usr/bin:/bin:/usr/local/bin"})
        if r.returncode != 0:
            print(f"panel_bench: harness failed: {r.stderr.strip()[:400]}",
                  file=sys.stderr)
            return None
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print("panel_bench: harness output was not JSON", file=sys.stderr)
            return None
    return {"name": BENCH_NAME, "rig_class": "trend",
            "rows": [
                {"metric": "panel_open_core_ms", "unit": "ms",
                 "value_us": data["panel_open_core_us"]["value_us"] / 1000.0,
                 "n": data["panel_open_core_us"]["n"], "sampled": True,
                 "surrogate": True},
                {"metric": "panel_open_subtree_scans", "unit": "scans",
                 "value_us": data["panel_open_subtree_scans"]["value_us"],
                 "surrogate": True},
            ],
            "notes": {
                "doc_targets": data["doc_targets"],
                "frame_targets": data["frame_targets"],
                "landed_on_open": data["landed_on_open"],
            }}


def merge_trend(bench: dict, path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    kept = [r for r in doc["rows"] if r["metric"] not in METRICS]
    doc["rows"] = kept + bench["rows"]
    doc["notes"] = {**(doc.get("notes") or {}), **bench["notes"]}
    if "panel" not in doc["name"]:
        doc["name"] += " + panel frame core (surrogate)"
    doc["rig_class"] = bench["rig_class"]
    path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")
    print(f"panel_bench: merged {len(bench['rows'])} panel row(s) into {path}")


def check_trend(path: Path) -> int:
    """The gate's deterministic half: the committed trend input carries the
    panel rows, measured values included, without re-measuring."""
    if not path.is_file():
        print(f"panel_bench: FAIL — {path} is missing", file=sys.stderr)
        return EXIT_FAIL
    doc = json.loads(path.read_text(encoding="utf-8"))
    have = {r["metric"]: r for r in doc["rows"]}
    missing = [m for m in METRICS if m not in have]
    if missing:
        print(f"panel_bench: FAIL — {path} is missing {missing} "
              f"(run tools/panel_bench.py --merge-trend)", file=sys.stderr)
        return EXIT_FAIL
    scan = have["panel_open_subtree_scans"]
    core = have["panel_open_core_ms"]
    if not scan.get("surrogate") or not core.get("surrogate"):
        print("panel_bench: FAIL — the panel rows must be marked surrogate "
              "(a surrogate may never pass as a real rig)", file=sys.stderr)
        return EXIT_FAIL
    doc_targets = int(doc.get("notes", {}).get("doc_targets", 0))
    if doc_targets and int(scan["value_us"]) > 2:
        print(f"panel_bench: FAIL — the open path read subtrees {scan['value_us']} "
              f"times over a {doc_targets}-element document: the frame is "
              f"walking more than its own subtree (lazy-tab law)", file=sys.stderr)
        return EXIT_FAIL
    print(f"panel_bench: PASS — committed trend rows present "
          f"(core {core['value_us']:.4f} ms median of {core.get('n')}, "
          f"open path reads {scan['value_us']} subtree(s) of a "
          f"{doc_targets}-element document)")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="panel-bench",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--merge-trend", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()

    if a.check:
        return check_trend(repo / "docs" / "state" / "bench-trend.json")
    if not (Path("/usr/bin/node").exists() or subprocess.run(
            ["sh", "-c", "command -v node"], capture_output=True).returncode == 0):
        print("panel_bench: SKIP (node not installed) — sources shipped")
        return EXIT_SKIP
    bench = measure(repo)
    if bench is None:
        print("panel_bench: SKIP (node/toolchain/bundle unavailable) — "
              "sources shipped")
        return EXIT_SKIP
    if a.json:
        print(json.dumps(bench, indent=1, sort_keys=True))
        return EXIT_PASS
    if a.merge_trend:
        merge_trend(bench, repo / "docs" / "state" / "bench-trend.json")
        return EXIT_PASS
    for row in bench["rows"]:
        print(f"panel_bench: {row['metric']} = {row['value_us']} {row['unit']} "
              f"(surrogate, trend rig — never MET)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
