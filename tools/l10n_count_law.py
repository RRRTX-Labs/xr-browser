#!/usr/bin/env python3
"""tools/l10n_count_law.py — a verdict-bearing assertion compares DERIVED
values, never an embedded number (P13-C-P0.1c).

THE DEFECT THIS CLOSES
----------------------
`tools/tests/test_p8_t5_l10n.py:48` read, verbatim, at e503f9e:

    assert "OK (127 messages" in r.stdout
    # P11-T6: +36 shield; P12-T6: +14 cosmetic

The TOOL was green (it reports whatever the file actually holds) and the TEST
was red, because a number had been copied out of a transcript and into an
assertion, with a comment tracking which phase last bumped it. Every phase that
adds a string must remember to edit that literal, so the literal is not a gate —
it is a time bomb that fires on the phase that forgets, and the phase that
forgets is always a later one.

At the pin today the same file reports **136** messages and the literal still
said 127: three phases had edited it, and P13 (the +5 panel.tab.* titles) had
not. Refreshing 127 -> 136 would have reproduced the defect with a fresher
number, so the number is not refreshed — it is REMOVED. Two derived quantities
are compared instead:

  1. the count the TOOL reports, parsed out of its own stdout transcript, and
  2. an INDEPENDENT count of `<message>` elements in the same `.grdp`.

If those disagree, one of the two is lying about the file and the lane fails.
The independent count then faces a RATCHET (`docs/qa/l10n-ratchet.json`): the
string source is grow-only, so a drop is a finding, and raising the ratchet is a
deliberate, reviewed act rather than a side-effect of adding a string. (Shape
precedent: P8's `ratchet: "916 (grow-only)"` row in `perf-budgets.json`.)

WHY IT TAKES A TRANSCRIPT
-------------------------
The live gate captures `grdp_check`'s stdout to a file and hands it here, rather
than piping the two together: a verdict may never ride a pipeline exit code
(`tools/negatives/lib.sh` was fixed for exactly this in `f969499`), and a
captured transcript is what makes the failure testable. Feeding this tool a
STALE transcript is the registered negative — "a `.grdp` with an extra message
while the tool reports the old count" — and without the transcript argument
that case could not be written at all.

THE LAW, NAMED (docs/process/gate-law.md):
  A verdict-bearing assertion compares derived values, never an embedded number.

Scope: this file governs the xr_strings.grdp count because that is where the
defect was found. The same grep over the tree (`grep -rn 'assert ".*[0-9]\\{2,\\}'
tools/tests/ | grep -iE "messages|cases|count"`) returns this one hit and no
others; the remaining numeric assertions in `tools/tests/` are law CONSTANTS
(the 380-line ceiling, index mode 100755, the 400 LOC ceiling) or fixture-local
counts, and are cited as such in evidence/P13-CLOSE/.

Exit: 0 pass · 1 fail · 2 usage. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

TOOL_LINE_RE = re.compile(r"OK\s*\((\d+)\s+messages")
RATCHET_DEFAULT = "docs/qa/l10n-ratchet.json"


def independent_count(grdp: Path) -> int:
    """`<message>` elements in the file, counted without asking the tool."""
    root = ET.parse(grdp).getroot()
    return sum(1 for m in root if m.tag == "message")


def reported_count(transcript: str) -> int | None:
    """The count the tool put in its own stdout, or None when it said nothing.

    None is deliberate: an absent count is not zero, and treating "the tool
    printed no PASS line" as agreement would be the vacuity this whole family of
    laws exists to remove.
    """
    m = TOOL_LINE_RE.search(transcript)
    return int(m.group(1)) if m else None


def ratchet_value(path: Path) -> int | None:
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    v = doc.get("messages")
    return int(v) if isinstance(v, int) else None


def check(grdp: Path, transcript: str, ratchet: Path | None) -> list[str]:
    """Findings; [] == pass. Derived vs derived, then derived vs ratchet."""
    fails: list[str] = []
    if not grdp.is_file():
        return [f"BLOCKED-LAYOUT: no .grdp at {grdp} — the count law has nothing "
                f"to count (this is not a pass)"]
    derived = independent_count(grdp)
    reported = reported_count(transcript)
    if reported is None:
        fails.append(f"count-law: the tool's transcript carries no "
                     f"'OK (N messages' line, so there is no reported count to "
                     f"compare against the {derived} the file actually holds")
    elif reported != derived:
        fails.append(f"count-law: {grdp.name} carries {derived} <message> "
                     f"elements but the tool reported {reported} — one of the "
                     f"two is lying about the file; a stale transcript is the "
                     f"usual cause")
    if ratchet is not None:
        floor = ratchet_value(ratchet)
        if floor is None:
            fails.append(f"count-law: no readable `messages` integer in "
                         f"{ratchet} — a ratchet that cannot be read is not a "
                         f"floor")
        elif derived < floor:
            fails.append(f"count-law: {grdp.name} holds {derived} messages, "
                         f"below the grow-only ratchet {floor} ({ratchet}) — a "
                         f"dropping string source loses user-visible copy, and "
                         f"lowering the ratchet is a reviewed act, not an edit")
    return fails


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="l10n_count_law", description=__doc__)
    ap.add_argument("--grdp", required=True, help="the .grdp to count")
    ap.add_argument("--tool-stdout", required=True,
                    help="captured stdout transcript of tools/grdp_check.py "
                         "(captured to a FILE, never piped: no verdict rides a "
                         "pipeline exit code)")
    ap.add_argument("--ratchet", default=RATCHET_DEFAULT,
                    help=f"grow-only floor file (default: {RATCHET_DEFAULT})")
    ap.add_argument("--no-ratchet", action="store_true")
    # House style: `--check` is the diff-clean/verdict form. This tool only has
    # that form — it never writes — so the flag is accepted and documented
    # rather than left out for a caller to guess.
    ap.add_argument("--check", action="store_true",
                    help="assert instead of report (this tool has no other mode)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    grdp = Path(args.grdp)
    transcript = Path(args.tool_stdout)
    if not transcript.is_file():
        print(f"BLOCKED-LAYOUT: no transcript at {transcript} — the count law "
              f"compares the tool's own words against the file", file=sys.stderr)
        return EXIT_USAGE
    ratchet = None if args.no_ratchet else Path(args.ratchet)
    if ratchet is not None and not ratchet.is_file():
        ratchet = None
    fails = check(grdp, transcript.read_text(encoding="utf-8"), ratchet)
    derived = independent_count(grdp) if grdp.is_file() else -1
    if args.json:
        print(json.dumps({"tool": "l10n_count_law", "grdp": str(grdp),
                          "derived_messages": derived,
                          "reported_messages": reported_count(
                              transcript.read_text(encoding="utf-8")),
                          "ratchet": str(ratchet) if ratchet else None,
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=1))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        if not fails:
            floor = ratchet_value(ratchet) if ratchet else None
            print(f"PASS: l10n_count_law — the tool's reported count and an "
                  f"independent count of {grdp.name} agree at {derived} "
                  f"message(s)"
                  + (f", and {derived} >= the grow-only ratchet {floor}" if floor
                     else " (no ratchet read)"))
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
