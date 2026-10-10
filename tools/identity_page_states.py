#!/usr/bin/env python3
"""tools/identity_page_states.py — the xr://identities half of the
state-coverage gate (P14-T7, P14-CLOSE C-3), called by
tools/shield_state_check.py (which owns the exit code and the negatives'
fixture flags; this module keeps that file under the 380-line ceiling).

Laws (each one has a planted negative in tools/negatives/p14c_c3.sh):
1. Every value in the core's kManagerPageStates
   (xr-core/identity/core/manager_page.h, served by identity_host
   `manager-page-states`) is in the view's IDENTITIES_PAGE_STATES union
   (ui/identities/identities-core.ts) and has a `case '<state>':` arm in its
   stateText switch, which also carries an honest-unknown `default:` arm.
2. reset-all is DEV-ONLY BY ENFORCEMENT: in identity_host.cc every branch
   that names "manager-page" or "reset-all" is the one gated branch, whose
   first statement calls DevChannel(channel, ...) and rejects; main() parses
   the real --build-channel option with "release" as the default. The
   view's resetAllAllowed() demands channel === 'dev'.
3. The roster carries identities.page behind build.channel-dev at tier2.
4. Every IDS_XR_IDENTITIES_* id the core or view references exists in the
   grdp, and the required state/dev-only ids are referenced.

Stdlib only. Importable (findings(...) -> list[str]); no exit code here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent.parent / "xr-core"
HEADER = CORE / "identity" / "core" / "manager_page.h"
HOST_CC = CORE / "identity" / "host" / "identity_host.cc"
VIEW_CORE = CORE / "ui" / "identities" / "identities-core.ts"
VIEW_LIT = CORE / "ui" / "identities" / "identities.ts"
ROSTER = CORE / "commands" / "core" / "roster_v1.json"
GRDP = CORE / "l10n" / "xr_strings.grdp"
REQUIRED_IDS = ["IDS_XR_IDENTITIES_DEV_ONLY", "IDS_XR_IDENTITIES_STATE_NORMAL",
                "IDS_XR_IDENTITIES_STATE_EMPTY",
                "IDS_XR_IDENTITIES_STATE_PURGE_UNVERIFIED",
                "IDS_XR_IDENTITIES_STATE_DEV_REFUSED",
                "IDS_XR_IDENTITIES_STATE_UNKNOWN",
                "IDS_XR_IDENTITIES_RESET_ALL_CONFIRM"]
GATED = ("manager-page", "reset-all")


def host_states(header_text: str) -> list[str]:
    m = re.search(r"kManagerPageStates\[\]\s*=\s*\{(.*?)\}", header_text, re.S)
    return re.findall(r'"([a-z-]+)"', m.group(1)) if m else []


def view_states(view_text: str) -> list[str]:
    m = re.search(r"IDENTITIES_PAGE_STATES\s*=\s*\[(.*?)\]", view_text, re.S)
    return re.findall(r"'([a-z-]+)'", m.group(1)) if m else []


def _block_end(text: str, open_brace: int) -> int:
    """Index just past the brace that closes the one at `open_brace`."""
    depth = 0
    for i in range(open_brace, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return i + 1
    return len(text)


def gate_findings(host_text: str) -> list[str]:
    """Law 2 on the host source: every branch naming a gated subcommand is
    either a gated branch (DevChannel(channel, ...) is its first statement,
    and it rejects) or lies INSIDE one; plus the real fail-closed option."""
    fails: list[str] = []
    branches = [m for m in re.finditer(r'cmd == "([a-z-]+)"', host_text)
                if m.group(1) in GATED]
    if not branches:
        return ["identity_host.cc names no manager-page / reset-all branch"]
    gated: list[tuple[int, int]] = []
    for b in branches:
        if any(lo <= b.start() < hi for lo, hi in gated):
            continue  # nested inside an already-gated branch
        brace = host_text.find("{", b.end())
        body = host_text[brace:brace + 600]
        call = body.find("DevChannel(channel")
        stmts = re.sub(r"//[^\n]*", "", body[1:call]) if call >= 0 else ";"
        # an initializer-free declaration has no effect; anything else does
        stmts = re.sub(r"(?m)^\s*std::string \w+;\s*$", "", stmts)
        if call < 0 or ";" in stmts:
            fails.append(f'identity_host.cc: the branch naming "{b.group(1)}" does '
                         f"not call DevChannel(channel, ...) before anything else "
                         f"(a dev-only escape reachable without the gate)")
        elif "EmitReject(" not in body[call:call + 200]:
            fails.append(f'identity_host.cc: the "{b.group(1)}" gate does not reject')
        else:
            gated.append((b.start(), _block_end(host_text, brace)))
    if not re.search(r'std::string channel = "release";', host_text):
        fails.append("identity_host.cc: --build-channel does not default to release "
                     "(the gate must fail CLOSED)")
    if '"--build-channel"' not in host_text:
        fails.append("identity_host.cc: main() does not parse --build-channel")
    return fails


def findings(view_core: Path | None = None, host_cc: Path | None = None) -> list[str]:
    fails: list[str] = []
    host = host_states(HEADER.read_text(encoding="utf-8"))
    if not host:
        return ["manager_page.h: kManagerPageStates is missing or empty"]
    vtext = (view_core or VIEW_CORE).read_text(encoding="utf-8")
    view = view_states(vtext)
    for s in host:
        if s not in view:
            fails.append(f"identities view union missing host state {s}")
    m = re.search(r"export function stateText\(.*?\n\}", vtext, re.S)
    arms = m.group(0) if m else ""
    if not arms:
        fails.append("identities view has no stateText switch")
    else:
        for s in host:
            if f"case '{s}':" not in arms:
                fails.append(f"identities stateText missing an arm for {s}")
        if "default:" not in arms:
            fails.append("identities stateText has no honest-unknown default arm")
    r = re.search(r"export function resetAllAllowed\(.*?\n\}", vtext, re.S)
    if not r or "channel === 'dev'" not in r.group(0):
        fails.append("identities resetAllAllowed() does not demand channel === 'dev'")
    fails += gate_findings((host_cc or HOST_CC).read_text(encoding="utf-8"))
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    page = {c["descriptor"]["id"]: c for c in roster["commands"]}.get("identities.page")
    if page is None:
        fails.append("roster missing required command identities.page")
    else:
        if page["registry"].get("predicate_id") != "build.channel-dev":
            fails.append("identities.page does not ride the build.channel-dev predicate")
        if page["descriptor"].get("attention_tier") != "tier2":
            fails.append("identities.page attention tier must stay tier2")
    grdp = set(re.findall(r'<message name="(IDS_XR_IDENTITIES_[A-Z0-9_]+)"',
                          GRDP.read_text(encoding="utf-8")))
    used = set(re.findall(r"IDS_XR_IDENTITIES_[A-Z0-9_]+",
                          vtext + VIEW_LIT.read_text(encoding="utf-8")))
    for s in sorted(used - grdp):
        fails.append(f"grdp missing message {s} (referenced by ui/identities)")
    for s in REQUIRED_IDS:
        if s not in used:
            fails.append(f"ui/identities does not reference required string {s}")
    return fails


def summary() -> str:
    host = host_states(HEADER.read_text(encoding="utf-8"))
    return (f"identities page: {len(host)} host states ({', '.join(host)}) rendered; "
            f"manager-page/reset-all behind DevChannel + --build-channel (default "
            f"release); identities.page behind build.channel-dev")
