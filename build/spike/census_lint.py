"""census_lint.py — enforce the papercut census schema (P4-T6).

The census is only useful if it is complete and actionable, so the Plan's
named surfaces and field set are enforced rather than requested:

  * every named surface is present (by keyword match over the row text);
  * every row has all 9 columns, none empty, no placeholder ("TBD", "?");
  * the owner is one of the Plan's owner letters {A, B, E, F, G};
  * the patch estimate parses as "<n> files x <category> [+ ...]" and every
    category is a real §1.2 budget category;
  * the severity is S1/S2/S3 and the landing phase looks like a phase token;
  * (P14-T9) the fix-closure table has EXACTLY one row per census id, a
    status from {closed-core, matrix-covered, exception-documented,
    open-browser}, a closing artifact whose path EXISTS in the repo or the
    pinned sibling, and — for open-browser rows — a non-empty method for
    the browser half (a NOT-RUN row must carry its method; the cited-path
    law, applied to the census);
  * (P14-CLOSE C-5) the ledger table has EXACTLY one row per census id; its
    status equals the closure status; its owner and budget equal the census
    row's; its test cell cites an existing path; a closed-core or
    matrix-covered row carries `yes: <log>` with an existing transcript; an
    open-browser row carries `NOT-RUN: <method>` with an existing path.

Exit 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, repo_root  # noqa: E402

DEFAULT_DOC = "docs/spike-identity/papercut-census.md"
COLUMNS = ["id", "surface", "what breaks", "repro", "severity", "owner",
           "patch estimate (files x category)", "landing phase",
           "attacker-observable cross-identity"]
N_SURFACE_COLS = 9

# The Plan's named surfaces. A row matches by keyword so wording can evolve.
NAMED_SURFACES = {
    "downloads": ["download"],
    "printing": ["print"],
    "DevTools attach": ["devtools"],
    "omnibox providers": ["omnibox"],
    "cross-identity drag-and-drop": ["drag-and-drop", "drag and drop"],
    "find-in-page": ["find-in-page"],
    "PiP": ["picture-in-picture", "pip"],
    "SW notifications": ["notification"],
    "chrome:// pages": ["chrome://"],
    "autofill UI": ["autofill"],
    "tab search + soft-reuse corner cases": ["tab search"],
    "favicon cache": ["favicon"],
    "desktop drag": ["desktop drag"],
}

VALID_OWNERS = {"A", "B", "E", "F", "G"}
VALID_SEVERITY = {"S1", "S2", "S3"}
BUDGET_CATEGORIES = {"branding", "hook_points", "blink_seams", "content_seams",
                     "network_seams", "ui", "extension_chokepoint"}
ESTIMATE_RE = re.compile(r"^\s*(\d+)\s+files?\s*x\s+([\w_]+)\s*$")
PHASE_RE = re.compile(r"^P\d{1,2}$")
PLACEHOLDERS = {"tbd", "?", "-", "—", "", "n/a", "todo", "fixme"}

# ---- P14-T9: the fix-closure table ---------------------------------------
CLOSURE_HEADER = ["id", "P14 outcome", "status",
                  "closing artifact (verified to exist)",
                  "the browser half (method when it runs)"]
N_CLOSURE_COLS = 5
VALID_CLOSURE = {"closed-core", "matrix-covered", "exception-documented",
                 "open-browser"}
N_LEDGER_COLS = 6
RUN_RE = re.compile(r"\b(yes|NOT-RUN):\s*((?:\.\./xr-core/)?[\w./-]+)")
ARTIFACT_PATH_RE = re.compile(r"(\.\./xr-core/[\w./-]+|[a-z]+/[\w./-]+)")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != N_SURFACE_COLS:
            continue
        if set(cells[0]) <= set("-: ") or cells[0].lower() == "id":
            continue          # separator / header
        rows.append(cells)
    return rows


def lint(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        raise ToolError(f"census not found: {path}")
    rows = parse_rows(path)
    failures: list[str] = []
    if not rows:
        return [], [f"{path}: no census rows parsed (table shape changed?)"]

    checked: list[dict[str, Any]] = []
    seen_text: list[str] = []
    for cells in rows:
        rid = cells[0]
        row = dict(zip(COLUMNS, cells))
        seen_text.append(" ".join(cells).lower())
        checked.append(row)

        for col in COLUMNS:
            val = row[col].strip()
            if val.lower() in PLACEHOLDERS:
                failures.append(f"{rid}: column {col!r} is empty/placeholder")
            elif "TODO" in val or "FIXME" in val:
                failures.append(f"{rid}: column {col!r} contains TODO/FIXME "
                                "(an unowned estimate is not an estimate)")

        if row["owner"].strip() not in VALID_OWNERS:
            failures.append(f"{rid}: owner {row['owner']!r} not in "
                            f"{sorted(VALID_OWNERS)}")
        if row["severity"].strip() not in VALID_SEVERITY:
            failures.append(f"{rid}: severity {row['severity']!r} not in "
                            f"{sorted(VALID_SEVERITY)}")
        if not PHASE_RE.match(row["landing phase"].strip()):
            failures.append(f"{rid}: landing phase {row['landing phase']!r} is "
                            f"not a phase token (P<n>)")

        est = row["patch estimate (files x category)"]
        for part in re.split(r"\s*\+\s*", est):
            m = ESTIMATE_RE.match(part)
            if not m:
                failures.append(f"{rid}: patch estimate {part!r} does not parse "
                                f"as '<n> files x <category>'")
                continue
            if m.group(2) not in BUDGET_CATEGORIES:
                failures.append(f"{rid}: budget category {m.group(2)!r} is not a "
                                f"§1.2 category {sorted(BUDGET_CATEGORIES)}")

    blob = " || ".join(seen_text)
    for name, keywords in NAMED_SURFACES.items():
        if not any(k in blob for k in keywords):
            failures.append(f"named surface missing from the census: {name!r}")

    ids = [r["id"] for r in checked]
    dupes = {i for i in ids if ids.count(i) > 1}
    for d in sorted(dupes):
        failures.append(f"duplicate census id: {d}")
    root = path.parents[2] if len(path.parents) > 2 else None
    failures += lint_closure(path, checked, root_hint=root)
    failures += lint_ledger(path, checked, root_hint=root)
    return checked, failures


def _resolve(root: Path, token: str) -> Path:
    p = Path(token)
    return (root / p).resolve() if not p.is_absolute() else p


def lint_closure(path: Path, census_rows: list[dict[str, Any]],
                 root_hint: Path | None = None) -> list[str]:
    """Enforce the P14 fix-closure table (one honest row per census id)."""
    failures: list[str] = []
    root = root_hint if root_hint is not None else path.parents[2]
    closures: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != N_CLOSURE_COLS or not re.match(r"^C-\d{2}$",
                                                        cells[0]):
            continue
        if cells[0].lower() in closures:
            failures.append(f"closure: duplicate row for {cells[0]}")
        closures[cells[0]] = cells
    census_ids = {r["id"] for r in census_rows}
    for cid in sorted(census_ids - set(closures)):
        failures.append(f"closure: census id {cid} has no closure row")
    for cid in sorted(set(closures) - census_ids):
        failures.append(f"closure: row {cid} matches no census id")
    for cid, cells in sorted(closures.items()):
        _rid, _outcome, status, artifact, browser_half = cells
        if status not in VALID_CLOSURE:
            failures.append(f"closure {cid}: status {status!r} not in "
                            f"{sorted(VALID_CLOSURE)}")
        tokens = [m.group(1).rstrip(".,;)") for m in
                  ARTIFACT_PATH_RE.finditer(artifact)]
        if not tokens:
            failures.append(f"closure {cid}: no citable path in the "
                            "artifact column")
        elif not any(_resolve(root, tok).exists() for tok in tokens):
            failures.append(f"closure {cid}: artifact path(s) {tokens} do "
                            "not exist (a closing artifact that cannot be "
                            "opened is a claim, not a citation)")
        if status == "closed-core" and not any(
                tok.startswith("../xr-core/") and _resolve(root, tok).exists()
                for tok in tokens):
            failures.append(f"closure {cid}: closed-core must cite an "
                            "existing ../xr-core artifact (the law lives "
                            "in the core)")
        if status == "open-browser" and (
                browser_half.strip().lower() in PLACEHOLDERS
                or len(browser_half.strip()) < 20):
            failures.append(f"closure {cid}: open-browser row must name "
                            "the method that will prove the fix (the "
                            "cited-path law)")
    return failures


def _norm(est: str) -> str:
    return " + ".join(" ".join(p.split()) for p in re.split(r"\s*\+\s*",
                                                            est.strip()))


def lint_ledger(path: Path, census_rows: list[dict[str, Any]],
                root_hint: Path | None = None) -> list[str]:
    """Enforce the P14-CLOSE ledger (status/test/owner/budget, zero silent)."""
    failures: list[str] = []
    root = root_hint if root_hint is not None else path.parents[2]
    statuses: dict[str, str] = {}
    ledger: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _cells(line) if line.strip().startswith("|") else []
        if len(cells) == N_CLOSURE_COLS and re.match(r"^C-\d{2}$", cells[0]):
            statuses[cells[0]] = cells[2]
        if len(cells) == N_LEDGER_COLS and re.match(r"^C-\d{2}$", cells[0]):
            if cells[0] in ledger:
                failures.append(f"ledger: duplicate row for {cells[0]}")
            ledger[cells[0]] = cells
    census = {r["id"]: r for r in census_rows}
    for cid in sorted(set(census) - set(ledger)):
        failures.append(f"ledger: census id {cid} has no ledger row (a "
                        "silent row)")
    for cid in sorted(set(ledger) - set(census)):
        failures.append(f"ledger: row {cid} matches no census id")
    for cid, cells in sorted(ledger.items()):
        if cid not in census:
            continue
        _rid, status, test, owner, budget, ran = cells
        row = census[cid]
        if status != statuses.get(cid):
            failures.append(f"ledger {cid}: status {status!r} differs from "
                            f"the closure table ({statuses.get(cid)!r})")
        if owner != row["owner"].strip():
            failures.append(f"ledger {cid}: owner {owner!r} differs from the "
                            f"census row ({row['owner'].strip()!r})")
        want = _norm(row["patch estimate (files x category)"])
        if _norm(budget) != want:
            failures.append(f"ledger {cid}: budget {budget!r} differs from "
                            f"the census estimate ({want!r})")
        tokens = [m.group(1).rstrip(".,;)") for m in
                  ARTIFACT_PATH_RE.finditer(test)]
        if not any(_resolve(root, t).exists() for t in tokens):
            failures.append(f"ledger {cid}: test cell cites no existing path "
                            f"({tokens})")
        runs = {k: [] for k in ("yes", "NOT-RUN")}
        for m in RUN_RE.finditer(ran):
            runs[m.group(1)].append(m.group(2).rstrip(".,;)"))
        for kind, paths in runs.items():
            for tok in paths:
                if not _resolve(root, tok).exists():
                    failures.append(f"ledger {cid}: '{kind}:' path {tok!r} "
                                    "does not exist")
        if status in ("closed-core", "matrix-covered") and not runs["yes"]:
            failures.append(f"ledger {cid}: {status} needs 'yes: <log>' (a "
                            "closed row with no transcript is a claim)")
        if status == "open-browser" and not runs["NOT-RUN"]:
            failures.append(f"ledger {cid}: open-browser needs 'NOT-RUN: "
                            "<method>' (a NOT-RUN row must carry its method)")
        if not runs["yes"] and not runs["NOT-RUN"]:
            failures.append(f"ledger {cid}: run-here cell says neither "
                            "'yes:' nor 'NOT-RUN:'")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="lint the papercut census schema")
    ap.add_argument("--doc", default=DEFAULT_DOC)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        root = repo_root()
        p = Path(args.doc)
        doc = p if p.is_absolute() else root / p
        rows, failures = lint(doc)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    ok = not failures
    if args.json:
        print(json.dumps({"doc": str(args.doc), "rows": len(rows),
                          "named_surfaces": sorted(NAMED_SURFACES),
                          "failures": failures,
                          "status": "pass" if ok else "fail"}, indent=2))
    else:
        print(f"census rows: {len(rows)}  named surfaces required: "
              f"{len(NAMED_SURFACES)}")
        for f in failures:
            print(f"FAIL: {f}")
        print(f"{'PASS' if ok else 'FAIL'}: census-lint")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
