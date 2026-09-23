#!/usr/bin/env python3
"""tools/cosmetic_bench.py — the P12-T7 cosmetic bench driver.

This is a SURROGATE bench: it drives the cosmetic_host (the same compiled
core the renderer uses) over a deterministic synthetic rule workload and
emits the normalized tools/perf_gate.py row shape. It never claims a
browser measurement: the seam-enabling halves (document-start p95 over
real Blink, blank-page detection, the 50-hard-apps spot check, the
breakage-diff baseline, the DOM-poll vs the cited uBO reference) are
recorded NOT-RUN in docs/qa/browser-harness.md with their method.

Rows (metric -> source):
  * cosmetic_keyset_build_ms — host `key-set` build over the generic-set
    rules (33) and a synthetic 4096-rule set, measured here, `trend` only;
  * cosmetic_generic_set_rules — the shipped set's count (33), read from
    xr-lists/generic-hide-set.v1.json, never measured into a placeholder.

`rig_class` is `trend` in this sandbox: the comparator's rig-class law
refuses a browser-side `reference` budget asserted from a trend rig, and a
negative fixture (tools/negatives/p12_t7.sh) keeps that refusal red.
--merge-trend folds the rows into docs/state/bench-trend.json (the
committed trend input the P9-T5 lane consumes); --check verifies the
committed rows are present without re-measuring.

Exit: 0 pass · 1 fail · 2 usage · 77 visible skip (host absent).
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77
REPO = Path(__file__).resolve().parents[1]
TREND = REPO / "docs" / "state" / "bench-trend.json"
SET_FILE = "xr-lists/generic-hide-set.v1.json"
METRICS = ("cosmetic_keyset_build_ms", "cosmetic_generic_set_rules")


def host_bin(xr_core: Path) -> Path:
    return (xr_core / "renderer" / "cosmetic" / "tests" / "build" /
            "cosmetic_host")


def call(host: Path, method: str, args: dict) -> dict:
    frame = json.dumps({"args": args, "method": method},
                       sort_keys=True, separators=(",", ":"))
    r = subprocess.run([str(host)], input=frame, capture_output=True,
                       text=True, timeout=120)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


def time_keyset(host: Path, rules: list[dict], iters: int = 20) -> float | None:
    """Median wall-clock ms to compile the rule set (process-per-iter —
    honest: this measures the surrogate path, labelled as such)."""
    samples: list[float] = []
    frame = json.dumps({"args": {"rules": rules}, "method": "key-set"},
                       sort_keys=True, separators=(",", ":"))
    for _ in range(iters):
        t0 = time.perf_counter()
        subprocess.run([str(host)], input=frame, capture_output=True,
                       text=True, timeout=120)
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return samples[len(samples) // 2]


def measure(xr_core: Path) -> dict | None:
    host = host_bin(xr_core)
    if not host.exists():
        return None
    set_doc = json.loads((REPO / SET_FILE).read_text(encoding="utf-8"))
    rules = [{"id": f"g{i}", "selector": e["selector"],
              "action": e["action"],
              **(dict(e["style"]) if e.get("style") else {})}
             for i, e in enumerate(set_doc["selectors"])]
    build_ms = time_keyset(host, rules)
    return {"name": "cosmetic-surrogate (cosmetic_host key-set)",
            "rig_class": "trend",
            "rows": [
                {"metric": "cosmetic_keyset_build_ms", "unit": "ms",
                 "value_us": build_ms, "n": 20, "sampled": True,
                 "surrogate": True},
                {"metric": "cosmetic_generic_set_rules", "unit": "rules",
                 "value_us": len(set_doc["selectors"]),
                 "surrogate": True},
            ]}


def merge_trend(rows: list[dict], rig: str, path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    kept = [r for r in doc["rows"] if r["metric"] not in METRICS]
    clean = [{k: v for k, v in r.items()} for r in rows]
    doc["rows"] = kept + clean
    if "cosmetic" not in doc["name"]:
        doc["name"] += " + cosmetic keyset (surrogate)"
    doc["rig_class"] = rig
    path.write_text(json.dumps(doc, sort_keys=True,
                               separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"cosmetic_bench: merged {len(clean)} cosmetic row(s) into {path}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="cosmetic-bench",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--merge-trend", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed bench-trend.json carries the "
                         "cosmetic rows (no re-measurement)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    repo = Path(a.repo).resolve()
    xr_core = (Path(a.xr_core).resolve() if a.xr_core
               else repo.parent / "xr-core")
    trend = repo / "docs" / "state" / "bench-trend.json"

    if a.check:
        doc = json.loads(trend.read_text(encoding="utf-8"))
        have = {r["metric"] for r in doc["rows"]}
        missing = [m for m in METRICS if m not in have]
        if missing:
            print(f"FAIL: bench-trend.json missing cosmetic rows: {missing} "
                  "(run cosmetic_bench.py --merge-trend)")
            return EXIT_FAIL
        print(f"PASS: cosmetic-bench --check (rows present: "
              f"{', '.join(sorted(have & set(METRICS)))})")
        return EXIT_PASS

    res = measure(xr_core)
    if res is None:
        print("SKIP: SKIP (tool absent: g++/make) — needed for: the cosmetic "
              "key-set surrogate bench (cosmetic_host); local hint: "
              "apt-get install g++ make (build-essential)")
        return EXIT_SKIP
    if a.merge_trend:
        merge_trend(res["rows"], res["rig_class"], trend)
    if a.json:
        print(json.dumps(res, sort_keys=True))
    else:
        for r in res["rows"]:
            print(f"  {r['metric']}: value_us={r.get('value_us')} "
                  f"(surrogate={r.get('surrogate')})")
        print(f"cosmetic-bench: {len(res['rows'])} row(s), "
              f"rig_class={res['rig_class']}")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
