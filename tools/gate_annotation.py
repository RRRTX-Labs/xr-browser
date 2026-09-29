#!/usr/bin/env python3
"""tools/gate_annotation.py — put the reason in the annotation (P13-P0-B).

Why this exists. The hosted failure that cost a phase carried the annotation
"Process completed with exit code 126." — a bare exit code with no lane, no
gate, no reason. `GET /repos/<o>/<r>/check-runs/<id>/annotations` is public on a
public repo, so the text was readable; it simply said nothing. A green/red light
that does not name the bulb is not a diagnostic.

This tool turns a captured gate transcript into exactly one GitHub workflow
command, emitted by the step that ran the gate:

    ::error::<lane>: <first failing gate> - <one-line reason>

Extraction rules (the --why it chose its answer is in the output, never guessed):

  1. the FIRST `LANE FAIL (keep-going): <cmd>` line — the `--keep-going` tally in
     tools/checks/gate_runner.sh names the first lane that failed, which is the
     one a reader should look at first;
  2. else the first line matching `FAIL` (`FAIL: …`, `== FAIL …`, `GATE_EXIT=1`
     is NOT a gate name and is never used as one);
  3. else the annotation says the reason is unavailable and points at the step
     log — it does not invent a cause.

GitHub workflow commands must be single-line: `%`, CR and LF are escaped as
`%25`, `%0D`, `%0A`.

Stdlib only. Exit: 0 emitted · 1 nothing to emit (no failure found in the log) ·
2 usage. `--json` for tests and for machine consumers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_NOTHING, EXIT_USAGE = 0, 1, 2

LANE_FAIL_RE = re.compile(r"^\s*LANE FAIL \(keep-going\):\s*(.+?)\s*$")
FAIL_RE = re.compile(r"^\s*(?:==\s*)?(?:FAIL|FAILED)\b[::]?\s*(.*)$")
# `FAIL: <gate>: <reason>` / `FAIL: <gate> (<reason>)` — split the gate from its
# reason so the annotation reads as a diagnosis, not as the same sentence twice.
GATE_REASON_RE = re.compile(r"^([A-Za-z0-9_./@-]+)\s*[:(]\s*(.*?)[)\s]*$")
UNAVAILABLE = ("reason unavailable (the captured output carries no FAIL line; "
               "open the step log — the gate itself printed nothing machine-readable)")


def _escape(line: str) -> str:
    return line.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _one_line(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


def choose(log_text: str) -> dict:
    """Pick the first failing gate + a one-line reason from a gate transcript."""
    lines = log_text.splitlines()
    keep_going = None
    first_fail = None
    for idx, line in enumerate(lines):
        if keep_going is None:
            m = LANE_FAIL_RE.match(line)
            if m:
                keep_going = (idx, m.group(1))
                continue
        if first_fail is None:
            m = FAIL_RE.match(line)
            if m:
                first_fail = (idx, m.group(1))
    if keep_going is not None:
        idx, gate = keep_going
        reason = _one_line(gate)
        for back in range(idx - 1, max(-1, idx - 12), -1):
            if lines[back].strip():
                reason = _one_line(f"{gate} :: {lines[back]}")
                break
        return {"source": "keep-going tally", "gate": _one_line(gate),
                "reason": reason, "line": idx + 1}
    if first_fail is not None:
        idx, rest = first_fail
        m = GATE_REASON_RE.match(rest)
        gate = _one_line(m.group(1)) if m else _one_line(rest) or _one_line(lines[idx])
        reason = _one_line(m.group(2)) if m else _one_line(rest) or _one_line(lines[idx])
        if not reason:
            for back in range(idx - 1, max(-1, idx - 12), -1):
                if lines[back].strip():
                    reason = _one_line(lines[back])
                    break
        return {"source": "first FAIL line", "gate": gate,
                "reason": reason, "line": idx + 1}
    return {"source": "none", "gate": "", "reason": UNAVAILABLE, "line": 0}


def annotation(lane: str, chosen: dict) -> str:
    if not chosen["gate"]:
        return f"::error::{lane}: gate failed - {chosen['reason']}"
    return f"::error::{lane}: {chosen['gate']} - {chosen['reason']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lane", required=True, help="workflow/job lane name (e.g. governance)")
    ap.add_argument("--log", required=True, help="captured gate transcript")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.log)
    if not path.is_file():
        print(f"usage: log not found: {path}", file=sys.stderr)
        return EXIT_USAGE
    chosen = choose(path.read_text(encoding="utf-8", errors="replace"))
    line = _escape(annotation(args.lane, chosen))
    if args.json:
        print(json.dumps({"lane": args.lane, "annotation": line, **chosen},
                         indent=1, sort_keys=True))
    else:
        print(line)
    return EXIT_OK if chosen["source"] != "none" else EXIT_NOTHING


if __name__ == "__main__":
    sys.exit(main())
