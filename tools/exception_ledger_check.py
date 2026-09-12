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

P11-T4 adds the SECOND ledger: `## shield exception ledger rows` — the
disclosure table for XR Shield exception scopes (the runtime authorization
data of xr-core/shield/host_protocol.md's exception surface: exception-add /
exception-remove / exception-sweep / site-toggle). Each row is
`| scope_id | scope | reason | expiry | owner |` with: scope = comma-joined
`k=v` dimensions (k ∈ site/rule_id/list_id/identity/workspace, ≥1, no
dupes); reason non-empty (the T2 scope grammar requires it); expiry = a
MONOTONIC integer ≥ -1 (-1 = never) checked against `--as-of` — the shield
ledger never carries wall-clock dates (determinism law; the as-of is the
argument, expiry inclusive: as_of ≥ expiry ⇒ expired). Rows with a
`site-toggle:<site>` scope_id must carry exactly the scope cell
`site=<site>` and reason `user-site-toggle` (the host's canonical shape —
drift here is a lie about what the toggle granted). The section must EXIST; ZERO rows pass
(the v1 host is stateless and ships no standing exceptions — a row lands in
the same commit as the surface that grants it). These rows are NOT §1.13
isolation-matrix cells and reuse no waivers semantics (ADR-0046).

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
SHIELD_HEADING = "## shield exception ledger rows"
SHIELD_DIMS = ("identity", "list_id", "rule_id", "site", "workspace")
TOGGLE_PREFIX = "site-toggle:"
TOGGLE_REASON = "user-site-toggle"


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


def shield_rows(text: str) -> tuple[bool, list[dict[str, str]]]:
    """Parse the shield exception-ledger table. Returns (section_present,
    rows) — rows keep the raw cells; validation lives in check_shield."""
    rows: list[dict[str, str]] = []
    present = False
    in_table = False
    for line in text.splitlines():
        if line.strip() == SHIELD_HEADING:
            present = True
            in_table = True
            continue
        if in_table and line.strip().startswith("#"):
            break
        if in_table and line.strip().startswith("|") and \
                "---" not in line and "scope_id" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0]:
                rows.append({"scope_id": cells[0], "scope": cells[1],
                             "reason": cells[2], "expiry": cells[3],
                             "owner": cells[4] if len(cells) > 4 else ""})
    return present, rows


def parse_scope_cell(cell: str) -> str:
    """Validate the scope cell grammar; returns "" or a failure reason."""
    if not cell:
        return "scope cell is empty (≥1 dimension required)"
    seen: set[str] = set()
    for part in cell.split(","):
        part = part.strip()
        if "=" not in part:
            return f"scope dimension {part!r} is not k=v"
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if key not in SHIELD_DIMS:
            return f"scope dimension {key!r} not in {'/'.join(SHIELD_DIMS)}"
        if not value:
            return f"scope dimension {key!r} has an empty value"
        if key in seen:
            return f"scope dimension {key!r} appears twice"
        seen.add(key)
    return ""


def check_shield(repo: Path, as_of: int) -> tuple[list[str], list[str], int]:
    """The P11-T4 shield ledger: grammar + reason + monotonic expiry vs the
    --as-of argument (deterministic; expiry boundary INCLUSIVE, matching the
    host's SweepAsOf law). Returns (failures, info, row_count)."""
    fails: list[str] = []
    info: list[str] = []
    lim = repo / LIMITATIONS
    if not lim.exists():
        return [f"{LIMITATIONS}: missing — shield ledger cannot be "
                "checked"], [], 0
    present, rows = shield_rows(lim.read_text(encoding="utf-8"))
    if not present:
        return [f"{LIMITATIONS}: no '{SHIELD_HEADING}' section (P11-T4: the "
                "shield exception ledger must exist — zero rows is fine, "
                "a missing section is drift)"], [], 0
    for row in rows:
        sid = row["scope_id"]
        bad = parse_scope_cell(row["scope"])
        if bad:
            fails.append(f"{sid}: {bad}")
        if not row["reason"]:
            fails.append(f"{sid}: reason is empty (every exception scope "
                         "carries a reason — T2 grammar)")
        if not row["owner"]:
            fails.append(f"{sid}: ledger row has an empty owner")
        try:
            expiry = int(row["expiry"])
        except ValueError:
            fails.append(f"{sid}: expiry {row['expiry']!r} is not a "
                         "monotonic integer (no wall-clock dates in the "
                         "shield ledger)")
            expiry = None
        if expiry is not None:
            if expiry < -1:
                fails.append(f"{sid}: expiry {expiry} < -1 (-1 = never is "
                             "the floor)")
            elif expiry >= 0 and as_of >= expiry:
                fails.append(f"{sid}: expiry {expiry} has passed as of "
                             f"--as-of {as_of} (sweep it or extend it in "
                             "the same commit)")
        if sid.startswith(TOGGLE_PREFIX):
            want_scope = "site=" + sid[len(TOGGLE_PREFIX):]
            if row["scope"] != want_scope:
                fails.append(f"{sid}: toggle row must carry scope cell "
                             f"{want_scope!r} (the host's canonical shape)")
            if row["reason"] != TOGGLE_REASON:
                fails.append(f"{sid}: toggle row must carry reason "
                             f"{TOGGLE_REASON!r}")
        if not any(f.startswith(sid + ":") for f in fails):
            info.append(f"ok(shield): {sid} scope={row['scope']} "
                        f"expiry={row['expiry']}")
    if not rows:
        info.append("ok(shield): ledger section present, zero rows (the v1 "
                    "host ships no standing exceptions)")
    return fails, info, len(rows)


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
    p.add_argument("--as-of", type=int, default=0,
                   help="monotonic as-of for the SHIELD ledger's expiry "
                        "column (deterministic; default 0 = fresh boot; "
                        "the §1.13 ledger keeps its wall-clock expiry "
                        "law — P9 legacy, unchanged)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.as_of < 0:
        print("usage: --as-of must be >= 0")
        return EXIT_USAGE

    repo = Path(args.repo).resolve()
    mj = Path(args.matrix_json)
    if not mj.is_absolute():
        mj = repo / mj
    fails, info = check(repo, mj)
    shield_fails, shield_info, shield_n = check_shield(repo, args.as_of)
    fails += shield_fails
    info += shield_info
    if args.json:
        print(json.dumps({"tool": "exception_ledger_check",
                          "count": len(fails), "violations": fails,
                          "as_of": args.as_of, "shield_rows": shield_n,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        for i in info:
            print(i)
        print(f"{'PASS' if not fails else 'FAIL'}: exception_ledger_check "
              f"({len(info)} ledger row(s) ok, {shield_n} shield row(s), "
              f"{len(fails)} failure(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
