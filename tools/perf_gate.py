#!/usr/bin/env python3
"""tools/perf_gate.py — the perf budget comparator (P9-T5).

Consumes bench JSON (normalized by the in-repo adapters below, or provided
directly) and compares it against build/qa/perf/perf-budgets.json (generated
from the pinned plan). Enforces:

  * the empty-run law — zero bench rows is a FAILURE;
  * the noise law — a delta inside the ±2% band is NEUTRAL (never MET),
    beyond it is MISSED (regression, auto-assigned);
  * the rig-class law — a browser-side row may only emit MET/MISSED from a
    `reference` rig; a `trend` rig asserting one is REFUSED (exit 1);
  * regression auto-assign — each MISSED row is mapped to its S0 owner via
    docs/process/s0-paths.yaml (the CODEOWNERS source), never hand-picked.

Bench input shape (normalized): {"name", "rig_class", "rows": [
  {"metric", "value_us", "budget_us"?, "samples"?, "n"?}]}.
`--report-json`/`--report-md` write docs/state/perf-budgets.md
(generated, --check diff-clean in CI). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build.qa import _common as c  # noqa: E402

BUDGETS = "build/qa/perf/perf-budgets.json"
S0_PATHS = "docs/process/s0-paths.yaml"
REPORT_MD = "docs/state/perf-budgets.md"
NOISE_BAND = 0.02
RIG_RANK = {"trend": 1, "reference": 2, "farm": 0}


def load_budgets(repo: Path) -> dict:
    doc = c.read_json(repo / BUDGETS)
    if doc.get("schema_version") != 1:
        raise c.RunnerError(f"{BUDGETS}: unsupported schema_version")
    return doc


def owners(repo: Path) -> dict[str, list[str]]:
    """S0 owner groups from docs/process/s0-paths.yaml (CODEOWNERS source)."""
    import yaml
    doc = yaml.safe_load((repo / S0_PATHS).read_text(encoding="utf-8"))
    groups = {k: (v if isinstance(v, list) else [v])
              for k, v in (doc.get("owner_groups") or {}).items()}
    return groups


def subsystem(metric: str) -> str:
    for prefix in ("policy", "commands", "settings", "themes"):
        if metric.startswith(prefix) or prefix in metric:
            return prefix
    return "default"


def assign_owner(metric: str, groups: dict[str, list[str]]) -> list[str]:
    sub = subsystem(metric)
    for key, members in groups.items():
        if key == sub:
            return members
    return groups.get("default", [])


def _median(samples: list[float]) -> float:
    return float(statistics.median(samples))


def read_bench_json(path: Path) -> dict:
    """Read a bench file that may carry a human table header (policy bench
    prints the table above the canonical JSON line)."""
    import re as _re
    text = path.read_text(encoding="utf-8")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    try:
        return json.loads(text)
    except Exception as exc:
        raise c.RunnerError(f"{path}: not valid JSON ({exc})") from exc


def normalize_bench(doc: dict) -> dict[str, Any]:
    """Adapter: accept the four in-repo bench shapes + the normalized shape."""
    import re as _re
    rig = doc.get("rig_class", "trend")
    rows: list[dict[str, Any]] = []

    if "rows" in doc and isinstance(doc["rows"], list):
        rows = [dict(r) for r in doc["rows"]]
    elif "verdicts" in doc and "budgets" in doc:
        # policy bench: {verdicts:{m:..}, <m>:{p99}, budgets:{m_us}}
        for metric, verdict in doc["verdicts"].items():
            norm = _re.sub(r"_\d+$", "", metric) + "_us"
            budget_us = doc["budgets"].get(metric + "_us") or \
                doc["budgets"].get(norm)
            stat = doc.get(metric, {})
            rows.append({"metric": norm,
                         "value_us": stat.get("p99"),
                         "samples": [stat.get("p50"), stat.get("p99"),
                                     stat.get("p99.9")] if stat else None,
                         "budget_us": budget_us})
    elif "sub_budget_us_p99" in doc:
        # commands/settings bench
        rows.append({"metric": "sub_budget_p99_us",
                     "value_us": doc.get("p99_us"),
                     "budget_us": doc.get("sub_budget_us_p99")})
    elif "budget_us" in doc and "avg_custom_import_us" in doc:
        # themes bench
        rows.append({"metric": "theme_apply_us",
                     "value_us": doc.get("worst_single_us"),
                     "budget_us": doc.get("budget_us")})
    else:
        raise c.RunnerError("unrecognized bench JSON shape")
    return {"name": doc.get("name", doc.get("tool", doc.get("bench",
                                                           "bench"))),
            "rig_class": rig, "rows": rows}


def compare(repo: Path, bench: dict[str, Any]) -> dict[str, Any]:
    budgets = {r["metric"]: r for r in load_budgets(repo)["rows"]}
    groups = owners(repo)
    rows_out: list[dict[str, Any]] = []
    for row in bench["rows"]:
        metric = row["metric"]
        samples = row.get("samples")
        value = float(row["value_us"]) if row.get("value_us") is not None \
            else (_median([s for s in samples if s is not None])
                  if samples else None)
        if value is None:
            raise c.RunnerError(f"{metric}: no value or samples")
        budget_row = budgets.get(metric)
        if budget_row is None:
            # record-only: trend shape, no verdict claim
            rows_out.append({"metric": metric, "value": value,
                             "unit": row.get("unit", "us"),
                             "verdict": "RECORD-ONLY",
                             "rig_class": bench["rig_class"]})
            continue
        assert_class = budget_row["assert_class"]
        if RIG_RANK.get(bench["rig_class"], -1) < RIG_RANK[assert_class]:
            raise c.RunnerError(
                f"{metric}: {bench['rig_class']} rig cannot assert a "
                f"{budget_row['surface']} budget (assert_class="
                f"{assert_class}) — rig-class law (docs/hw.md)")
        budget = float(budget_row["value"])
        ratio = value / budget if budget else float("inf")
        if value <= budget:
            verdict = "MET"
        elif ratio <= 1 + NOISE_BAND:
            verdict = "NEUTRAL"   # inside the noise band: never MET
        else:
            verdict = "MISSED"
        rows_out.append({
            "metric": metric, "value": value, "unit": budget_row["unit"],
            "budget": budget, "verdict": verdict,
            "delta_pct": round((ratio - 1) * 100, 3),
            "rig_class": bench["rig_class"], "surface": budget_row["surface"],
            "owner": assign_owner(metric, groups),
            "plan_cite": budget_row["plan_cite"]})
    c.require_cases(len(rows_out), "perf_gate")
    missed = [r for r in rows_out if r["verdict"] == "MISSED"]
    neutral = [r for r in rows_out if r["verdict"] == "NEUTRAL"]
    return {"bench": bench["name"], "rig_class": bench["rig_class"],
            "rows": rows_out, "missed": len(missed), "neutral": len(neutral),
            "ok": not missed}


def render_md(result: dict[str, Any], as_of: str) -> str:
    lines = ["# Perf budgets (generated — P9-T5)",
             "",
             f"Generated with `--as-of {as_of}`. Do not hand-edit; regenerate "
             f"with `tools/perf_gate.py --report-md`. Budgets transcribed "
             f"from the pinned plan by `gen_perf_budgets.py`.",
             "",
             f"Bench: {result['bench']} (rig class **{result['rig_class']}**)",
             "",
             "| metric | value | budget | delta % | verdict | owner | plan |",
             "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        lines.append(f"| {r['metric']} | {r.get('value')} | "
                     f"{r.get('budget', '—')} | {r.get('delta_pct', '—')} | "
                     f"{r['verdict']} | {', '.join(r.get('owner', []))} | "
                     f"{r.get('plan_cite', r.get('verdict'))} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="perf_gate", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--bench", action="append", default=[],
                   help="bench JSON file (repeatable; in-repo shapes or "
                        "normalized)")
    p.add_argument("--report-json", default="")
    p.add_argument("--report-md", default="",
                   help="write the generated report here (explicit; the "
                        "report is never written unless asked — a bare "
                        "comparison must not mutate the repo)")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed report drifted")
    p.add_argument("--json", action="store_true")
    c.as_of_arg(p)
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not args.bench:
        print("FAIL: no --bench files given (usage error)")
        return c.EXIT_USAGE

    results: list[dict[str, Any]] = []
    try:
        for b in args.bench:
            bp = Path(b)
            if not bp.is_absolute():
                bp = repo / bp
            raw = read_bench_json(bp)
            bench = normalize_bench(raw)
            results.append(compare(repo, bench))
    except c.RunnerError as exc:
        print(f"FAIL: {exc}")
        return c.EXIT_FAIL

    total_missed = sum(r["missed"] for r in results)
    total_neutral = sum(r["neutral"] for r in results)
    total_rows = sum(len(r["rows"]) for r in results)
    payload = {"as_of": c.iso(args.as_of), "results": results,
               "rows": total_rows, "missed": total_missed,
               "neutral": total_neutral}

    new_md = render_md({"bench": ", ".join(r["bench"] for r in results),
                        "rig_class": results[0]["rig_class"],
                        "rows": [x for r in results for x in r["rows"]]},
                       args.as_of)
    if args.check:
        md_path = Path(args.report_md) if args.report_md else \
            Path(REPORT_MD)
        if not md_path.is_absolute():
            md_path = repo / md_path
        ok = md_path.exists() and \
            md_path.read_text(encoding="utf-8") == new_md
        if not ok:
            print(f"FAIL: {md_path} drifted — regenerate with --report-md")
            return c.EXIT_FAIL
        print("PASS: perf_gate --check (report diff-clean)")
        return c.EXIT_PASS

    if args.report_json:
        jp = Path(args.report_json)
        if not jp.is_absolute():
            jp = repo / jp
        c.write_stable(jp, payload, as_of=args.as_of)
    if args.report_md:
        # the report is written ONLY when explicitly requested — a bare
        # comparison (tests, canaries) must never mutate the committed report.
        md_path = Path(args.report_md)
        if not md_path.is_absolute():
            md_path = repo / md_path
        md_path.write_text(new_md, encoding="utf-8")

    if args.json:
        print(c.stable_json({"tool": "perf_gate", **payload,
                             "status": "pass" if not total_missed else "fail"}))
    else:
        print(f"perf_gate: {total_rows} row(s), {total_missed} MISSED, "
              f"{total_neutral} NEUTRAL (rig {results[0]['rig_class']})")
        for r in results:
            for row in r["rows"]:
                print(f"  {row['verdict']:12s} {row['metric']}")
        print(f"{'PASS' if not total_missed else 'FAIL'}: perf_gate")
    return c.EXIT_PASS if not total_missed else c.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
