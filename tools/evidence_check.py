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
  strict scope  --strict with no --only auto-covers every P<n> newer than the
                P2 legacy exemption (P3+); P1/P2 stay exempt (HG-25). A new
                phase is gated the moment its bundle lands — the list that used
                to be hardcoded in run_checks.sh is now derived (debt T0).
  human-gates   evidence/<phase>/human-gates.md exists and is non-empty
  honesty       --strict: rows may not claim a verdict whose vocabulary is
                not declared, and a VERIFIED row must cite >=1 real artifact
  P9-T12        (P9+ bundles) three machine-side "green" amendments:
                (a) a ci-run row must carry ci_run+ci_job ids, and --strict
                    resolves them through build/upstream/fetch.py (the
                    chokepoint) — conclusion != success or a head_sha the
                    bundle does not record is a FAIL, offline is a visible
                    SKIP;
                (b) any PARTIAL/BLOCKED/HUMAN-GATED row requires a non-empty
                    not_done_by_design list (P8 shipped [] with partial work);
                (c) every local-run row must cite a logs/* transcript.

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

# P1/P2 bundles ship qualified statuses (e.g. "VERIFIED (mock; ...)"). The
# HG-25 ruling keeps them on the tolerant legacy path; every phase newer than
# P2 is strict (bare tokens, resolved citations, source labels). A hardcoded
# list here was the P6/P7 debt T0 closes: it silently skipped new bundles.
LEGACY_EXEMPT_MAX_PHASE = 2
_PHASE_DIR_RE = re.compile(r"^P(\d+)$")

# P9-T12: the machine-side "green" amendments bind P9+ bundles only. P3-P8
# predate the rule (P6 has a HUMAN-GATED row and no not_done_by_design, for
# one) — grandfathered, exactly like the P2 legacy exemption. P9's own bundle
# is the first checked under them.
T12_MIN_PHASE = 9
CI_RUN_LABEL = "ci-run"
_COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_OPEN_STATUS_PREFIXES = ("PARTIAL", "BLOCKED", "HUMAN-GATED")


from evidence_ci import CI_RESOLVER  # noqa: E402 - sibling tool module (P10-T0-d split)

def strict_default_phases(root: Path) -> list[str]:
    """Phase dirs strict mode auto-covers when no explicit --only is given.

    Every ``P<n>`` bundle with ``n > LEGACY_EXEMPT_MAX_PHASE`` (i.e. newer
    than the P2 legacy exemption), sorted numerically. New phases are covered
    automatically — nothing to remember to add to a gate list.
    """
    out: list[str] = []
    if root.is_dir():
        for d in root.iterdir():
            m = _PHASE_DIR_RE.fullmatch(d.name) if d.is_dir() else None
            if m and int(m.group(1)) > LEGACY_EXEMPT_MAX_PHASE:
                out.append(d.name)
    return sorted(out, key=lambda n: int(_PHASE_DIR_RE.fullmatch(n).group(1)))


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


def _phase_number(dirname: str) -> int | None:
    m = _PHASE_DIR_RE.fullmatch(dirname)
    return int(m.group(1)) if m else None


def _is_open_status(status: str) -> bool:
    """PARTIAL / BLOCKED* / HUMAN-GATED — work shipped but not as done."""
    return status.strip().upper().startswith(_OPEN_STATUS_PREFIXES)


def _bundle_commits(doc: dict[str, Any]) -> set[str]:
    """Commit shas the bundle records (pin + repos block), for ci-run head
    matching. A ci-run row is green only if its head_sha is one of these."""
    commits: set[str] = set()
    for key in ("pin",):
        if isinstance(doc.get(key), str):
            commits.update(_COMMIT_RE.findall(doc[key]))
    repos = doc.get("repos")
    if isinstance(repos, dict):
        for value in repos.values():
            texts = value if isinstance(value, list) else [value]
            for t in texts:
                if isinstance(t, str):
                    commits.update(_COMMIT_RE.findall(t))
    return commits




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

    phase_num = _phase_number(path.parent.name)
    if strict and phase_num is not None and phase_num >= T12_MIN_PHASE:
        # (b) a PARTIAL/BLOCKED/HUMAN-GATED row must be explained: the bundle
        # carries a non-empty not_done_by_design (P8 shipped [] with partial
        # work — that hole closes here).
        if any(_is_open_status(str(r.get("status", ""))) for r in rows):
            ndbd = doc.get("not_done_by_design")
            if not isinstance(ndbd, list) or not ndbd:
                fails.append(f"{path}: a PARTIAL/BLOCKED/HUMAN-GATED row "
                             f"requires a non-empty not_done_by_design list "
                             f"(P9-T12)")
        # (a) ci-run rows: ids required; --strict resolves them machine-side.
        bundle_commits = _bundle_commits(doc)
        for row in rows:
            if row.get("source") != CI_RUN_LABEL:
                continue
            rid = row.get("id", "<no id>")
            run_id, job_id = row.get("ci_run"), row.get("ci_job")
            if not run_id or not job_id:
                fails.append(f"{path}: ci-run row {rid} must carry ci_run "
                             f"and ci_job ids (P9-T12)")
                continue
            verdict = CI_RESOLVER(int(run_id), int(job_id), bundle_commits)
            if verdict is True:
                continue
            if verdict is False:
                fails.append(f"{path}: ci-run row {rid} run {run_id}/"
                             f"{job_id} is not certifiably green (P9-T12)")
            else:
                print(f"SKIP: ci-run verification for {rid}: {verdict}",
                      file=sys.stderr)
        # (c) a local-run row must name its logs/* transcript.
        for row in rows:
            if row.get("source") != "local-run":
                continue
            rid = row.get("id", "<no id>")
            cites = [str(e).strip() for e in (row.get("evidence") or [])
                     if isinstance(e, str) and PATHISH_RE.match(str(e).strip())]
            if not any(c.startswith("logs/") for c in cites):
                fails.append(f"{path}: local-run row {rid} must cite a "
                             f"logs/* transcript (P9-T12)")

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
                    help="also require cited artifact paths to exist + source "
                         "labels; with no --only, auto-covers every P<n> newer "
                         "than the P2 legacy exemption (P3+)")
    ap.add_argument("--only", default="",
                    help="comma-separated phase dirs to check (default: all; "
                         "in --strict mode without --only, auto P3+)")
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
    elif args.strict:
        # strict with no explicit list auto-covers every bundle newer than the
        # P2 legacy exemption (P3+), so a new phase is gated the moment it lands.
        wanted = set(strict_default_phases(root))
        files = [f for f in files if f.parent.name in wanted]
    if not files:
        scope = (f" strict-auto P>{LEGACY_EXEMPT_MAX_PHASE}"
                 if (args.strict and not args.only) else "")
        print(f"error: no evidence/*/evidence.json under {root}{scope}",
              file=sys.stderr)
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
