#!/usr/bin/env python3
"""tools/leaktest.py — xr-leaktest v0 runner (P9-T3).

``leaktest run --mode loopback`` executes every probe x policy-state cell
(plan §11.8 endpoint-audit matrix: fresh profile / after import / after each
S0 toggle flip) through the userspace loopback tap and compares observed
contacts to the documented set — today that set is empty, so ANY contact is
a leak (zero-default-telemetry; the owning phase documents real targets in
build/qa/leaktest/probes.yaml in the same commit as the feature).

``leaktest run --mode capture`` needs tcpdump/libpcap (absent here) and
SKIPs visibly with the farm runbook (docs/qa/leaktest.md) — never a
simulated PASS.

``leaktest --self-test`` is the mandatory self-verification:
  1. a clean run must be CLEAN;
  2. a planted egress (canary) must be flagged LEAK;
  3. the INVERSE — the canary is planted but the harness is blinded — must
     make the self-test exit non-zero (a harness that cannot see a leak is
     exactly the bug class this phase exists to eliminate).

Results follow docs/contracts/leaktest-result-v1.md. Stdlib only; the only
socket it ever opens binds 127.0.0.1 (zero new egress).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build.qa import _common as c  # noqa: E402
from build.qa.leaktest import engine  # noqa: E402

PROBES_YAML = "build/qa/leaktest/probes.yaml"
RESULT_JSON = "build/qa/leaktest/leaktest-result.json"


def load(repo: Path) -> tuple[list[engine.Probe], list[str]]:
    p = repo / PROBES_YAML
    if not p.exists():
        raise c.RunnerError(f"missing {PROBES_YAML}")
    return engine.load_probes(p)


def self_test(repo: Path, as_of: str) -> int:
    probes, states = load(repo)
    out: dict[str, Any] = {"as_of": c.iso(as_of), "checks": {}}

    # 1. clean baseline
    clean = engine.run_loopback(probes, states)
    out["checks"]["clean_baseline"] = clean["ok"]
    if not clean["ok"]:
        print("FAIL: leaktest self-test — clean baseline leaked "
              f"({clean['leak_count']} leaks)")
        return c.EXIT_FAIL

    # 2. planted egress must be flagged
    planted = {probes[0].id: engine.CANARY_HOST}
    hostile = engine.run_loopback(probes, states, planted=planted)
    detected = hostile["leak_count"] >= 1 and any(
        engine.CANARY_HOST in r["leaks"] for r in hostile["results"])
    out["checks"]["planted_detected"] = detected
    if not detected:
        print("FAIL: leaktest self-test — planted egress NOT detected "
              "(the harness cannot see a leak)")
        return c.EXIT_FAIL

    # 3. inverse: a BLIND harness (canary planted, detection suppressed)
    #    reports CLEAN — that is exactly the state check 2 refuses with a
    #    non-zero exit. Reproduce it so the failure mode is proven reachable.
    blind = engine.run_loopback(probes, states, planted=planted, blind=True)
    out["checks"]["blind_harness_reproduces_clean"] = blind["ok"]
    if not blind["ok"]:
        print("FAIL: leaktest self-test — cannot reproduce the blind-harness "
              "failure mode (expected a CLEAN lie, got a detection)")
        return c.EXIT_FAIL

    (repo / "build/qa/leaktest/leaktest-self-test.json").write_text(
        c.stable_json(out) + "\n", encoding="utf-8")
    print("PASS: leaktest self-test (clean baseline; planted egress detected; "
          "blind harness refused)")
    return c.EXIT_PASS


def run(repo: Path, mode: str, as_of: str, as_json: bool) -> int:
    probes, states = load(repo)
    if mode == "capture":
        # capture is a farm-only lane (docs/qa/leaktest.md: "automatable:
        # no"). tcpdump/libpcap is necessary but NOT sufficient — the real
        # capture also needs the browser and CAP_NET_RAW (root). So the lane
        # SKIPs visibly (77) on every non-farm host, naming the missing part:
        # tcpdump when it is absent, the farm harness when tcpdump merely
        # ships with the OS image (GitHub's ubuntu-latest does). A FAIL here
        # would turn governance red on any host that happens to have tcpdump,
        # and a fabricated capture is forbidden — off-farm is always a
        # visible SKIP, never a PASS and never a spurious FAIL.
        if shutil.which("tcpdump") is None:
            return c.skip_visible(
                "leaktest(capture)",
                "SKIP (tool absent: tcpdump/libpcap) — needed for: privileged "
                "whole-tree capture of the endpoint audit; this host has no "
                "tcpdump; farm runbook: docs/qa/leaktest.md")
        return c.skip_visible(
            "leaktest(capture)",
            "SKIP (farm-only lane) — needed for: the real capture (tcpdump "
            "is present here but the browser + CAP_NET_RAW farm harness is "
            "not); the capture is never simulated; farm runbook: "
            "docs/qa/leaktest.md")
    result = engine.run_loopback(probes, states)
    result["as_of"] = c.iso(as_of)
    result["mode"] = "loopback"
    result["rig_class"] = "trend"
    out = repo / RESULT_JSON
    out.write_text(c.stable_json(result) + "\n", encoding="utf-8")
    if as_json:
        print(c.stable_json({"tool": "leaktest", **result}))
    else:
        print(f"leaktest: {result['cells']} probe x state cells executed, "
              f"{result['leak_count']} leak(s)")
        print(f"{'PASS' if result['ok'] else 'FAIL'}: leaktest (loopback)")
    return c.EXIT_PASS if result["ok"] else c.EXIT_FAIL


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="leaktest", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--self-test", action="store_true",
                   help="run the mandatory self-verification")
    p.add_argument("--mode", choices=["loopback", "capture"],
                   default="loopback")
    p.add_argument("--json", action="store_true")
    c.as_of_arg(p)
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        if args.self_test:
            return self_test(repo, args.as_of)
        return run(repo, args.mode, args.as_of, args.json)
    except c.RunnerError as exc:
        print(f"FAIL: {exc}")
        return c.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
