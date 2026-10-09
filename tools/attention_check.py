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
# P12-T6: cosmetic adds rows to the shield page but MUST NOT gain its own
# attention surface — no notification/badge/modal vocabulary for cosmetic
# (the chrome is silent; the Observatory labels page-modifying rows, not a
# pop-up). The marker + the scan below make a planted cosmetic modal RED.
COSMETIC_MARKERS = ["## Cosmetic (P12-T6)", "cosmetic adds rows",
                    "no modal", "no badge", "no notification",
                    "silent otherwise"]
COSMETIC_BANNED = re.compile(
    r"\b(toast|badge|modal|notification)s?\b", re.IGNORECASE)

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


# --- P15-T7: the permission-prompt rule (anchored, never stacked, ceiling) --
PERM_MARKERS = ["## Permissions (P15-T7)", "anchored prompt", "never stacked",
                "demote one tier", "logged", "no modal", "no badge", "no toast",
                "3 per hour"]
PERM_SOURCES = [CORE / "permissions" / "core" / "present.h",
                CORE / "permissions" / "core" / "present.cc"]
# "notification" is a capability name in permission copy, so the permission
# scan bans the escalation nouns only (the shield scan keeps the wider list).
PERM_BANNED = re.compile(r"\b(toast|badge|modal)s?\b", re.IGNORECASE)


def permission_fails(paths: list[Path]) -> list[str]:
    out: list[str] = []
    for src in paths:
        if not src.exists():
            out.append(f"permission surface missing: {src}")
            continue
        for i, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if PERM_BANNED.search(line):
                out.append(f"{src.name}:{i} permission surface carries escalation "
                           f"vocabulary: {line.strip()[:72]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="attention-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--fixture-view", default=None,
                    help="negative fixture: a shield view file carrying "
                         "banned attention vocabulary")
    ap.add_argument("--fixture-permission", default=None,
                    help="negative fixture: a permission surface file carrying "
                         "banned attention vocabulary (P15-T7)")
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

    # --- 2b) the P12-T6 cosmetic rule -------------------------------------
    for m in COSMETIC_MARKERS:
        if re.sub(r"\s+", " ", m).lower() not in flat.lower():
            fails.append(f"cosmetic-section marker missing or drifted: {m!r}")

    # --- 2c) the P15-T7 permission rule ----------------------------------
    for m in PERM_MARKERS:
        if re.sub(r"\s+", " ", m).lower() not in flat.lower():
            fails.append(f"permission-section marker missing or drifted: {m!r}")
    if not a.fixture_view and not a.fixture_permission:
        fails += permission_fails(PERM_SOURCES)
        present = PERM_SOURCES[0]
        if present.exists():
            ptext = present.read_text(encoding="utf-8")
            if "kT3PromptsPerHour = 3" not in ptext:
                fails.append("present.h: the T3 ceiling constant drifted from 3 per hour")
            if "max_stacked = 1" not in ptext:
                fails.append("present.h: max_stacked is no longer 1 (prompts would stack)")

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
        # P12-T6 cosmetic rule: no cosmetic string may escalate attention
        # (a planted modal in a cosmetic label is RED, even though the
        # generic shield scan would also catch it — the rule is named here
        # so a reader knows cosmetic was checked, not merely adjacent).
        for name, body in grdp_shield_messages():
            if name.startswith("IDS_XR_SHIELD_COSMETIC_") and \
                    COSMETIC_BANNED.search(body):
                fails.append(f"cosmetic string {name} carries attention-"
                             "escalation vocabulary")
        if not grdp_shield_messages():
            fails.append("grdp has no IDS_XR_SHIELD_* messages")
        if not any(n.startswith("IDS_XR_SHIELD_COSMETIC_")
                   for n, _ in grdp_shield_messages()):
            fails.append("grdp has no IDS_XR_SHIELD_COSMETIC_* messages "
                         "(the cosmetic rows would drop off the page)")

    if a.fixture_permission:
        # negative fixture: a planted permission surface MUST redden the gate
        pfails = permission_fails([Path(a.fixture_permission)])
        if pfails:
            print(f"ok: negative fixture reddened ({pfails[0]})")
            return 0
        print("FAIL: negative fixture did NOT redden (the permission rule cannot fail)")
        return 1
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
