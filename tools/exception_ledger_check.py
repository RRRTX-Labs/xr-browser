#!/usr/bin/env python3
"""tools/exception_ledger_check.py — the §1.13-in-same-commit law (P9-T2).

Plan §11.4: "a new exception requires a §1.13/§9.1 disclosure row in the same
commit (CI)". This gate makes that mechanical: every cell the isolation
matrix marks `EXCEPTION` must have a row in docs/limitations.md's exception
ledger with a non-empty owner AND a non-empty expiry date.

The ledger is a markdown table under the `## §1.13 exception ledger rows`
heading; each row is `| mechanism | owner | expiry | note |`. A mechanism id
in the matrix without a matching row — or a row with an empty owner/expiry,
or an expiry in the past — fails the gate. A ledger row for a mechanism the
matrix no longer marks exception is an orphan (also a failure: a stale
disclosure is drift).

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError  # noqa: E402

LIMITATIONS = "docs/limitations.md"
MATRIX_JSON = "../xr-core/test/isolation/isolation-matrix.json"
LEDGER_HEADING = "## §1.13 exception ledger rows"


def ledger_rows(text: str) -> dict[str, dict[str, str]]:
    """Parse the §1.13 exception-ledger table from limitations.md."""
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in text.splitlines():
        if line.strip() == LEDGER_HEADING:
            in_table = True
            continue
        if in_table and line.strip().startswith("#") and \
                not line.strip().startswith(LEDGER_HEADING):
            break
        if in_table and line.strip().startswith("|") and \
                "---" not in line and "mechanism" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0]:
                rows[cells[0]] = {"owner": cells[1], "expiry": cells[2],
                                  "note": cells[3] if len(cells) > 3 else ""}
    return rows


def check(repo: Path, matrix_json: Path) -> tuple[list[str], list[str]]:
    """Returns (failures, info lines)."""
    fails: list[str] = []
    info: list[str] = []
    lim = repo / LIMITATIONS
    if not lim.exists():
        return [f"{LIMITATIONS}: missing — exception ledger cannot be checked"], []
    rows = ledger_rows(lim.read_text(encoding="utf-8"))
    if not rows:
        return [f"{LIMITATIONS}: no §1.13 exception-ledger rows found"], []

    try:
        doc = json.loads(matrix_json.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{matrix_json}: unreadable ({exc})"], []
    exception_mechs = sorted({c["mechanism"] for c in doc.get("cells", [])
                              if c.get("verdict") == "EXCEPTION"})
    today = date.today()

    for mech in exception_mechs:
        row = rows.get(mech)
        if row is None:
            fails.append(f"{mech}: EXCEPTION cell has no §1.13 ledger row "
                         f"(add owner + expiry in the same commit)")
            continue
        if not row["owner"]:
            fails.append(f"{mech}: ledger row has an empty owner")
        if not row["expiry"]:
            fails.append(f"{mech}: ledger row has an empty expiry")
            continue
        try:
            when = date.fromisoformat(row["expiry"])
        except ValueError:
            fails.append(f"{mech}: expiry {row['expiry']!r} is not a date")
            continue
        if when < today:
            fails.append(f"{mech}: expiry {row['expiry']} is in the past")
        info.append(f"ok: {mech} -> owner={row['owner']} expiry={row['expiry']}")

    for mech in rows:
        if mech not in exception_mechs:
            fails.append(f"{mech}: ledger row is an orphan (no EXCEPTION cell "
                         f"in the matrix cites it)")
    return fails, info


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="exception_ledger_check",
                                description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--matrix-json", default=MATRIX_JSON)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    mj = Path(args.matrix_json)
    if not mj.is_absolute():
        mj = repo / mj
    fails, info = check(repo, mj)
    if args.json:
        print(json.dumps({"tool": "exception_ledger_check",
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        for i in info:
            print(i)
        print(f"{'PASS' if not fails else 'FAIL'}: exception_ledger_check "
              f"({len(info)} exception row(s), {len(fails)} failure(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
