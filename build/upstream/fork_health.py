"""build/upstream/fork_health.py — the fork-health headline chart (P3-T7).

One generated page — docs/state/fork-health.md (+ JSON) — that answers, at a
glance and per promotion cycle: how much fork surface do we carry (budget
usage per category + total), how fast are seams retiring (ledger velocity),
is the rebase canary green (last drift), are §12.4 assumptions intact, and
where does the security fast-lane clock stand.

SKIP-visibility law (L6): anything not yet measured is printed as an explicit
SKIP row — never silently omitted, never guessed. All numbers carry their
source (manifest | ledger | rebase-run | assumptions-run | sla-clock).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard, repo_root  # noqa: E402
import retirements as retirements_mod  # noqa: E402

STATE_DOC = Path("docs/state/fork-health.md")


def _row(label: str, value: str, status: str, source: str) -> dict[str, str]:
    return {"metric": label, "value": value, "status": status, "source": source}


def budget_rows(manifest_path: Path) -> list[dict[str, str]]:
    """Per-category + total budget usage (same math as the T3 gate)."""
    import yaml
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    caps = data.get("categories", {}) or {}
    total_cap = data.get("total_cap", 150)
    per: dict[str, int] = {}
    for p in data.get("patches") or []:
        per[p.get("category", "?")] = per.get(p.get("category", "?"), 0) + 1
    rows = []
    for cat in sorted(caps):
        used = per.get(cat, 0)
        cap = caps[cat].get("cap") if isinstance(caps[cat], dict) else caps[cat]
        cap_s = f"{used}/{cap}" if cap is not None else f"{used}/∞"
        status = "OK"
        if cap is not None and used > cap:
            status = "OVER"
        rows.append(_row(f"budget:{cat}", cap_s, status, "manifest"))
    total = sum(per.values())
    rows.append(_row("budget:TOTAL", f"{total}/{total_cap}",
                     "OK" if total <= total_cap else "OVER", "manifest"))
    return rows


def collect(root: Path, xr_core_dir: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows: list[dict[str, str]] = []
    manifest = xr_core_dir / "patches" / "manifest.yaml"
    if manifest.exists():
        rows.extend(budget_rows(manifest))
    else:
        rows.append(_row("budget", "manifest not found", "SKIP", "manifest"))

    ledger = retirements_mod.load_ledger(root)
    n = len(ledger.get("retirements", []))
    rows.append(_row("seams-retired (§12.5 reward metric)", str(n),
                     "OK" if n > 0 else "SKIP", "retirements ledger"))
    latest = ledger["retirements"][-1] if n else None
    if latest:
        rows.append(_row("latest retirement", f"{latest['id']} ({latest['mechanism']})",
                         "OK", "retirements ledger"))

    cache = root / "work" / "upstream-cache"
    # last rebase run (drift signal)
    rb = cache / "rebase-report.json"
    if rb.exists():
        rep = json.loads(rb.read_text(encoding="utf-8"))
        verdict = rep.get("verdict", "?")
        nonclean = sum(1 for p in rep.get("patches", []) if p.get("cls") != "clean")
        rows.append(_row("rebase canary (last run)",
                         f"verdict={verdict} ({nonclean} patch(es) non-clean, "
                         f"{rep.get('source', '?')} lane, -> {str(rep.get('to_resolved', '?'))[:12]})",
                         "OK" if verdict == "GREEN" else "DRIFT", "rebase-report.json"))
    else:
        rows.append(_row("rebase canary (last run)", "no run yet this cycle",
                         "SKIP", "rebase-report.json"))

    ar = cache / "assumptions-run.json"
    if ar.exists():
        run = json.loads(ar.read_text(encoding="utf-8"))
        counts = {"PASS": 0, "SKIP": 0, "FAIL": 0}
        for r in run.get("results", []):
            counts[r.get("status", "?")] = counts.get(r.get("status", "?"), 0) + 1
        rows.append(_row("assumptions §12.4",
                         f"{counts['PASS']} PASS / {counts['SKIP']} SKIP / {counts['FAIL']} FAIL",
                         "FAIL" if counts["FAIL"] else "OK", "assumptions-run.json"))
    else:
        rows.append(_row("assumptions §12.4", "no run recorded", "SKIP", "assumptions-run.json"))

    # fast-lane clock vs the current stable/extended tags (drills are labeled)
    drills = sorted(cache.glob("fastlane/*/drill-report-*.json")) if (cache / "fastlane").exists() else []
    if drills:
        last = json.loads(drills[-1].read_text(encoding="utf-8"))
        verdict = last.get("verdict", "?")
        rows.append(_row("fastlane drills", f"last: {last.get('label', '?')} \u2192 "
                         f"{verdict} (SIMULATED; {last.get('simulated_elapsed_hours', '?')}h simulated)",
                         "OK" if verdict == "PASS" else "DRIFT", str(drills[-1].relative_to(root))))
    else:
        rows.append(_row("fastlane drills", "none recorded", "SKIP", "drill-report"))

    freeze = cache / "feature-freeze.json"
    if freeze.exists():
        rows.append(_row("feature-freeze marker", "PRESENT (advisory pre-GA; HARD at P9)",
                         "DRIFT", "feature-freeze.json"))
    else:
        rows.append(_row("feature-freeze marker", "absent", "OK", "feature-freeze.json"))

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": str(manifest),
        "note": "generated page — do not edit by hand; regenerate via "
                "`./scripts/build fork-health`",
    }
    return rows, meta


def render_markdown(rows: list[dict[str, str]], meta: dict[str, Any]) -> str:
    lines = [
        "# Fork health (generated)",
        "",
        f"_Generated {meta['generated_at']} by `build/upstream/fork_health.py` "
        "(`./scripts/build fork-health`). DO NOT EDIT BY HAND._",
        "",
        "Headline table for the current cycle. SKIP rows are honest "
        "not-measured markers (L6) — never guesses.",
        "",
        "| Metric | Value | Status | Source |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['metric']} | {r['value']} | {r['status']} | {r['source']} |")
    lines += [
        "",
        "## Reading the table",
        "",
        "- **budget:*** — patch-budget usage (§1.2 caps; total ≤150). OVER = the T3 gate "
        "blocks CI until a seam retires.",
        "- **seams-retired** — the §12.5 reward metric; SKIP means the zero baseline "
        "(P3 ships with 0 retirements — stated, not hidden).",
        "- **rebase canary** — drift count from the last `rebase` run this cycle; "
        "DRIFT routes owner issue bundles (T2).",
        "- **assumptions §12.4** — blocking surface checks; FAIL = P0 artifact + "
        "promotion block.",
        "- **fastlane drills** — SIMULATED security-lane rehearsals (T5); real "
        "activations come with the first security tag after GA.",
        "- **feature-freeze marker** — §15-R1 kill-switch signal (advisory pre-GA; "
        "the P9 dashboard makes it HARD — stated).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-fork-health",
        description="Generate docs/state/fork-health.md (headline chart, SKIP-visible).")
    parser.add_argument("--xr-core", default=None, help="xr-core checkout path")
    parser.add_argument("--out", default=None, help="output markdown path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    xr_core = Path(args.xr_core) if args.xr_core else (root.parent / "xr-core")
    rows, meta = collect(root, xr_core)
    md = render_markdown(rows, meta)
    out = Path(args.out) if args.out else (root / STATE_DOC)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    payload = {"schema_version": 1, "tool": "xr-fork-health", "meta": meta, "rows": rows}
    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for r in rows:
            print(f"{r['status']:<6} {r['metric']}: {r['value']}")
        print(f"\nwrote {out.relative_to(root)} + {json_out.relative_to(root)}")
    skip_or_over = [r for r in rows if r["status"] in ("SKIP", "OVER", "DRIFT")]
    if skip_or_over:
        print(f"({len(skip_or_over)} row(s) SKIP/OVER/DRIFT — visible by design, L6)")
    return 0


if __name__ == "__main__":
    main_with_guard(lambda: main())
