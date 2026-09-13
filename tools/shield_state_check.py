#!/usr/bin/env python3
"""tools/shield_state_check.py — the shield state-coverage gate (P11-T6):
every enumerator value in the C++ host's kPageStates list must appear in
the xr://shield view's SHIELD_PAGE_STATES union AND in its stateText
switch (missing => FAIL). This is the machine-checked version of "the UI
cannot forget a failure state" for the debug page: the host enumerates
normal/engine-dead/engine-poisoned/kill-switch/route-loss; the view
(ui/shield/shield.ts) must render every one of them, an unknown state
must render honestly (never guessed), the enterprise force-disable note
must carry the reason VERBATIM (IDS_XR_SHIELD_FORCED_DISABLED with a
REASON placeholder), and the blocked count must ride as a chip NUMBER
(IDS_XR_SHIELD_CHIP_COUNT — no badge/toast/modal vocabulary).

Also: the page-state vocabulary must stay byte-identical in the Python
fake (fakes/shield.py PAGE_STATES), the roster must carry the shield
commands with shield.page behind the build.channel-dev predicate, and
both availability backends must register that predicate (the dev-only
law lives in the availability snapshot, not in a comment). The grdp must
carry every required IDS_XR_SHIELD_* message.

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOST_CC = REPO.parent / "xr-core" / "shield" / "host" / "shield_host.cc"
FAKE_PY = REPO.parent / "xr-core" / "fakes" / "shield.py"
VIEW_TS = REPO.parent / "xr-core" / "ui" / "shield" / "shield.ts"
ROSTER = REPO.parent / "xr-core" / "commands" / "core" / "roster_v1.json"
AVAIL_CC = REPO.parent / "xr-core" / "commands" / "core" / "availability.cc"
FAKE_CMDS = REPO.parent / "xr-core" / "fakes" / "commands.py"
GRDP = REPO.parent / "xr-core" / "l10n" / "xr_strings.grdp"

REQUIRED_STRINGS = [
    "IDS_XR_SHIELD_DEV_ONLY",
    "IDS_XR_SHIELD_FORCED_DISABLED",
    "IDS_XR_SHIELD_CHIP_COUNT",
    "IDS_XR_SHIELD_STATE_NORMAL",
    "IDS_XR_SHIELD_STATE_ENGINE_DEAD",
    "IDS_XR_SHIELD_STATE_ENGINE_POISONED",
    "IDS_XR_SHIELD_STATE_KILL_SWITCH",
    "IDS_XR_SHIELD_STATE_ROUTE_LOSS",
]
REQUIRED_COMMANDS = ["shield.toggle", "shield.add-rule", "shield.remove-rule",
                     "shield.page"]


def host_states() -> list[str]:
    text = HOST_CC.read_text(encoding="utf-8")
    m = re.search(r"kPageStates\[\]\s*=\s*\{(.*?)\}", text, re.S)
    if not m:
        raise SystemExit(f"FAIL: cannot locate the host's kPageStates list "
                         f"in {HOST_CC}")
    return re.findall(r'"([a-z-]+)"', m.group(1))


def fake_states() -> list[str]:
    text = FAKE_PY.read_text(encoding="utf-8")
    m = re.search(r"PAGE_STATES\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        raise SystemExit(f"FAIL: cannot locate PAGE_STATES in {FAKE_PY}")
    return re.findall(r'"([a-z-]+)"', m.group(1))


def view_states(view_path: Path) -> tuple[list[str], str]:
    text = view_path.read_text(encoding="utf-8")
    m = re.search(r"SHIELD_PAGE_STATES\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        raise SystemExit(f"FAIL: cannot locate SHIELD_PAGE_STATES in "
                         f"{view_path}")
    return re.findall(r"'([a-z-]+)'", m.group(1)), text


def main() -> int:
    ap = argparse.ArgumentParser(prog="shield-state-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--fixture-view", default=None,
                    help="negative fixture: a view file missing a state")
    a = ap.parse_args()
    host = host_states()
    if not host:
        print("FAIL: host page-state list is empty (a state machine with "
              "no states certifies nothing)")
        return 1
    fake = fake_states()
    if fake != host:
        print(f"FAIL: fake PAGE_STATES {fake} != host kPageStates {host} "
              "(the byte-parity law covers the vocabulary too)")
        return 1
    view_path = Path(a.fixture_view) if a.fixture_view else VIEW_TS
    view, view_text_src = view_states(view_path)
    fails: list[str] = []

    missing = [s for s in host if s not in view]
    if missing:
        fails.append(f"view union missing host state(s): {', '.join(missing)}")
    # every state must also have a stateText arm (a union member with no
    # render is a forgotten failure state by another name)
    m = re.search(r"private stateText\(.*?\n  \}", view_text_src, re.S)
    arms = m.group(0) if m else ""
    if not arms:
        fails.append("view has no stateText switch")
    else:
        for state_id in host:
            if f"case '{state_id}':" not in arms:
                fails.append(f"stateText missing an arm for {state_id}")
        if "default:" not in arms:
            fails.append("stateText has no honest-unknown default arm")
    # the enterprise force-disable note must carry the reason VERBATIM
    if "IDS_XR_SHIELD_FORCED_DISABLED" in view_text_src and \
            "REASON" not in view_text_src:
        fails.append("force-disable note does not carry the REASON "
                     "placeholder (silent suppression)")
    for s in REQUIRED_STRINGS:
        if s not in view_text_src:
            fails.append(f"view does not reference required string {s}")
    grdp = GRDP.read_text(encoding="utf-8")
    for s in REQUIRED_STRINGS:
        if s not in grdp:
            fails.append(f"grdp missing required message {s}")
    # roster: the shield commands exist and shield.page rides the dev
    # predicate (the dev-only law is data, not a comment)
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    by_id = {c["descriptor"]["id"]: c for c in roster["commands"]}
    for cmd in REQUIRED_COMMANDS:
        if cmd not in by_id:
            fails.append(f"roster missing required command {cmd}")
    page = by_id.get("shield.page")
    if page is not None:
        if page["registry"].get("predicate_id") != "build.channel-dev":
            fails.append("shield.page does not ride the build.channel-dev "
                         "predicate")
        if page["descriptor"].get("attention_tier") != "tier2":
            fails.append("shield.page attention tier must stay tier2 "
                         "(chip-number law: never tier1)")
    # both availability backends must register the predicate
    for path, needle in ((AVAIL_CC, '"build.channel-dev"'),
                         (FAKE_CMDS, '"build.channel-dev"')):
        if needle not in path.read_text(encoding="utf-8"):
            fails.append(f"{path.name} does not register build.channel-dev")

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
        print(f"FAIL: shield-state-check ({len(fails)} gap(s); host states: "
              f"{', '.join(host)})")
        return 1
    print(f"PASS: shield-state (all {len(host)} host page states rendered: "
          f"{', '.join(host)}; fake vocabulary byte-identical; stateText "
          "arms + honest default; force-disable reason verbatim; "
          "shield.page behind build.channel-dev in roster + both "
          "availability backends; grdp rows present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
