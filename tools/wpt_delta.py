#!/usr/bin/env python3
"""tools/wpt_delta.py — WPT pass-rate comparator (P9-T4, §11.12).

Inputs: two expectation/result sets as JSON — a baseline (e.g. Chrome
stable) and a candidate (XR). Outputs: the delta %, per-project grouping,
and the regression list. The 0.5 % law is enforced as data: a delta inside
the threshold is WITHIN-TOLERANCE; above it is a REGRESSION (blocking).

The flaky rule is recorded, not hand-picked: a test whose baseline status is
"FLAKY" is excluded from the delta by the comparator's own rule (a flaky
baseline cannot produce a meaningful regression). A regression is
baseline=PASS -> candidate=FAIL; everything else is not a regression.

Input shape (both files): {"name": str, "tests": {"path": "PASS|FAIL|FLAKY"}}.
Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError, \
    require_cases, stable_json  # noqa: E402

THRESHOLD_PCT = 0.5


def load(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunnerError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(doc.get("tests"), dict) or not doc.get("tests"):
        raise RunnerError(f"{path}: 'tests' must be a non-empty mapping "
                          f"(empty-run law)")
    return doc


def compare(base: dict, cand: dict) -> dict:
    base_tests, cand_tests = base["tests"], cand["tests"]
    common = sorted(set(base_tests) & set(cand_tests))
    require_cases(len(common), "wpt_delta")

    eligible = {t for t in common if base_tests[t] != "FLAKY"}
    regressions = [t for t in sorted(eligible)
                   if base_tests[t] == "PASS" and cand_tests[t] == "FAIL"]
    total = len(eligible)
    delta_pct = round(100.0 * len(regressions) / total, 3) if total else 0.0

    # per-project grouping (path prefix up to the first '/')
    groups: dict[str, dict] = {}
    for t in sorted(eligible):
        project = t.split("/")[0]
        g = groups.setdefault(project, {"total": 0, "regressions": 0})
        g["total"] += 1
        if t in regressions:
            g["regressions"] += 1

    verdict = "REGRESSION" if delta_pct > THRESHOLD_PCT else "WITHIN-TOLERANCE"
    return {"name_base": base.get("name", "base"),
            "name_candidate": cand.get("name", "candidate"),
            "common": len(common), "eligible": total,
            "flaky_excluded": len(common) - total,
            "regressions": regressions, "delta_pct": delta_pct,
            "threshold_pct": THRESHOLD_PCT, "verdict": verdict,
            "groups": groups}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="wpt_delta", description=__doc__)
    p.add_argument("baseline", help="baseline result set JSON")
    p.add_argument("candidate", help="candidate result set JSON")
    p.add_argument("--threshold", type=float, default=THRESHOLD_PCT,
                   help=f"regression threshold % (default {THRESHOLD_PCT})")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    try:
        base = load(Path(args.baseline))
        cand = load(Path(args.candidate))
        result = compare(base, cand)
    except RunnerError as exc:
        print(f"FAIL: {exc}")
        return EXIT_FAIL
    result["threshold_pct"] = args.threshold
    result["verdict"] = ("REGRESSION"
                         if result["delta_pct"] > args.threshold
                         else "WITHIN-TOLERANCE")

    if args.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print(f"wpt_delta: {result['eligible']} eligible tests, "
              f"{len(result['regressions'])} regression(s), "
              f"delta {result['delta_pct']}% "
              f"(threshold {args.threshold}%)")
        for t in result["regressions"][:20]:
            print(f"  REGRESSION: {t}")
        print(f"{result['verdict']}: wpt_delta")
    return EXIT_PASS if result["verdict"] == "WITHIN-TOLERANCE" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
