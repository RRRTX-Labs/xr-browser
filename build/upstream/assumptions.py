"""build/upstream/assumptions.py — the §12.4 upstream-assumptions runner (P3-T6).

Loads build/upstream/assumptions.yaml and, per row:
  file-contract   → fetch <file> at the target rev through the allowlisted
                    choke point; assert every <contains> string present.
                    FAIL = surface drift = P0 to the owning team BEFORE the
                    promotion lands (§12.4) — exit 1 + a P0 issue artifact.
  pending-feature → SKIP, printed with the reason, never a pass (L6).
                    SKIP counts appear in the fork-health headline table.

Wired into: the rebase bot (real runs embed the summary), the promotion job
(blocking), the nightly lane definition (ci/), and governance CI
(`--validate`: registry schema; the fixture pass/fail paths are unit-tested).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard  # noqa: E402
from fetch import FetchError  # noqa: E402

REGISTRY = Path(__file__).resolve().parent / "assumptions.yaml"
REQUIRED_ROW_FIELDS = {"id", "assumption", "owner", "check_type", "since_rev"}
CHECK_TYPES = {"file-contract", "pending-feature"}


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"assumptions registry parse failure: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ToolError("assumptions registry: schema_version must be 1")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ToolError("assumptions registry: non-empty rows list required")
    return data


def validate_registry(reg: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    seen: set[str] = set()
    for row in reg["rows"]:
        if not isinstance(row, dict):
            fails.append("row is not a mapping")
            continue
        rid = row.get("id")
        missing = REQUIRED_ROW_FIELDS - set(row)
        if missing:
            fails.append(f"row {rid!r}: missing fields {sorted(missing)}")
            continue
        if rid in seen:
            fails.append(f"duplicate row id {rid!r}")
        seen.add(rid)
        if row["check_type"] not in CHECK_TYPES:
            fails.append(f"row {rid}: check_type must be one of {sorted(CHECK_TYPES)}")
        if row["check_type"] == "file-contract":
            if not row.get("file") or not isinstance(row.get("contains"), list) or not row["contains"]:
                fails.append(f"row {rid}: file-contract requires file + non-empty contains[]")
        if row["check_type"] == "pending-feature" and not row.get("reason"):
            fails.append(f"row {rid}: pending-feature requires a printed reason")
    return fails


def run_rows(source, rev: str, reg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute every row against `rev`. Returns (results, failures)."""
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for row in reg["rows"]:
        rid, rtype = row["id"], row["check_type"]
        if rtype == "pending-feature":
            reason = " ".join(row.get("reason", "").split())
            results.append({"id": rid, "status": "SKIP", "reason": reason,
                            "owner": row["owner"], "assumption": row["assumption"]})
            continue
        try:
            text = source.file_text(rev, row["file"])
        except FetchError as exc:
            results.append({"id": rid, "status": "FAIL", "owner": row["owner"],
                            "assumption": row["assumption"],
                            "reason": f"file fetch failed: {exc}"})
            failures.append(f"{rid} ({row['assumption']}): file {row['file']!r} "
                            f"not fetchable at {rev} — {exc}")
            continue
        missing = [s for s in row["contains"] if s not in text]
        if missing:
            results.append({"id": rid, "status": "FAIL", "owner": row["owner"],
                            "assumption": row["assumption"],
                            "reason": f"surface strings missing at {rev}: {missing}"})
            failures.append(f"{rid} ({row['assumption']}): upstream surface drifted at "
                            f"{rev[:12]}… — missing {missing} in {row['file']} "
                            f"(P0 to {row['owner']} BEFORE promotion lands, §12.4)")
        else:
            results.append({"id": rid, "status": "PASS", "owner": row["owner"],
                            "assumption": row["assumption"],
                            "reason": f"{row['file']} surface intact at {rev[:12]}…"})
    return results, failures


def _p0_artifact(row: dict[str, Any], rev: str, reason: str, out_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{stamp}-P0-assumption-{row['id']}.md"
    p.write_text(
        f"# [P0] upstream assumption {row['id']} FAILED at `{rev[:12]}…`\n\n"
        f"- **Assumption (§12.4):** {row['assumption']}\n"
        f"- **Owner:** {row['owner']}\n"
        f"- **Reason:** {reason}\n\n"
        "Failures are P0 to the owning team **before the promotion lands** (§12.4).\n"
        "This artifact was prepared by the assumptions runner (no auto-file; HG-16).\n",
        encoding="utf-8")
    return p


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-assumptions",
        description="§12.4 upstream-assumptions suite: registry validation + "
                    "file-contract checks at a rev (SKIP never passes).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate the registry schema (CI gate)")
    r = sub.add_parser("run", help="run every row against a rev (live, allowlisted)")
    r.add_argument("--rev", help="40-char rev (or omit with --use-deps for the DEPS pin)")
    r.add_argument("--use-deps", action="store_true", help="resolve --rev from DEPS chromium_rev")
    r.add_argument("--out", default="work/upstream-cache", help="artifact dir")
    r.add_argument("--json", action="store_true")
    args = parser.parse_args()

    reg = load_registry()
    if args.cmd == "validate":
        fails = validate_registry(reg)
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: assumptions registry "
              f"({len(reg['rows'])} rows)")
        return 1 if fails else 0

    rev = args.rev
    if args.use_deps:
        from _common import load_deps, repo_root
        rev = load_deps(repo_root())["chromium_rev"]
    if not rev:
        raise ToolError("either --rev <sha> or --use-deps is required")
    if len(rev) != 40 or not all(c in "0123456789abcdef" for c in rev):
        raise ToolError(f"--rev must be a 40-char sha (got {rev!r})")

    from fetch import GitilesFetchSource
    source = GitilesFetchSource()
    results, failures = run_rows(source, rev, reg)

    import json
    summary = {
        "tool": "xr-assumptions", "rev": rev,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pass": sum(1 for r in results if r["status"] == "PASS"),
        "skip": sum(1 for r in results if r["status"] == "SKIP"),
        "fail": sum(1 for r in results if r["status"] == "FAIL"),
        "results": results,
    }
    artifacts = [_p0_artifact(r, rev, r["reason"], Path(args.out))
                 for r in results if r["status"] == "FAIL"]
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for r in results:
            print(f"{r['status']:<5} {r['id']:<4} {r['assumption'][:60]:<62} "
                  f"{('- ' + r['reason'][:80]) if r['status'] != 'PASS' else ''}")
        print(f" totals: {summary['pass']} PASS / {summary['skip']} SKIP / {summary['fail']} FAIL")
    for a in artifacts:
        print(f"P0 artifact: {a}")
    (Path(args.out) / "assumptions-run.json").parent.mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "assumptions-run.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    main_with_guard(lambda: main())
