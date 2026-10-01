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
    law, applied to the census).

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
    failures += lint_closure(path, checked, root_hint=path.parents[2]
                             if len(path.parents) > 2 else None)
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
