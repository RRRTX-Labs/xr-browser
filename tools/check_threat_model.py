"""check_threat_model.py — threat-model v0 structural gate (Plan P1-T13).

Plan §9.1: the threat model is machine-checked and "shipping a feature
that changes the model without updating the model is a blocked merge".
This gate verifies the v0 document's STRUCTURE and BINDINGS so a
softening or deletion cannot pass silently:

  1. Header: declares version v0, names the bound plan file, and embeds
     the plan's full SHA-256 — which must equal the actual hash of the
     pinned plan in this repo (the model is bound to an exact plan).
  2. Merge-blocking sentence present (the model is a release gate).
  3. Assets table has at least 3 rows.
  4. Adversaries table: header contains the honesty column
     "Does NOT protect against"; rows T1..T11 each exist and their
     "Does NOT protect against" cell is non-empty (DR-09/DR-18: the
     honesty column is product law — a missing or softened cell blocks
     the merge).
  5. Invariants section: at least 12 numbered items, each linking the
     plan copy in this repo.
  6. Out of scope section explicitly names T8 and T9 (stated, not
     footnoted).

Scope honesty (L5): this is a structural/integrity checker. It does not
judge whether the adversary analysis is correct (that is human review,
S0); it prevents silent deletion and unbound drift.

Exit codes: 0 = pass, 1 = fail, 2 = usage.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from _common import (
    PLAN_FILE,
    THREAT_MODEL_FILE,
    ToolError,
    add_common_flags,
    emit,
    main_with_usage_guard,
    sha256_file,
)

REQUIRED_ADVERSARIES = [f"T{i}" for i in range(1, 12)]
HONESTY_COL = "Does NOT protect against"
MIN_ASSETS = 3
MIN_INVARIANTS = 12
PLAN_FILENAME = "XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    return m.group(1)


def _table_rows(section_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.fullmatch(r"\|(?:\s*:?-{2,}:?\s*\|)+\s*", s):
            continue
        rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def run(args: argparse.Namespace) -> int:
    root = Path(args.repo or ".").resolve()
    fails: list[str] = []
    info: dict[str, Any] = {"tool": "check_threat_model"}

    tm_path = root / THREAT_MODEL_FILE
    if not tm_path.exists():
        raise ToolError(f"missing threat model: {THREAT_MODEL_FILE}")
    text = tm_path.read_text(encoding="utf-8")

    # 1. Header bindings.
    if not re.search(r"Version:\*\*\s*v0", text):
        fails.append("header: version is not declared v0")
    if PLAN_FILENAME not in text.split("## How to read")[0]:
        fails.append(f"header: does not name the bound plan file {PLAN_FILENAME}")
    header = text.split("## How to read")[0]
    sha_m = re.findall(r"([0-9a-f]{64})", header)
    plan_path = root / PLAN_FILE
    if not plan_path.exists():
        fails.append(f"pinned plan missing: {PLAN_FILE} (cannot verify model binding)")
    elif not sha_m:
        fails.append("header: no 64-hex SHA-256 found in the header block")
    else:
        actual = sha256_file(plan_path)
        if actual not in sha_m:
            fails.append(f"header SHA-256 does not match pinned plan hash {actual}")
        else:
            info["plan_sha256"] = actual

    # 2. Merge-blocking sentence.
    if "blocked merge" not in text:
        fails.append("missing merge-blocking statement (Plan §9.1: model change without update = blocked merge)")

    # 3. Assets.
    assets_rows = _table_rows(_section(text, "Assets"))
    asset_data = [r for r in assets_rows if r and r[0].startswith("A")]
    info["assets"] = len(asset_data)
    if len(asset_data) < MIN_ASSETS:
        fails.append(f"Assets table has {len(asset_data)} rows (< {MIN_ASSETS})")

    # 4. Adversaries.
    adv_sec = _section(text, "Adversaries")
    adv_rows = _table_rows(adv_sec)
    if not adv_rows or HONESTY_COL not in " | ".join(adv_rows[0]):
        fails.append(f"Adversaries table header lacks the honesty column {HONESTY_COL!r}")
    else:
        col = adv_rows[0].index(HONESTY_COL)
        found: dict[str, bool] = {}
        for r in adv_rows[1:]:
            if not r or not re.fullmatch(r"T\d+", r[0]):
                continue
            found[r[0]] = len(r) > col and r[col].strip() not in ("", "—")
        for t in REQUIRED_ADVERSARIES:
            if t not in found:
                fails.append(f"adversary {t}: row missing")
            elif not found[t]:
                fails.append(f"adversary {t}: 'Does NOT protect against' cell is empty (honesty column is law)")
        info["adversaries_present"] = sorted(found)

    # 5. Invariants.
    inv_sec = _section(text, "Invariants")
    inv_items = re.findall(rf"^\d+\.\s+\*\*(?:[^*]+):\*\*.*?\[Plan §1\.12-\d+\]\({re.escape(PLAN_FILENAME)}\)", inv_sec, re.MULTILINE)
    info["invariants_linked"] = len(inv_items)
    if len(inv_items) < MIN_INVARIANTS:
        fails.append(f"Invariants section has {len(inv_items)} plan-linked items (< {MIN_INVARIANTS})")

    # 6. Out of scope.
    oos = _section(text, "Out of scope")
    if not oos:
        fails.append("Out of scope section missing")
    for t in ("T8", "T9"):
        if not re.search(rf"\b{t}\b", oos):
            fails.append(f"Out of scope does not explicitly name {t}")

    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="check_threat_model.py",
        description="Structural gate for docs/threat-model.md v0 (Plan §9.1).",
    )
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
