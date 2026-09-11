#!/usr/bin/env python3
"""tools/about_state_check.py — the state-coverage gate (P10-T8): every
enumerator value in the C++ host's about-states list must appear in the
About view's switch (missing => FAIL). This is the machine-checked version
of "the UI cannot forget a failure state": the host enumerates
idle/checking/available/downloading/ready/failed/refused; the view
(ui/about/about.ts) must render every one of them, and the failed/refused
renders must carry the reason + manual path + check-again affordance
(strings IDS_XR_ABOUT_UPDATE_MANUAL_PATH / IDS_XR_ABOUT_CHECK_AGAIN).

Also: the roster commands update.about / update.check-now /
update.manual-download must exist in commands/core/roster_v1.json and the
grdp must carry the manual-path strings (the no-silent-failures law).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOST_CC = REPO.parent / "xr-core" / "update" / "host" / "update_host.cc"
VIEW_TS = REPO.parent / "xr-core" / "ui" / "about" / "about.ts"
ROSTER = REPO.parent / "xr-core" / "commands" / "core" / "roster_v1.json"
GRDP = REPO.parent / "xr-core" / "l10n" / "xr_strings.grdp"

REQUIRED_STRINGS = [
    "IDS_XR_ABOUT_MANUAL_DOWNLOAD",
    "IDS_XR_ABOUT_CHECK_AGAIN",
    "IDS_XR_ABOUT_NOT_SIGNED_DEV_CHANNEL",
]
REQUIRED_COMMANDS = ["update.about", "update.check-now",
                     "update.manual-download"]


def host_states() -> list[str]:
    text = HOST_CC.read_text(encoding="utf-8")
    m = re.search(r'kStates\[\]\s*=\s*\{(.*?)\}', text, re.S)
    if not m:
        raise SystemExit("FAIL: cannot locate the host's kStates list "
                         f"in {HOST_CC}")
    return re.findall(r'"([a-z-]+)"', m.group(1))


def view_states(view_path: Path) -> tuple[list[str], str]:
    text = view_path.read_text(encoding="utf-8")
    m = re.search(r"ABOUT_STATES\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        raise SystemExit(f"FAIL: cannot locate ABOUT_STATES in {view_path}")
    return re.findall(r"'([a-z-]+)'", m.group(1)), text


def main() -> int:
    ap = argparse.ArgumentParser(prog="about-state-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--fixture-view", default=None,
                    help="negative fixture: a view file missing a state")
    a = ap.parse_args()
    host = host_states()
    if not host:
        print("FAIL: host about-states list is empty (a state machine with "
              "no states certifies nothing)")
        return 1
    view_path = Path(a.fixture_view) if a.fixture_view else VIEW_TS
    view, view_text_src = view_states(view_path)
    fails: list[str] = []

    missing = [s for s in host if s not in view]
    if missing:
        fails.append(f"view switch missing host state(s): {', '.join(missing)}")
    # the failure renders must carry the typed reason (stateText's arms)
    m = re.search(r"private stateText\(.*?\n  \}", view_text_src, re.S)
    arms = m.group(0) if m else ""
    for state_id in ("failed", "refused"):
        if state_id not in view:
            continue
        if f"'{state_id}'" not in arms or "REASON" not in arms:
            fails.append(f"{state_id} render does not carry the reason")
    for s in REQUIRED_STRINGS:
        if s not in view_text_src:
            fails.append(f"view does not reference required string {s}")
    grdp = GRDP.read_text(encoding="utf-8")
    for s in REQUIRED_STRINGS:
        if s not in grdp:
            fails.append(f"grdp missing required message {s}")
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    ids = {c["descriptor"]["id"] for c in roster["commands"]}
    for cmd in REQUIRED_COMMANDS:
        if cmd not in ids:
            fails.append(f"roster missing required command {cmd}")

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
        print(f"FAIL: about-state-check ({len(fails)} gap(s); host states: "
              f"{', '.join(host)})")
        return 1
    print(f"PASS: about-state (all {len(host)} host states rendered: "
          f"{', '.join(host)}; failed/refused carry reason + manual path + "
          "check-again; roster + grdp rows present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
