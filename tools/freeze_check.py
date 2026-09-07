#!/usr/bin/env python3
"""tools/freeze_check.py — FROZEN.yaml + review-packet gate (P5, DoD #8).

Checks docs/contracts/FROZEN.yaml:
  * every §1.11 item (14) is present;
  * each row's review packet exists with status REVIEW-COMPLETE;
  * each packet carries the required checklist rows (narrow surface / typed
    errors / no generic exec / fuzz target required before integration);
  * `ratified: PENDING` on every row.

HARD BAN (encoded as a check, mirrored by a test): an agent-written
`ratified: RATIFIED` / `ratified: true` / `FROZEN-APPROVED` anywhere in
FROZEN.yaml FAILS. Ratification is HG-26 (human).

No YAML dependency (stdlib): FROZEN.yaml uses the simple block form this tool
parses directly.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

EXPECTED_ITEMS = {
    "effective-policy", "policy-resolver", "identity-manager", "shield",
    "route-manager", "vault-service", "guard-ledger", "download-safety",
    "activity-log", "command-descriptor", "list-bundle-manifest",
    "update-manifest", "isolation-card", "settings-theme-schema",
}
CHECKLIST_ROWS = [
    "narrow surface",
    "typed errors",
    "no generic exec",
    "fuzz target required before integration",
]
BANNED_RATIFIED = re.compile(r"ratified:\s*(RATIFIED|true|yes|APPROVED)", re.IGNORECASE)
FROZEN_APPROVED = re.compile(r"FROZEN[-_ ]APPROVED", re.IGNORECASE)


def _parse_contracts(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    in_contracts = False
    for line in text.splitlines():
        if line.strip() == "contracts:":
            in_contracts = True
            continue
        if not in_contracts:
            continue
        m = re.match(r"\s*-\s*id:\s*(\S+)", line)
        if m:
            if cur:
                rows.append(cur)
            cur = {"id": m.group(1)}
            continue
        m = re.match(r"\s+(\w+):\s*(\S+)", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2)
    if cur:
        rows.append(cur)
    return rows


def check(repo: Path) -> list[str]:
    fails: list[str] = []
    fp = repo / "docs/contracts/FROZEN.yaml"
    if not fp.exists():
        return ["FROZEN.yaml missing"]
    text = fp.read_text()
    # Strip full-line and inline comments so the ban does not trip on the
    # comment that documents the ban itself.
    noncomment = "\n".join(re.sub(r"#.*$", "", ln) for ln in text.splitlines())

    # Hard ban: no agent-written ratification / freeze-complete.
    if BANNED_RATIFIED.search(noncomment):
        fails.append("FROZEN.yaml contains a ratified verdict — HG-26 is human-only")
    if FROZEN_APPROVED.search(noncomment):
        fails.append("FROZEN.yaml contains FROZEN-APPROVED — not an agent state")

    rows = _parse_contracts(text)
    seen = {r["id"] for r in rows}
    for missing in EXPECTED_ITEMS - seen:
        fails.append(f"FROZEN.yaml missing §1.11 item: {missing}")
    for extra in seen - EXPECTED_ITEMS:
        fails.append(f"FROZEN.yaml has unknown item: {extra}")

    for r in rows:
        if r.get("status") != "REVIEW-COMPLETE":
            fails.append(f"{r['id']}: status != REVIEW-COMPLETE ({r.get('status')})")
        if r.get("ratified") != "PENDING":
            fails.append(f"{r['id']}: ratified must be PENDING (got {r.get('ratified')})")
        pkt = r.get("packet")
        if not pkt:
            fails.append(f"{r['id']}: no packet path")
            continue
        pp = repo / "docs/contracts" / pkt
        if not pp.exists():
            fails.append(f"{r['id']}: packet not found: {pkt}")
            continue
        ptext = pp.read_text().lower()
        for row in CHECKLIST_ROWS:
            if row not in ptext:
                fails.append(f"{r['id']}: packet missing checklist row {row!r}")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="freeze_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    fails = check(Path(args.repo).resolve())
    if args.json:
        import json
        print(json.dumps({"tool": "freeze_check",
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: freeze_check")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
