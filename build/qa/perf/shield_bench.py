#!/usr/bin/env python3
"""build/qa/perf/shield_bench.py — the P11-T7 shield bench driver.

Compiles and runs build/qa/perf/shield_bench.cc (the C++ binding:
DecideMatch over the shield core, TableEngine by default or the
vendored adblock-rust through the FFI shim with --engine real on the
hosted lane), then measures the PYTHON fake binding (fakes/shield.py
decide_match — the byte-parity mirror) over the SAME deterministic
synthetic corpus (>=50k requests, no RNG, no wall clock in the data).

Rows are emitted in the normalized tools/perf_gate.py shape; verdicts
are perf_gate's job (rig-class law: this sandbox is a `trend` rig —
the <=80MB plan budget is a browser-side `reference` row and is NEVER
asserted here; rss_structures_mb has no budget row = RECORD-ONLY).
--merge-trend folds the shield rows into docs/state/bench-trend.json
(the committed trend-rig input the P9-T5 perf lane consumes);
--check verifies those rows are present without re-measuring.

Exit: 0 pass · 1 fail · 2 usage · 77 visible skip (g++ absent —
skip-policy law). Stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BENCH_CC = Path(__file__).resolve().parent / "shield_bench.cc"
TREND = REPO / "docs" / "state" / "bench-trend.json"
SHIELD_METRICS = ("fakecore_decision_p99_ms", "filter_decision_p99_ms",
                  "list_apply_ms", "rss_structures_mb",
                  "fake_decision_p99_ms")
# Required in the committed trend file (sandbox side); the product row
# filter_decision_p99_ms is the HOSTED reference rig's (real engine) and
# is optional here.
TREND_REQUIRED = ("fakecore_decision_p99_ms", "list_apply_ms",
                  "fake_decision_p99_ms")
CORE_SRCS = [
    "shield/core/context.cc", "shield/core/posture.cc",
    "shield/core/bundle.cc", "shield/core/scope.cc",
    "shield/core/apply.cc", "shield/core/events.cc",
    "shield/core/match.cc", "shield/core/fake_engine.cc",
    "common/core/json.cc", "common/core/json_parse.cc",
    "common/core/sha256.cc",
]


def percentiles(samples: list[float]) -> tuple[float, float, float]:
    v = sorted(samples)
    at = lambda q: v[int(q * (len(v) - 1))]  # noqa: E731
    return at(0.50), at(0.99), at(0.999)


# ---- the deterministic synthetic corpus (mirrors shield_bench.cc) ----

def make_bundle_doc(version: int, per_list: int) -> dict:
    lists = []
    for l in range(4):
        rules = []
        for i in range(per_list):
            g = l * per_list + i
            rid = f"r{g}"
            k = i % 5
            if k == 0:
                rules.append({"action": "block", "filter":
                              f"||b{g}.track.example^", "id": rid,
                              "kind": "network"})
            elif k == 1:
                rules.append({"action": "block", "filter":
                              f"||cdn{g}.cdn.example/js/adframe.js",
                              "id": rid, "kind": "network"})
            elif k == 2:
                rules.append({"action": "block", "filter":
                              f"||wild{g}.wild.example/ad_*.js", "id": rid,
                              "kind": "network"})
            elif k == 3:
                rules.append({"action": "allow", "filter":
                              f"||allow{g}.allow.example^", "id": rid,
                              "kind": "network"})
            else:
                rules.append({"action": "block", "domains":
                              [f"site{g % 97}.example"], "filter":
                              f"||meta{g}.meta.example^", "id": rid,
                              "kind": "network"})
        lists.append({"attribution":
                      "The EasyList authors (https://easylist.to/)",
                      "name": f"l{l}", "rules": rules})
    return {"bundle_version": version, "lists": lists, "name": "xr-bench",
            "refusals": [], "schema": "xr-list-bundle", "schema_version": 1}


def make_context(j: int, nrules: int) -> dict:
    # g aligned to the targeted rule class (g%5 cycle in make_bundle_doc)
    base = (j * 7919) % (nrules // 5)
    classes = ["kSubresource", "kScript", "kNavigation", "kNetwork",
               "kPermission", "kStorage"]
    m = j % 20
    if m in (14, 15, 16):
        url = f"https://b{base * 5}.track.example/x{j}.js"
    elif m == 17:
        url = f"https://cdn{base * 5 + 1}.cdn.example/js/adframe.js"
    elif m == 18:
        url = f"https://allow{base * 5 + 3}.allow.example/x"
    elif m == 19:
        url = f"https://wild{base * 5 + 2}.wild.example/ad_9.js"
    else:
        url = f"https://nm{j}.clean.example/res/{j}.js"
    # rd = the naive last-two-labels of the url host (all bench hosts are
    # RFC 2606 .example — fixture data, never fetched: chokepoint law)
    rd = ".".join(url.split("://", 1)[1].split("/", 1)[0].split(".")[-2:])
    return {"identity": {"value":
                         "xr:00000000-0000-4000-8000-000000000001"},
            "origin": {"registrable_domain": rd, "scheme": "https"},
            "request_class": classes[j % 6], "url": url}


def run_python_binding(xr_core: Path, iters: int, rules: int) -> dict:
    """The Python reference-fake measurement: decide_match over pre-parsed
    data. SAMPLED by default (--py-iters 2000): the fake is a pure-Python
    linear scan (O(rules) per no-match — hours at 50k x 20k rules), so the
    brief's >=50k floor rides the PRODUCT-path bindings: the C++ core
    binding here (50k, this run) and the real-engine binding on the hosted
    reference rig (50k, core-hardening step). The row is RECORD-ONLY and
    carries its honest n."""
    fake_path = xr_core / "fakes" / "shield.py"
    if str(fake_path.parent) not in sys.path:
        sys.path.insert(0, str(fake_path.parent))  # fakes/_base import
    spec = importlib.util.spec_from_file_location("xr_fake_shield_bench",
                                                  fake_path)
    fake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fake)
    bundle = fake.parse_bundle(make_bundle_doc(3, rules // 4))
    scopes = fake.parse_scopes([{"reason": "user-allow", "scope_id": "ex-1",
                                 "site": "example.org"}])
    pin = fake.parse_posture_args({})
    ctxs = [fake.parse_context(make_context(j, rules))
            for j in range(iters)]
    for j in range(min(200, iters)):
        fake.decide_match(ctxs[j], bundle, scopes, 1000 + j, pin)
    samples = []
    counts = [0, 0, 0]
    for j in range(iters):
        t0 = time.perf_counter()
        out = fake.decide_match(ctxs[j], bundle, scopes, 1000 + j, pin)
        samples.append((time.perf_counter() - t0) * 1000.0)
        v = out["verdict"]
        if v.get("engine_decision") and v.get("action") == "block":
            counts[0] += 1
        elif v.get("engine_decision"):
            counts[1] += 1
        else:
            counts[2] += 1
    p50, p99, p999 = percentiles(samples)
    return {"metric": "fake_decision_p99_ms", "n": iters, "p50": p50,
            "p99": p99, "p999": p999, "sampled": True, "unit": "ms",
            "value_us": p99, "mix": counts}


def compile_and_run_cc(xr_core: Path, tmp: Path, args) -> dict | None:
    gxx = shutil.which("g++")
    if not gxx:
        return None
    srcs = [str(BENCH_CC)] + [str(xr_core / s) for s in CORE_SRCS]
    binary = tmp / "shield_bench"
    cmd = [gxx, "-O2", "-std=c++20", f"-I{xr_core}", "-o", str(binary)]
    link = []
    if args.engine == "real":
        if not args.shim_dir:
            raise SystemExit("FAIL: --engine real needs --shim-dir (the "
                             "cargo-built libxr_shield_engine directory)")
        cmd += ["-DXR_SHIELD_REAL_ENGINE"]
        # Libraries AFTER the objects: GNU ld resolves left-to-right and
        # drops a -l whose symbols nothing has referenced yet (hosted run
        # 34758863940 taught this with undefined xr_shield_engine_*).
        link = [f"-L{args.shim_dir}", "-lxr_shield_engine",
                f"-Wl,-rpath,{args.shim_dir}"]
    cmd += srcs + link
    print(f"shield_bench: compiling ({' '.join(cmd[:4])} … {len(srcs)} TUs)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: shield_bench.cc compile:\n" + r.stderr[-2000:])
        raise SystemExit(1)
    run = [str(binary), "--iters", str(args.iters), "--rules",
           str(args.rules), "--apply-iters", str(args.apply_iters),
           "--rig", args.rig, "--engine", args.engine]
    r = subprocess.run(run, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(1)
    doc = None
    for line in reversed(r.stdout.splitlines()):
        if line.strip().startswith("{"):
            doc = json.loads(line)
            break
    if doc is None:
        print("FAIL: no canonical JSON line from the bench binary")
        raise SystemExit(1)
    return doc


def merge_trend(rows: list[dict], rig: str, path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    kept = [r for r in doc["rows"] if r["metric"] not in SHIELD_METRICS]
    clean = [{k: v for k, v in r.items() if k != "mix"} for r in rows]
    doc["rows"] = kept + clean
    doc["name"] = ("trend-rig benches (policy resolve + themes apply + "
                   "shield decision/apply)")
    doc["rig_class"] = rig
    path.write_text(json.dumps(doc, sort_keys=True,
                              separators=(",", ":")) + "\n",
                    encoding="utf-8")
    print(f"shield_bench: merged {len(clean)} shield row(s) into {path}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="shield-bench",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--iters", type=int, default=50000)
    ap.add_argument("--rules", type=int, default=20000)
    ap.add_argument("--apply-iters", type=int, default=10)
    ap.add_argument("--py-iters", type=int, default=2000,
                    help="Python reference-fake sample size (record-only "
                         "row; see run_python_binding docstring)")
    ap.add_argument("--rig", choices=("trend", "reference"),
                    default="trend")
    ap.add_argument("--engine", choices=("fake", "real"), default="fake")
    ap.add_argument("--shim-dir", default=None)
    ap.add_argument("--merge-trend", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed bench-trend.json carries "
                         "the shield rows (no re-measurement)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.iters < 50000 or args.rules < 4000 or args.rules % 4:
        print("usage error: --iters >= 50000 (the plan's floor), --rules "
              ">= 4000 and a multiple of 4")
        return 2
    repo = Path(args.repo).resolve()
    trend = repo / "docs" / "state" / "bench-trend.json"
    if args.check:
        doc = json.loads(trend.read_text(encoding="utf-8"))
        have = {r["metric"] for r in doc["rows"]}
        required = list(TREND_REQUIRED)
        if sys.platform == "linux":
            required.append("rss_structures_mb")
        missing = [m for m in required if m not in have]
        if missing:
            print(f"FAIL: bench-trend.json missing shield rows: {missing} "
                  "(run shield_bench.py --merge-trend)")
            return 1
        print(f"PASS: shield-bench --check (rows present: "
              f"{', '.join(sorted(have & set(SHIELD_METRICS)))})")
        return 0

    xr_core = Path(args.xr_core).resolve() if args.xr_core \
        else repo.parent / "xr-core"
    tmp = Path(tempfile.mkdtemp(prefix="shield-bench."))
    try:
        cc = compile_and_run_cc(xr_core, tmp, args)
        if cc is None:
            print("SKIP: SKIP (tool absent: g++) — needed for: the shield "
                  "decision/apply bench (C++ binding); local hint: "
                  "apt-get install g++ (build-essential)")
            return 77
        py = run_python_binding(xr_core, args.py_iters, args.rules)
        p50, p99, p999 = py["p50"], py["p99"], py["p999"]
        print(f"python fake binding (SAMPLED n={args.py_iters}): "
              f"p50={p50:.6f} p99={p99:.6f} p99.9={p999:.6f} ms (mix: "
              f"{py['mix'][0]} block / {py['mix'][1]} allow / "
              f"{py['mix'][2]} no-match; record-only)")
        rows = cc["rows"] + [{k: v for k, v in py.items()
                              if k != "mix"}]
        if args.merge_trend:
            merge_trend(rows, cc.get("rig_class", args.rig), trend)
        if args.json:
            print(json.dumps({"name": cc["name"],
                              "rig_class": cc.get("rig_class", args.rig),
                              "rows": rows}, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
