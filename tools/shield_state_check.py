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

P14-CLOSE C-3 extends the same law to the xr://identities dev page
(tools/identity_page_states.py): the core's kManagerPageStates ⊆ the view
union + stateText arms, reset-all/manager-page gated on the real
--build-channel, identities.page behind build.channel-dev.

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identity_page_states  # noqa: E402  (P14-CLOSE C-3: the xr://identities half)

REPO = Path(__file__).resolve().parent.parent
HOST_CC = REPO.parent / "xr-core" / "shield" / "host" / "shield_host.cc"
FAKE_PY = REPO.parent / "xr-core" / "fakes" / "shield.py"
VIEW_TS = REPO.parent / "xr-core" / "ui" / "shield" / "shield.ts"
ROSTER = REPO.parent / "xr-core" / "commands" / "core" / "roster_v1.json"
AVAIL_CC = REPO.parent / "xr-core" / "commands" / "core" / "availability.cc"
FAKE_CMDS = REPO.parent / "xr-core" / "fakes" / "commands.py"
GRDP = REPO.parent / "xr-core" / "l10n" / "xr_strings.grdp"
# P13-T3: the Observatory renders the ledger, so the ledger's enum surface is a
# law too. The export's canonical field list must carry every enum-bearing
# property block-event-v1 defines (a new enum value the observatory cannot
# export is a value it silently never shows), and it may not name a property the
# schema does not have (an invented column is a claim about data that does not
# exist). The tab's own row type must carry the fields it filters and drills on.
BLOCK_EVENT_SCHEMA = REPO / "docs/contracts/block-event-v1.schema.json"
OBS_EXPORT = REPO / "tools/observatory_export.py"
OBS_TAB = REPO.parent / "xr-core" / "ui" / "panel" / "observatory-tab.ts"
# Fields whose values come from a closed vocabulary — i.e. values a renderer
# must be able to name, not free text.
ENUM_FIELDS = ("action", "why_code", "request_class", "page_modifying")
TAB_ROW_FIELDS = ("type", "origin", "why_code", "rule_id", "list_id")

REQUIRED_STRINGS = [
    "IDS_XR_SHIELD_DEV_ONLY",
    "IDS_XR_SHIELD_FORCED_DISABLED",
    "IDS_XR_SHIELD_CHIP_COUNT",
    "IDS_XR_SHIELD_STATE_NORMAL",
    "IDS_XR_SHIELD_STATE_ENGINE_DEAD",
    "IDS_XR_SHIELD_STATE_ENGINE_POISONED",
    "IDS_XR_SHIELD_STATE_KILL_SWITCH",
    "IDS_XR_SHIELD_STATE_ROUTE_LOSS",
    # P12-T6: the cosmetic riding row must render (it REPORTS cosmetic_host's
    # state verbatim — never derives it), and every seam-guard enum value
    # must render honestly (the stateText law extended to the guard union).
    "IDS_XR_SHIELD_COSMETIC_HEADING",
    "IDS_XR_SHIELD_COSMETIC_FLAG",
    "IDS_XR_SHIELD_COSMETIC_GENERIC_SET",
    "IDS_XR_SHIELD_COSMETIC_KEY_SET_RULES",
    "IDS_XR_SHIELD_COSMETIC_BLOB_OCCUPANCY",
    "IDS_XR_SHIELD_COSMETIC_SCRIPTLETS",
    "IDS_XR_SHIELD_COSMETIC_REFUSED_ROW",
    "IDS_XR_SHIELD_COSMETIC_DEGRADE",
    "IDS_XR_SHIELD_COSMETIC_SEAM_GUARD",
    "IDS_XR_SHIELD_COSMETIC_GUARD_ARMED",
    "IDS_XR_SHIELD_COSMETIC_GUARD_INERT",
    "IDS_XR_SHIELD_COSMETIC_GUARD_HOOK_DEAD",
    "IDS_XR_SHIELD_COSMETIC_EMPTY",
]
COSMETIC_GUARD_STATES = ["armed", "inert", "hook-dead"]
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


def view_seam_guard_states(view_path: Path) -> list[str]:
    """P12-T6: the seam-guard union the view must render. A state in the
    host's closed guard vocabulary (armed/inert/hook-dead) with no view arm
    is a forgotten debug row. """
    text = view_path.read_text(encoding="utf-8")
    m = re.search(r"COSMETIC_SEAM_GUARD_STATES\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        return []
    return re.findall(r"'([a-z-]+)'", m.group(1))


def export_aliases(path: Path | None = None) -> dict[str, str]:
    """The exporter's declared FIELD_ALIASES (canonical name -> renderer name)."""
    text = (path or OBS_EXPORT).read_text(encoding="utf-8")
    m = re.search(r"^FIELD_ALIASES = \{(.*?)\}", text, re.S | re.M)
    if not m:
        return {}
    return dict(re.findall(r'"([a-z_]+)":\s*"([a-z_]+)"', m.group(1)))


def export_fields(path: Path | None = None) -> list[str]:
    """The exporter's canonical field tuple, read from its own source.

    Read rather than imported: this gate deliberately does not execute another
    tool, and a tuple is a declaration. The pattern is anchored on the
    assignment so a mention of a field in prose cannot satisfy it.
    """
    text = (path or OBS_EXPORT).read_text(encoding="utf-8")
    m = re.search(r"^FIELDS = \((.*?)\)", text, re.S | re.M)
    if not m:
        return []
    return re.findall(r'"([a-z_]+)"', m.group(1))


def block_event_enum_fields() -> list[str]:
    """Property names whose schema carries an `enum` (plus the closed bool)."""
    schema = json.loads(BLOCK_EVENT_SCHEMA.read_text(encoding="utf-8"))
    props = schema.get("properties", {})
    return [name for name, sub in props.items() if isinstance(sub, dict) and "enum" in sub]


def observatory_findings(fixture_export: Path | None = None) -> list[str]:
    """P13-T3's enum surface: export ⊇ schema enums, export ⊆ schema fields."""
    fails: list[str] = []
    schema = json.loads(BLOCK_EVENT_SCHEMA.read_text(encoding="utf-8"))
    props = set(schema.get("properties", {}))
    fields = export_fields(fixture_export)
    if not fields:
        return ["observatory_export.py declares no FIELDS tuple — nothing to check"]
    for name in ENUM_FIELDS:
        if name not in schema.get("properties", {}):
            continue  # the schema dropped it; the schema's own tests own that
        if name not in fields:
            fails.append(f"the export's FIELDS omits {name!r}, an enum-bearing "
                         f"block-event property — a new enum value the "
                         f"observatory cannot export is one it never shows")
    for name in fields:
        if name not in props:
            fails.append(f"the export's FIELDS names {name!r}, which "
                         f"block-event-v1 does not define — an invented column")
    tab = OBS_TAB.read_text(encoding="utf-8") if OBS_TAB.is_file() else ""
    if not tab:
        fails.append(f"{OBS_TAB} is missing — the observatory tab's row type "
                     f"cannot be checked")
    else:
        for name in TAB_ROW_FIELDS:
            if f"{name}:" not in tab:
                fails.append(f"the observatory tab's row type does not carry "
                             f"{name!r}, which it filters or drills on")
    for canonical, alias in export_aliases(fixture_export).items():
        if canonical not in fields:
            fails.append(f"the exporter aliases {canonical!r} to {alias!r} but "
                         f"does not export {canonical!r} — an alias for a column "
                         f"that is not there")
        elif alias not in tab:
            fails.append(f"the exporter declares the alias {alias!r} for "
                         f"{canonical!r} and the tab no longer uses it")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(prog="shield-state-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--fixture-view", default=None,
                    help="negative fixture: a view file missing a state")
    ap.add_argument("--fixture-export", default=None,
                    help="negative fixture: an exporter source whose FIELDS is "
                         "missing an enum-bearing ledger field")
    ap.add_argument("--fixture-identities-view", default=None,
                    help="negative fixture: an identities-core.ts missing a state")
    ap.add_argument("--fixture-identity-host", default=None,
                    help="negative fixture: an identity_host.cc with a gate bypass")
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
    # P12-T6: the seam-guard union must be complete and every guard arm
    # rendered (a dropped guard state is a forgotten "hook-death = cosmetic
    # off, never blank page" row — the exact posture the degrade law owns).
    guard = view_seam_guard_states(view_path)
    if guard != COSMETIC_GUARD_STATES:
        fails.append(f"seam-guard union {guard} != {COSMETIC_GUARD_STATES} "
                     "(every host guard state must be in the view's "
                     "COSMETIC_SEAM_GUARD_STATES)")
    for gs in COSMETIC_GUARD_STATES:
        if f"case '{gs}':" not in view_text_src:
            fails.append(f"seamGuardText missing an arm for {gs}"
                         f" (never guessed)")
    if "seamGuardText" not in view_text_src:
        fails.append("view has no seamGuardText renderer for the cosmetic "
                     "seam-guard row")
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

    fails.extend(observatory_findings(Path(a.fixture_export) if a.fixture_export else None))
    fails.extend(identity_page_states.findings(
        Path(a.fixture_identities_view) if a.fixture_identities_view else None,
        Path(a.fixture_identity_host) if a.fixture_identity_host else None))

    if (a.fixture_view or a.fixture_export or a.fixture_identities_view
            or a.fixture_identity_host):
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
          "availability backends; grdp rows present; cosmetic rows + "
          f"seam-guard union {', '.join(guard)} rendered; observatory enum "
          f"surface: export FIELDS ⊇ {', '.join(ENUM_FIELDS)} and ⊆ the "
          f"block-event-v1 properties, tab row type carries "
          f"{', '.join(TAB_ROW_FIELDS)}; "
          f"{identity_page_states.summary()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
