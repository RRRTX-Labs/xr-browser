#!/usr/bin/env python3
"""tools/breakage_report.py — compose a breakage report that cannot leak (P13-T4).

A breakage report leaves the machine, so it is a DATA-LEAK AUDIT ITEM, not a
feature with a text box. This tool is the pre-send half: it builds the payload
from a blocked event, refuses anything that would carry page content or
identifying material, and writes to a LOCAL FIXTURE QUEUE labelled `fixture` in
its path AND in stdout.

The context is exactly four things — origin (scheme + registrable domain, no
path, no query, no fragment), a UA-LESS browser version tag, the matched rule id
and the list's bundle version. That is the schema's `context`, and the schema has
`additionalProperties: false` everywhere, so `{"html": "<div>…"}` is refused by
structure before any refusal rule has to notice it.

Refusal is PRE-SEND and by CLASS: a URL carrying a query, a cookie, a user-agent
string, selector text and credentials are each named in the error, and the tool
never writes a partially-redacted report — a report that went out "mostly
redacted" is a report that went out.

Transport: NONE here, deliberately. The plan says the report reuses P10's update
channel; that channel is an envelope-fetch (GET + minisign verification) and it
cannot carry a POST payload today. Adding a second egress path is a FAILURE
CONDITION, so this tool has no network code at all: it writes to
`--queue <dir>`, the fixture tree, whose path must contain `fixture` or the run
refuses. The live half is HUMAN-GATED and its drill is
docs/panel/breakage-report.md.

SLA labels are DATA (`sla: {label, hours, class}`), never a rendered sentence, so
no tool in this repository can assert a median it did not measure. The plan's
"48 h median proven on 20 seeded reports" is a production act: it is recorded
HUMAN-GATED, and there is no simulated median anywhere in P13.

Modes: `--from-event <json>` (a block-event row), `--note <text>`, `--as-of
<ISO>`, `--queue <dir>`, `--validate-only`, `--check` (the vector suite),
`--json`. Exit 0 ok · 1 refusal/finding · 2 usage. Stdlib only, offline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CONTRACT = "breakage-report"
VECTORS = "docs/contracts/vectors/breakage-report-v1.json"

# The refusal classes, checked in this order, each with the class NAME the error
# reports. Order matters only for which name a doubly-bad note gets.
SMUGGLE = (
    ("url", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s]*\?[^\s]*")),
    ("cookie", re.compile(r"(?i)\b(document\.cookie|set-cookie|session=|sid=|token=)")),
    ("user_agent", re.compile(r"(?i)Mozilla/5\.0|\buser[-_]?agent\b")),
    # A selector is a class/id followed by a combinator, a pseudo-element, or a
    # declaration block. Narrow on purpose: plain prose ends sentences with a
    # period and a space, and refusing that would make the feature unusable while
    # looking careful.
    ("selector", re.compile(r"(?i)([#.][A-Za-z][\w-]*\s*[>+~]|::[a-z-]+|\{[^{}]*:[^{}]*\})")),
    ("html", re.compile(r"(?i)</?[a-z][^>]*>")),
    ("credentials", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]*@")),
)
ORIGIN_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")


class Refused(Exception):
    def __init__(self, why_class: str, detail: str) -> None:
        super().__init__(f"{why_class}: {detail}")
        self.why_class = why_class
        self.detail = detail


def _scan_text(text: str) -> None:
    """Refuse any smuggle class in free text, naming the class."""
    for why_class, pattern in SMUGGLE:
        m = pattern.search(text)
        if m:
            # The match is NOT echoed. A refusal message that quotes the thing it
            # refused turns the error channel into the leak: a credential in a
            # stderr line ends up in a bug report, a log file, a screenshot. The
            # class and the byte count are enough to act on.
            raise Refused(why_class,
                          f"free text carries a {why_class} value "
                          f"({len(m.group(0))} byte(s), withheld — an error message "
                          f"must not become the leak) — the report path carries "
                          f"origin, version tag, rule id and list version, and "
                          f"nothing else (docs/contracts/breakage-report-v1.md)")


def compose(event: dict, note: str, as_of: str, *,
            version_tag: str = "xr-1.2.0.0") -> dict:
    """Build the payload from a block event. Raises Refused, never redacts."""
    _scan_text(note)
    origin = event.get("origin") or {}
    domain = str(origin.get("registrable_domain", ""))
    if not ORIGIN_RE.match(domain) or any(c in domain for c in "/?#@"):
        raise Refused("origin", f"origin {domain!r} is not a bare registrable domain — "
                                f"a path, query, fragment or credential has no business "
                                f"in a report context")
    scheme = str(origin.get("scheme", "https"))
    if scheme not in ("http", "https"):
        raise Refused("origin", f"scheme {scheme!r} is not http/https")
    rule_id = str(event.get("rule_id", ""))
    list_id = str(event.get("list_id", ""))
    return {
        "report": "breakage_report",
        "contract_version": 1,
        "created_at": as_of,          # caller-supplied: this tool has no clock
        "user_note": note,
        "queue": "fixture",           # const in the schema: there is no live mode here
        "sla": {
            "label": "corpus-linked-48h" if rule_id else "unclassified-48h",
            "hours": 48,
            "class": "corpus-linked" if rule_id else "unclassified",
        },
        "context": {
            "origin": {"scheme": scheme, "registrable_domain": domain},
            "browser_version_tag": version_tag,
            "rule_id": rule_id,
            "list_id": list_id,
            "bundle_version": int(event.get("bundle_version", 0)),
            "action": str(event.get("action", "kBlocked")),
        },
    }


def validate(repo: Path, payload: dict) -> list[str]:
    """Schema validation via tools/xr_schema.py (the repo's one validator)."""
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        tmp = fh.name
    # the CONTRACT NAME, not the path: tools/xr_schema.py owns the registry of
    # contract -> schema, so a new contract is registered there or it does not
    # validate anywhere.
    r = subprocess.run([sys.executable, str(repo / "tools" / "xr_schema.py"),
                        "--repo", str(repo), "validate", "breakage-report", tmp],
                       capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        return [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()] or ["schema refusal"]
    return []


def check_vectors(repo: Path) -> list[str]:
    """Every accepted vector validates; every refused one is refused WITH its class."""
    fails: list[str] = []
    vectors = json.loads((repo / VECTORS).read_text(encoding="utf-8"))
    for case in vectors["accept"]:
        out = validate(repo, case["payload"])
        if out:
            fails.append(f"vector {case['case']}: must validate, got {out[:1]}")
    for case in vectors["refuse"]:
        payload = case["payload"]
        refusal: str | None = None
        try:
            # smuggle classes are caught in compose(); schema classes here.
            context = payload.get("context") or {}
            origin = (context.get("origin") or {})
            if case["expect_refusal"] == "origin" or case["expect_refusal"] in dict(SMUGGLE):
                compose({**context, "rule_id": context.get("rule_id", ""),
                         "list_id": context.get("list_id", ""),
                         "bundle_version": context.get("bundle_version", 0),
                         "action": context.get("action", "kBlocked"),
                         "origin": origin},
                        str(payload.get("user_note", "")), str(payload.get("created_at", "")))
            out = validate(repo, payload)
            if out:
                refusal = "schema"
        except Refused as exc:
            refusal = exc.why_class
        if refusal is None:
            fails.append(f"vector {case['case']}: must be REFUSED as "
                         f"{case['expect_refusal']!r} and was accepted")
        elif refusal != case["expect_refusal"]:
            fails.append(f"vector {case['case']}: refused as {refusal!r}, expected "
                         f"{case['expect_refusal']!r}")
    return fails


def queue_dir(arg: str | None) -> Path:
    """The fixture queue. A path without `fixture` in it is REFUSED, by design."""
    if not arg:
        raise Refused("queue", "no --queue given: this tool writes to a local fixture "
                               "tree and has no live transport (see "
                               "docs/panel/breakage-report.md)")
    path = Path(arg)
    if "fixture" not in str(path):
        raise Refused("queue", f"queue path {path} does not contain 'fixture' — a local "
                               f"queue that does not say it is local is how a fixture "
                               "ends up looking like production")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="breakage_report", description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--from-event", default="", help="a block-event row (JSON file or -)")
    ap.add_argument("--note", default="", help="user-supplied free text")
    ap.add_argument("--as-of", dest="as_of", default="", help="ISO timestamp (no clock here)")
    ap.add_argument("--queue", default="", help="local fixture queue directory")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--check", action="store_true", help="run the vector suite")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()

    if args.check:
        fails = check_vectors(repo)
        for f in fails:
            print(f"FAIL: {f}")
        if fails:
            print(f"FAIL: breakage_report ({len(fails)} vector finding(s))")
            return 1
        vectors = json.loads((repo / VECTORS).read_text(encoding="utf-8"))
        print(f"PASS: breakage_report vectors ({len(vectors['accept'])} accepted, "
              f"{len(vectors['refuse'])} refused pre-send with the class named) — "
              f"queue mode: fixture only; live filing is HUMAN-GATED "
              f"(docs/panel/breakage-report.md)")
        return 0

    if not args.from_event:
        print("breakage_report: usage: --from-event <row.json> [--note TEXT] --as-of ISO "
              "--queue <dir-containing-fixture>", file=sys.stderr)
        return 2
    event = json.loads(Path(args.from_event).read_text(encoding="utf-8")
                       if args.from_event != "-" else sys.stdin.read())
    if not args.as_of:
        print("breakage_report: --as-of is required (this tool has no clock — a "
              "timestamp it invented would be a claim about when something happened)",
              file=sys.stderr)
        return 2
    try:
        payload = compose(event, args.note, args.as_of)
    except Refused as exc:
        print(f"breakage_report: REFUSED pre-send — {exc.why_class}: {exc.detail}",
              file=sys.stderr)
        return 1
    if args.validate_only:
        fails = validate(repo, payload)
        for f in fails:
            print(f"FAIL: {f}")
        print("PASS: breakage_report payload validates (fixture queue)" if not fails
              else "FAIL: breakage_report payload")
        return 1 if fails else 0
    try:
        q = queue_dir(args.queue)
    except Refused as exc:
        print(f"breakage_report: {exc.why_class}: {exc.detail}", file=sys.stderr)
        return 2
    q.mkdir(parents=True, exist_ok=True)
    out = q / f"report-{payload['created_at'].replace(':', '').replace('-', '')}.json"
    out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"tool": "breakage_report", "queue_mode": "fixture",
                          "path": str(out), "sla": payload["sla"]}, indent=1))
    else:
        print(f"breakage_report: wrote fixture report to {out} "
              f"(queue_mode: fixture — NOT a live queue; filing is HUMAN-GATED)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
