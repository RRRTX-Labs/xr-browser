"""build/qa/perf/gen_perf_budgets.py — transcribe the pinned plan's budgets
into build/qa/perf/perf-budgets.json (P9-T5).

Budgets are data from the pinned plan, never folklore: this generator
extracts each number from the plan markdown with a regex and REFUSES to emit
a row whose number is absent or contradicts the plan (a hand-authored number
that invents or contradicts a budget is a falsification — the law). The
§11.7 rows are scoped to the §11.7 section (so a same-looking number in §4
cannot silently drift in); the core-side rows are transcribed from the §4
bench rows the plan states.

Run:
    python3 build/qa/perf/gen_perf_budgets.py            # write the JSON
    python3 build/qa/perf/gen_perf_budgets.py --check    # CI: committed == generated
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qa"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError, \
    stable_json  # noqa: E402

PLAN_FILE = "docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md"
OUT = "build/qa/perf/perf-budgets.json"

# Each row: (id, metric, unit, value_us_if_time, surface, assert_class,
#            owner, note). The §11.7 rows are extracted from the §11.7
# section; the core-side rows from §4 (regexes anchored on their phase
# wording).
SECTION_117 = "## 11.7 Performance budgets"


def _extract_117(section: str, pattern: str) -> int:
    m = re.search(pattern, section)
    if not m:
        raise RunnerError(f"§11.7: no match for {pattern!r} — budget absent or "
                        f"reworded in the plan (stop, do not guess)")
    return int(m.group(1))


def _extract_plan(plan: str, pattern: str, why: str) -> int:
    m = re.search(pattern, plan)
    if not m:
        raise RunnerError(f"plan: no match for {why!r} ({pattern!r})")
    return int(m.group(1))


def ms_to_us(v: int) -> int:
    return v * 1000


def build(plan_text: str) -> dict:
    sec = re.search(re.escape(SECTION_117) + r"(.*?)(?=## 11\.8|\Z)",
                    plan_text, re.DOTALL)
    if not sec:
        raise RunnerError("plan: §11.7 section not found")
    s117 = sec.group(1)

    rows: list[dict] = []

    def add(row_id: str, metric: str, unit: str, value, surface: str,
            assert_class: str, owner: str, cite: str, note: str = "") -> None:
        rows.append({"id": row_id, "metric": metric, "unit": unit,
                     "value": value, "surface": surface,
                     "assert_class": assert_class, "owner": owner,
                     "plan_cite": cite, "note": note})

    # ---- §11.7 (browser-side; reference-assert only) ----
    add("cold-start", "cold_start_overhead_pct", "percent",
        _extract_117(s117, r"Cold start ≤ Chromium-same-build \+(\d+)%"),
        "browser-side", "reference", "browser-perf",
        "§11.7 (cold start ≤ Chromium-same-build +10%)")
    add("ntp-interactive", "ntp_interactive_ms", "ms",
        _extract_117(s117, r"interactive ≤(\d+) ms"),
        "browser-side", "reference", "browser-perf",
        "§11.7 (NTP→interactive ≤300 ms)")
    palette = re.search(r"palette ≤(\d+)/(\d+) ms", s117)
    if not palette:
        raise RunnerError("§11.7: palette ≤50/150 ms not found")
    add("palette-warm", "palette_warm_ms", "ms", int(palette.group(1)),
        "browser-side", "reference", "commands",
        "§11.7 (palette ≤50 ms interactive warm)")
    add("palette-cold", "palette_cold_ms", "ms", int(palette.group(2)),
        "browser-side", "reference", "commands",
        "§11.7 (palette ≤150 ms cold)")
    add("panel-open", "panel_open_ms", "ms",
        _extract_117(s117, r"panel open ≤(\d+) ms"),
        "browser-side", "reference", "browser-perf",
        "§11.7 (panel open ≤150 ms)")
    add("identity-switch", "identity_switch_ms", "ms",
        _extract_117(s117, r"identity switch ≤(\d+) ms"),
        "browser-side", "reference", "identity",
        "§11.7 (identity switch ≤200 ms) + §4 P14 switch ≤200 ms")
    add("filter-decision", "filter_decision_p99_ms", "ms",
        _extract_117(s117, r"filter decision p99 ≤(\d+) ms/request"),
        "core-side", "trend", "shield",
        "§11.7 (filter decision p99 ≤1 ms/request); core-side measurable "
        "once P11 lands")
    add("memory-default", "memory_default_mb", "MB",
        _extract_117(s117, r"memory ≤(\d+) MB"),
        "browser-side", "reference", "shield",
        "§11.7 (memory ≤80 MB default list sets)")
    add("idle-identity", "idle_identity_mb", "MB",
        _extract_117(s117, r"per-idle-identity ≤(\d+) MB"),
        "browser-side", "reference", "identity",
        "§11.7 (per-idle-identity ≤40 MB)")
    add("farbling", "farbling_first_read_ms", "ms",
        _extract_117(s117, r"farbling ≤(\d+) ms"),
        "browser-side", "reference", "identity",
        "§11.7 (farbling ≤4 ms first-read)")
    add("tab-scroll-500", "tab_scroll_500_fps", "fps",
        _extract_117(s117, r"500-tab scroll (\d+) fps"),
        "browser-side", "reference", "tabs",
        "§11.7 (500-tab scroll 60 fps mid-tier)")
    add("benchmarks-3pct", "benchmark_delta_pct", "percent",
        _extract_117(s117, r"within (\d+)% of same-milestone"),
        "browser-side", "reference", "browser-perf",
        "§11.7 (Speedometer/MotionMark/JetStream within 3%)")
    add("leak-fuzz-runtimes", "leak_fuzz_runtimes", "ceiling", None,
        "browser-side", "reference", "privacy",
        "§11.7 (leak-suite and fuzz runtimes inside §4 ceilings) — "
        "qualitative: no numeric budget stated in §11.7",
        "qualitative; the numeric ceilings live in the owning §4 rows")

    # ---- §4 core-side rows (trend-assertable; measured in-sandbox) ----
    # metric = the bench key in xr-core/*/tests/bench-results.json so the
    # comparator matches real bench output without a hand mapping.
    add("resolve-cached", "cache_warm_pinned_read_us", "us",
        _extract_plan(plan_text, r"p99 ≤ (\d+) µs cached", "resolve cached"),
        "core-side", "trend", "policy",
        "§4 P6 Perf (Resolve() p99 ≤5 µs cached; bench key "
        "cache_warm_pinned_read)")
    add("resolve-cold", "resolve_cold_us", "us",
        _extract_plan(plan_text, r"≤ (\d+) µs cold", "resolve cold"),
        "core-side", "trend", "policy",
        "§4 P6 Perf (Resolve() p99 ≤200 µs cold)")
    add("snapshot-apply", "snapshot_apply_us", "us",
        ms_to_us(_extract_plan(plan_text, r"snapshot apply ≤ (\d+) ms",
                               "snapshot apply")),
        "core-side", "trend", "policy",
        "§4 P6 Perf (snapshot apply ≤2 ms; bench key snapshot_apply_40, "
        "normalized by the comparator)")
    add("theme-apply", "theme_apply_us", "us",
        ms_to_us(_extract_plan(plan_text, r"theme apply ≤ (\d+) ms",
                               "theme apply")),
        "core-side", "trend", "themes",
        "§4 P8 Perf (theme apply ≤100 ms)")

    return {"schema_version": 1, "generated_from": PLAN_FILE,
            "rows": rows}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="gen_perf_budgets", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed perf-budgets.json drifted")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    plan = repo / PLAN_FILE
    if not plan.exists():
        print(f"FAIL: plan file missing at {plan}")
        return EXIT_FAIL
    try:
        doc = build(plan.read_text(encoding="utf-8"))
    except ToolError as exc:
        print(f"FAIL: {exc}")
        return EXIT_FAIL
    new = stable_json(doc) + "\n"
    out = repo / OUT
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != new:
            print(f"FAIL: {OUT} drifted from the pinned plan — regenerate "
                  f"with gen_perf_budgets.py (budgets are data, never "
                  f"folklore)")
            return EXIT_FAIL
        print(f"PASS: gen_perf_budgets --check ({len(doc['rows'])} rows "
              f"transcribed, diff-clean)")
        return EXIT_PASS
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new, encoding="utf-8")
    if args.json:
        print(new, end="")
    else:
        print(f"wrote {OUT} ({len(doc['rows'])} rows)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
