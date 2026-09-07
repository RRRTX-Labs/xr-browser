"""citation_audit.py — machine-check every file:line citation in the spike docs.

Anti-lazy-cite gate (P4-T7'). A citation table is only as good as its weakest
row, and hand-copied quotes rot silently. For every row in
docs/spike-identity/measured-shared-state.md (and any other doc with the same
column shape) this tool:

  1. re-fetches the cited file at the DEPS `chromium_rev` through
     build/upstream/fetch.py — the only network choke point;
  2. asserts the quoted text is present in that file;
  3. asserts it is at (or within 2 lines of) the cited line number, so a
     re-indentation upstream shows up as drift rather than as a silent pass;
  4. asserts the row does NOT claim a runtime result (every runtime cell must
     read PENDING-FARM until the farm executes — HG-21).

An unfetchable file is BLOCKED-NET and fails the run: it is never checked
against a remembered copy.

Writes evidence/P4/logs/citation-audit.txt. Exit 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import os
import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_p / "upstream"))   # fetch.py — the choke point
        break

from _common import ToolError, load_deps, repo_root  # noqa: E402

CITE_RE = re.compile(r"([\w./-]+\.(?:h|cc|mm|mojom|gn|py|md|yaml|json)):(\d+)")
RUNTIME_OK = {"PENDING-FARM", "N/A", "n/a", "—", "-"}
DEFAULT_DOCS = ["docs/spike-identity/measured-shared-state.md"]
LINE_TOLERANCE = 2


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_rows(path: Path) -> list[dict[str, Any]]:
    """Extract citation rows: a `file:line` cell + the quoted text after it."""
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip().startswith("|"):
            continue
        cells = _cells(line)
        for i, cell in enumerate(cells):
            m = CITE_RE.search(cell)
            if not m:
                continue
            file_path, cited = m.group(1), int(m.group(2))
            quote = ""
            if i + 1 < len(cells):
                quote = cells[i + 1].strip().strip("`").strip()
            # The row id is the first cell when it looks like an id (S-01, P-1).
            rid = cells[0].strip().strip("*").strip("`") if cells else str(lineno)
            runtime = cells[-1].strip().strip("`") if cells else ""
            rows.append({"doc": str(path), "doc_line": lineno, "id": rid,
                         "file": file_path, "line": cited, "quote": quote,
                         "runtime": runtime})
            break
    return rows


def audit(rows: list[dict[str, Any]], rev: str) -> tuple[list[dict[str, Any]], list[str]]:
    from fetch import FetchError, GitilesFetchSource  # the choke point
    src = GitilesFetchSource()
    cache: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    for row in rows:
        f = row["file"]
        if f not in cache:
            try:
                cache[f] = src.file_text(rev, f)
            except FetchError as exc:
                failures.append(f"{row['id']}: BLOCKED-NET cannot fetch {f} at "
                                f"{rev}: {exc}")
                results.append({**row, "verdict": "BLOCKED-NET"})
                continue
        text = cache[f]
        lines = text.splitlines()
        quote = row["quote"]
        # A quote can legitimately occur more than once (e.g. `CHECK(...)` is
        # a substring of `DCHECK(...)`). Score every occurrence and keep the
        # one nearest the cited line: that is the occurrence the author meant,
        # and anything further away than LINE_TOLERANCE is real drift.
        matches = [i + 1 for i, l in enumerate(lines) if quote in l]
        found_at = min(matches, key=lambda n: abs(n - row["line"])) if matches else None

        if not quote:
            failures.append(f"{row['id']} ({row['doc']}:{row['doc_line']}): no "
                            f"quoted text in the row — a citation without a "
                            f"quote cannot be audited")
            results.append({**row, "verdict": "FAIL"})
            continue
        if found_at is None:
            failures.append(f"{row['id']}: quote not found in {f} at {rev}: "
                            f"{quote!r}")
            results.append({**row, "verdict": "FAIL"})
            continue
        drift = abs(found_at - row["line"])
        if drift > LINE_TOLERANCE:
            failures.append(f"{row['id']}: {f} quote is at line {found_at} but "
                            f"the row cites {row['line']} (drift {drift})")
            results.append({**row, "verdict": "DRIFT", "found_at": found_at})
            continue
        if row["runtime"] and row["runtime"] not in RUNTIME_OK:
            failures.append(f"{row['id']}: runtime cell is {row['runtime']!r} — "
                            f"only PENDING-FARM is allowed until the farm runs")
            results.append({**row, "verdict": "FAIL"})
            continue
        results.append({**row, "verdict": "PASS", "found_at": found_at,
                        "drift": drift})
    return results, failures


def main() -> int:
    ap = argparse.ArgumentParser(description="verify every file:line citation "
                                             "in the spike docs at the pin")
    ap.add_argument("--rev", help="40-char chromium rev (default: DEPS)")
    ap.add_argument("--docs", nargs="*", default=DEFAULT_DOCS)
    ap.add_argument("--out", default="evidence/P4/logs/citation-audit.txt")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        root = repo_root()
        deps = load_deps(root)
        rev = args.rev or str(deps.get("chromium_rev") or "")
        if len(rev) != 40:
            raise ToolError(f"unusable chromium rev {rev!r}")
        rows: list[dict[str, Any]] = []
        for d in args.docs:
            p = (root / d) if not Path(d).is_absolute() else Path(d)
            if not p.is_file():
                raise ToolError(f"citation doc not found: {p}")
            rows.extend(parse_rows(p))
        if not rows:
            raise ToolError("no citation rows parsed — table format changed?")
        results, failures = audit(rows, rev)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    outp = root / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in ("PASS", "FAIL", "DRIFT", "BLOCKED-NET")}
    with outp.open("w", encoding="utf-8") as fh:
        # The log is a committed evidence artifact, so it must be reproducible:
        # the pin is the fact, the wall clock is not. Stamp only on request.
        fh.write(f"# citation audit — pinned Chromium {rev}\n")
        if os.environ.get("XR_CITATION_STAMP"):
            fh.write(f"run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        fh.write(f"rows checked: {len(results)}\n")
        fh.write(f"results: {counts}\n")
        fh.write("method: re-fetch each cited file at the pin through "
                 "build/upstream/fetch.py; assert the quote is present within "
                 f"{LINE_TOLERANCE} lines of the cited line number; assert the "
                 "runtime cell is PENDING-FARM.\n\n")
        for r in results:
            fh.write(f"{r['verdict']:<11} {r['id']:<6} {r['file']}:{r['line']}"
                     + (f" (found {r['found_at']})" if 'found_at' in r else "")
                     + f"  {r['quote'][:70]!r}\n")
        if failures:
            fh.write("\nFAILURES:\n")
            for f in failures:
                fh.write(f"  - {f}\n")

    ok = not failures
    if args.json:
        print(json.dumps({"rev": rev, "rows": len(results), "counts": counts,
                          "failures": failures, "status": "pass" if ok else "fail",
                          "log": str(outp.relative_to(root))}, indent=2))
    else:
        for r in results:
            if r["verdict"] != "PASS":
                print(f"{r['verdict']}: {r['id']} {r['file']}:{r['line']}")
        for f in failures:
            print(f"FAIL: {f}")
        print(f"rows checked: {len(results)}  {counts}")
        print(f"log: {args.out}")
        print(f"{'PASS' if ok else 'FAIL'}: citation-audit")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
