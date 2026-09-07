#!/usr/bin/env python3
"""tools/evidence_check.py — evidence-bundle validator (P4-T0.3, debt D-C).

Why this exists: P3 left `evidence/P3/` with only a logs/ directory — no
evidence.json and no human-gates.md — while reporting "104 tests pass". The
claim was true only in a pre-seeded environment; nothing in the repo could
have caught the difference. P1 and P2 set the standard and P3 broke it, so
the standard is now a gate instead of a habit.

Contract: docs/contracts/evidence-bundle-v1.md. Stdlib only (no new deps).

Checks
------
  structure     required top-level keys + types per schema_version
  vocabulary    every row status is in the declared vocabulary (BLOCKED-* ok)
  rows          every DoD/task row has id + text + status + >=1 evidence item
  citations     --strict: every evidence item that looks like a path resolves
                (relative to the phase dir, else the repo root)
  human-gates   evidence/<phase>/human-gates.md exists and is non-empty
  honesty       --strict: rows may not claim a verdict whose vocabulary is
                not declared, and a VERIFIED row must cite >=1 real artifact

Exit: 0 pass · 1 fail (with reasons) · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_KEYS = {
    "phase": str,
    "generated": str,
    "plan": str,
    "dod_rows": (list, dict),
}
OPTIONAL_KEYS = {
    "repos": (dict, str),
    "tasks": dict,
    "verdict_vocabulary": list,
    "policy": str,
    "human_gates": (dict, list),
    "not_done_by_design": list,
    "supersedes": str,
    "toolchain_capture": dict,
    "sources": list,
    "source_labels": list,
}
DEFAULT_VOCAB = ["VERIFIED", "HUMAN-GATED", "SIMULATED", "BLOCKED"]
BLOCKED_RE = re.compile(r"^BLOCKED(?:-[A-Z0-9_]+)*$")
PATHISH_RE = re.compile(r"^[\w./-]+\.\w{1,8}$")


def _status_token(status: str) -> str:
    """Lead verdict token of a status string.

    P1/P2 bundles ship qualified statuses such as
    "VERIFIED (mock; real sync needs a provisioned host)" — the parenthetical
    is a qualifier, not a different verdict. New bundles (P3+) are checked
    --strict and must use bare tokens.
    """
    return re.split(r"[\s(]", status.strip(), maxsplit=1)[0].upper()


def _rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    dod = doc.get("dod_rows", [])
    if isinstance(dod, dict):          # P2 style: id -> row
        for k, v in dod.items():
            if isinstance(v, dict):
                out.append({"id": v.get("id", k), "dod": v.get("dod", ""),
                            "status": v.get("status", ""),
                            "evidence": v.get("evidence", []),
                            **({"source": v["source"]} if "source" in v else {})})
    elif isinstance(dod, list):        # P1/P4 style: list of rows
        for r in dod:
            if isinstance(r, dict):
                out.append(r)
    for k, v in (doc.get("tasks") or {}).items():
        if isinstance(v, dict):
            out.append({"id": k, "dod": v.get("what", ""),
                        "status": v.get("status", ""),
                        "evidence": [v.get("artifact", "")]})
    return out


def check_file(path: Path, repo: Path, strict: bool) -> list[str]:
    """Return a list of failure strings (empty == pass)."""
    fails: list[str] = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: not valid JSON ({exc})"]
    if not isinstance(doc, dict):
        return [f"{path}: top level must be an object"]

    for key, typ in REQUIRED_KEYS.items():
        if key not in doc:
            fails.append(f"{path}: missing required key {key!r}")
        elif not isinstance(doc[key], typ):
            fails.append(f"{path}: key {key!r} must be {typ.__name__}")
    for key, typ in OPTIONAL_KEYS.items():
        if key in doc and not isinstance(doc[key], typ):
            fails.append(f"{path}: key {key!r} has the wrong type")

    vocab = set(doc.get("verdict_vocabulary") or DEFAULT_VOCAB) | set(DEFAULT_VOCAB)
    rows = _rows(doc)
    if not rows:
        fails.append(f"{path}: no DoD/task rows to judge")
    for row in rows:
        rid = row.get("id", "<no id>")
        for field in ("id", "dod", "status", "evidence"):
            if not row.get(field):
                fails.append(f"{path}: row {rid} has empty/missing {field!r}")
        status = str(row.get("status", ""))
        token = _status_token(status)
        if strict:
            if status not in vocab and not BLOCKED_RE.match(status):
                fails.append(f"{path}: row {rid} status {status!r} must be a bare "
                             f"token in {sorted(vocab)} (strict mode: no qualifiers)")
        elif token not in vocab and not BLOCKED_RE.match(token):
            fails.append(f"{path}: row {rid} status {status!r} is not in the "
                         f"declared vocabulary {sorted(vocab)}")
        ev = row.get("evidence")
        if ev is not None and (not isinstance(ev, list) or not ev):
            fails.append(f"{path}: row {rid} evidence must be a non-empty list")

        if strict:
            labels = set(doc.get("source_labels") or [])
            if labels and "source" in row and row["source"] not in labels:
                fails.append(f"{path}: row {rid} source {row['source']!r} not in "
                             f"declared source_labels {sorted(labels)}")
            if labels and "source" not in row:
                fails.append(f"{path}: row {rid} has no source label "
                             f"(required by source_labels in this bundle)")
            cites = [e for e in (ev or []) if isinstance(e, str) and PATHISH_RE.match(e.strip())]
            if str(status).startswith("VERIFIED") and not cites:
                fails.append(f"{path}: row {rid} claims VERIFIED but cites no "
                             f"artifact path")
            phase_dir = path.parent
            for cite in cites:
                c = cite.strip()
                if not ((phase_dir / c).exists() or (repo / c).exists()):
                    fails.append(f"{path}: row {rid} cites missing artifact {c!r}")

    gates = path.parent / "human-gates.md"
    if not gates.exists() or not gates.read_text(encoding="utf-8").strip():
        fails.append(f"{path.parent}: missing or empty human-gates.md "
                     f"(debt D-C — a phase without recorded human gates is not closed)")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="validate evidence/*/evidence.json bundles")
    ap.add_argument("--repo", default=".", help="repository root (default: cwd)")
    ap.add_argument("--dir", default="evidence", help="evidence root (default: evidence)")
    ap.add_argument("--strict", action="store_true",
                    help="also require cited artifact paths to exist + source labels")
    ap.add_argument("--only", default="",
                    help="comma-separated phase dirs to check (default: all)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    root = repo / args.dir
    if not root.is_dir():
        print(f"error: no evidence directory at {root}", file=sys.stderr)
        return 2
    files = sorted(root.glob("*/evidence.json"))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        files = [f for f in files if f.parent.name in wanted]
    if not files:
        print(f"error: no evidence/*/evidence.json under {root}", file=sys.stderr)
        return 2

    results: dict[str, list[str]] = {}
    for f in files:
        results[str(f.relative_to(repo))] = check_file(f, repo, args.strict)
    total = sum(len(v) for v in results.values())
    if args.json:
        print(json.dumps({"checked": list(results), "failures": results,
                          "status": "pass" if total == 0 else "fail"}, indent=2))
    else:
        for name, fails in results.items():
            if fails:
                for x in fails:
                    print(f"FAIL: {name}: {x}")
            else:
                print(f"PASS: {name} ({'strict' if args.strict else 'structural'})")
        print(f"{'PASS' if total == 0 else 'FAIL'}: evidence_check "
              f"({len(files)} bundle(s), {total} failure(s))")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
