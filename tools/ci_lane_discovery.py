#!/usr/bin/env python3
"""tools/ci_lane_discovery.py — C++ suite lane discovery (P9-T0-c).

Root cause T0-c closed: run_checks.sh had explicit hand-written `make -C`
lanes for policy/commands only; the settings and themes suites (9 C++ suites,
1.6 k mutants, two 600 s fuzzers) were reached only through pytest
side-effects, so `make -C xr-core/themes/tests test` going red did NOT redden
governance — the same scope-drift class as P7's evidence-gate bug.

This gate makes the DISCOVERED set the source of truth: every
``xr-core/*/tests/Makefile`` is a lane (run as its own named `make test`),
and hand-written lanes for those dirs are forbidden — they are what drifted
before. A lane list that drifts from the committed record
(docs/state/ci-lanes.json) FAILS the gate, so a suite added or removed in any
future phase is visible, never silently dropped.

The zero-case law: zero discovered lanes, or a lane whose make produced no
`ALL C++ ... TESTS PASSED` banner (and no visible SKIP), is a FAILURE.

Exit: 0 pass · 1 fail (drift / broken suite) · 2 usage · 77 SKIP (no g++/make).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77
MANIFEST = "docs/state/ci-lanes.json"


def discover(repo: Path, xr_core: Path) -> list[str]:
    """Lane names: every xr-core/*/tests/Makefile, sorted (deterministic)."""
    lanes: list[str] = []
    for mk in sorted(xr_core.glob("*/tests/Makefile")):
        lane = mk.parent.parent.name
        lanes.append(lane)
    return lanes


def run_lane(xr_core: Path, lane: str, repo: Path,
             timeout: int) -> tuple[bool, str, str]:
    """Run one lane's `make test`; return (passed, output, skip_reason)."""
    make_dir = xr_core / lane / "tests"
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin",
           "XR_BROWSER_ROOT": str(repo)}
    import os
    for k, v in os.environ.items():
        env.setdefault(k, v)
    try:
        proc = subprocess.run(["make", "test"], cwd=make_dir, env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout}s"
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        return False, out, ""
    return True, out, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repo", default=".", help="xr-browser root (default: cwd)")
    ap.add_argument("--record", action="store_true",
                    help="re-record the committed lane manifest")
    ap.add_argument("--lane-timeout", type=int, default=900,
                    help="per-lane make timeout seconds")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    xr_core = (repo.parent / "xr-core").resolve()
    if not xr_core.is_dir():
        print("error: no ../xr-core sibling checkout", file=sys.stderr)
        return EXIT_USAGE

    lanes = discover(repo, xr_core)
    if not lanes:
        print("error: zero xr-core/*/tests/Makefile lanes discovered "
              "(zero-case law)", file=sys.stderr)
        return EXIT_FAIL

    if args.record:
        mpath = repo / MANIFEST
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(json.dumps({"schema_version": 1, "lanes": lanes},
                                    indent=2) + "\n")
        print(f"PASS: recorded {len(lanes)} lanes -> {MANIFEST}")
        return EXIT_PASS

    # drift check: the discovered set is the source of truth; the committed
    # manifest is the record it must match (no silent add/remove).
    mpath = repo / MANIFEST
    if mpath.is_file():
        try:
            recorded = json.loads(mpath.read_text(encoding="utf-8"))["lanes"]
        except (json.JSONDecodeError, KeyError):
            recorded = None
        if recorded is None:
            print(f"FAIL: {MANIFEST} unreadable (lane list drift)")
            return EXIT_FAIL
        if sorted(recorded) != sorted(lanes):
            print(f"FAIL: lane list drifted — recorded {sorted(recorded)}, "
                  f"discovered {lanes}; re-run with --record")
            return EXIT_FAIL
    else:
        print(f"FAIL: no committed lane manifest at {MANIFEST}; run --record")
        return EXIT_FAIL

    if shutil.which("g++") is None or shutil.which("make") is None:
        print("SKIP: SKIP (tool absent: g++/make) — needed for: the discovered "
              f"C++ suite lanes {lanes}; local hint: apt-get install g++ make")
        return EXIT_SKIP

    results: dict[str, Any] = {}
    n_pass = 0
    for lane in lanes:
        ok, out, skip = run_lane(xr_core, lane, repo, args.lane_timeout)
        passed = ok and "ALL C++ " in out.upper() and "PASSED" in out.upper()
        if not ok:
            print(f"FAIL: lane {lane}: make test failed")
            print(out[-800:])
        elif not passed:
            print(f"FAIL: lane {lane}: no 'ALL C++ … TESTS PASSED' banner "
                  "(a run that executed nothing is a failure)")
            print(out[-800:])
        else:
            n_pass += 1
            print(f"PASS: lane {lane}: C++ suites passed")
        results[lane] = {"passed": bool(passed),
                         "tail": out.strip().splitlines()[-1:] if out else []}
    total_ok = n_pass == len(lanes)
    if args.json:
        print(json.dumps({"lanes": lanes, "results": results,
                          "status": "pass" if total_ok else "fail"}, indent=2))
    else:
        print(f"{'PASS' if total_ok else 'FAIL'}: ci_lane_discovery "
              f"({n_pass}/{len(lanes)} lanes)")
    return EXIT_PASS if total_ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
