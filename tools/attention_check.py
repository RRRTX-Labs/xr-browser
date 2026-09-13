#!/usr/bin/env python3
"""tools/attention_check.py — the Attention-Budget gate, extracted from
the inline tools/run_checks.sh P8-T6 lane (plan P11 §architecture
invariant 7: the enforcement lived inline in the gate script; this phase
moves it into a tool, which also buys the script headroom) and extended
with the P11-T6 shield rule.

Two jobs:
1. P8-T6 policy of record: docs/state/attention-budget.md must exist and
   carry the local-counters law markers (no upload / LOCAL COUNTERS ONLY
   / 90-day retention / day granularity / deny-preserve / zero bytes) so
   the citation in xr-core/settings/core/counters.h can never dangle.
2. P11-T6 shield rule: a shield surface that raises a modal, animates a
   badge, or reports anything other than the single chip count is a
   FAIL. Mechanically: the ledger's "## Shield (P11-T6)" section markers
   must be present, the shield view must reference the chip-count string,
   and NO shield surface (xr-core/ui/shield/*.ts, the IDS_XR_SHIELD_*
   grdp messages, ui/shell.ts) may carry attention-escalation vocabulary
   (toast / badge / modal / notification).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = REPO.parent / "xr-core"
LEDGER = REPO / "docs/state/attention-budget.md"

# The P8-T6 markers, verbatim from the inline lane this tool replaces.
POLICY_MARKERS = ["no upload", "LOCAL COUNTERS ONLY", "90", "day",
                  "deny-preserve", "zero bytes"]
# The P11-T6 shield-section markers (whitespace-normalized on both sides).
SHIELD_MARKERS = ["## Shield (P11-T6)", "chip count", "no toasts",
                  "no badges-on-timer", "no modals", "no notifications",
                  "silent otherwise", "tier2", "attention_check.py"]

BANNED = re.compile(r"\b(toast|badge|modal|notification)s?\b", re.IGNORECASE)
CHIP_STRING = "IDS_XR_SHIELD_CHIP_COUNT"


def shield_surfaces() -> list[Path]:
    views = sorted((CORE / "ui" / "shield").glob("*.ts"))
    return views + [CORE / "ui" / "shell.ts"]


def grdp_shield_messages() -> list[tuple[str, str]]:
    grdp = CORE / "l10n" / "xr_strings.grdp"
    if not grdp.exists():
        return []
    text = grdp.read_text(encoding="utf-8")
    return [(m.group(1), m.group(2)) for m in re.finditer(
        r'<message name="(IDS_XR_SHIELD_[A-Z0-9_]+)"[^>]*>(.*?)</message>',
        text, re.S)]


def main() -> int:
    ap = argparse.ArgumentParser(prog="attention-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--fixture-view", default=None,
                    help="negative fixture: a shield view file carrying "
                         "banned attention vocabulary")
    a = ap.parse_args()
    fails: list[str] = []

    # --- 1) the P8-T6 policy of record ----------------------------------
    if not LEDGER.exists():
        fails.append(f"{LEDGER.relative_to(REPO)} missing (the counters.h "
                     "citation would dangle)")
        flat = ""
    else:
        flat = re.sub(r"\s+", " ", LEDGER.read_text(encoding="utf-8"))
    for m in POLICY_MARKERS:
        if m not in flat:
            fails.append(f"P8-T6 policy marker missing or drifted: {m!r}")

    # --- 2) the P11-T6 shield rule ---------------------------------------
    for m in SHIELD_MARKERS:
        # case-insensitive: the section states the law in sentence case
        if re.sub(r"\s+", " ", m).lower() not in flat.lower():
            fails.append(f"shield-section marker missing or drifted: {m!r}")

    surfaces = shield_surfaces()
    if not surfaces:
        fails.append("no shield view surfaces found under xr-core/ui/shield/")
    if a.fixture_view:
        surfaces = [Path(a.fixture_view)]
    for src in surfaces:
        if not src.exists():
            fails.append(f"shield surface missing: {src}")
            continue
        for i, line in enumerate(
                src.read_text(encoding="utf-8").splitlines(), 1):
            if BANNED.search(line):
                fails.append(f"{src.name}:{i} attention-escalation "
                             f"vocabulary: {line.strip()[:72]}")
    view = CORE / "ui" / "shield" / "shield.ts"
    if not a.fixture_view:
        if view.exists() and CHIP_STRING not in view.read_text(
                encoding="utf-8"):
            fails.append(f"shield view does not reference {CHIP_STRING} "
                         "(the single chip count is the only passive "
                         "security counter)")
        for name, body in grdp_shield_messages():
            if BANNED.search(body):
                fails.append(f"grdp {name} carries attention-escalation "
                             "vocabulary")
        if not grdp_shield_messages():
            fails.append("grdp has no IDS_XR_SHIELD_* messages")

    if a.fixture_view:
        # negative fixture: the gate MUST fail
        if fails:
            print(f"ok: negative fixture reddened ({fails[0]})")
            return 0
        print("FAIL: negative fixture did NOT redden (the gate cannot "
              "fail — a coverage gate that cannot fail certifies nothing)")
        return 1

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: attention-check ({len(fails)} gap(s))")
        return 1
    print("PASS: attention-budget (P8-T6 policy markers present; P11-T6 "
          "shield rule: chip count only — no toast/badge/modal/"
          "notification vocabulary in any shield surface or string; "
          f"{len(surfaces)} surface(s) + "
          f"{len(grdp_shield_messages())} shield message(s) scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
