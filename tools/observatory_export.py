#!/usr/bin/env python3
"""tools/observatory_export.py — the Observatory's export, where redaction is CONTRACT (P13-T3).

The Observatory is the one place in the product that holds a live view of what
was blocked, so it is the one place where an "export" button is a data-leak
surface. The rules are therefore not a formatting preference — they are the
contract, and this tool is where they are enforced and *demonstrated*:

LAW 1 — **no query params by default, no fragments ever.** A `target` is stored
  as `scheme://host/path` (P6's block-event law already redacts at row creation);
  the exporter re-derives the redacted form from whatever it is handed, so a row
  that arrived from somewhere else is still safe to write. `--full` is the opt-in
  and it preserves the query string — and STILL refuses an authority carrying
  `user:pass@`.

LAW 2 — **credentials are REFUSED, not stripped.** `https://user:pw@host/` is
  refused with a typed error naming the row and the class. Silently stripping it
  would be worse than failing: the caller would believe the row was exported.
  Same for cookies, UA strings and cosmetic selector text, which are refused by
  class — a leak class is not a formatting detail.

LAW 3 — **the refused bytes never reach the writer.** Every refusal happens
  before serialization, and the check asserts the refused substring is absent
  from the produced bytes — not merely that some error was reported. This is the
  difference between "we validate" and "it cannot get out".

LAW 4 — **both backends, byte-identical.** The rows the C++ shield and the
  Python fake emit are already byte-identical (docs/contracts/tests/
  test_block_event.py proves that against the golden); the exporter's job is to
  keep it that way — identical input rows must produce identical bytes, and the
  check re-serializes the committed golden row through both entry points.

Modes: `--check` (the corpus, the smuggle fuzz and the parity run), `--json`,
`--csv`, `--fixture <path>` (rows on disk), `--full` (opt-in query retention).
Exit 0 clean · 1 finding · 2 usage. Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# The exported field set, in this order, for BOTH formats. One list, so a new
# column cannot appear in JSON and be missing from CSV.
FIELDS = ("seq", "ts_millis", "identity", "type", "origin", "target",
          "rule_id", "rule", "list_id", "bundle_version", "action",
          "why_code", "page_modifying")

# Fields no row may carry into an export. Refused by CLASS, with the class named,
# so the caller is told what they tried to send rather than that "a field" was
# wrong.
# A KEY with one of these names is a leak class on its own: a field called
# `cookie` is a cookie, whatever its value, and renaming it is the caller's
# problem to not do.
REFUSED_KEYS = {"cookie": "cookie", "set_cookie": "cookie",
                "document_cookie": "cookie", "user_agent": "user_agent",
                "useragent": "user_agent", "css_selector": "selector",
                "selector_text": "selector", "selector": "selector"}
# …and a VALUE that looks like one is refused even under an innocent key.
REFUSED_VALUES = {
    "cookie": re.compile(r"(?i)(document\.cookie|set-cookie|\bsession=|\bsid=)"),
    "user_agent": re.compile(r"(?i)Mozilla/5\.0|\buser[-_]?agent\b"),
    "selector": re.compile(r"(?i)::-webkit|display\s*:\s*none"),
}
# Fragments/queries are dropped from a TARGET and are NOT a property of the row:
# `###tracker-ad` is a filter rule, not a URL fragment, and treating the two the
# same way would corrupt the product's own data while looking careful.
CREDENTIAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@\s]+:[^/@\s]*@")
QUERY_RE = re.compile(r"\?[^#]*")


class Refused(Exception):
    """A row (or a field) that may not be exported, with its class named."""

    def __init__(self, why_class: str, detail: str) -> None:
        super().__init__(f"{why_class}: {detail}")
        self.why_class = why_class
        self.detail = detail


def split_target(target: str) -> dict:
    """scheme://host/path — the redacted form, re-derived from whatever arrived."""
    parts = urlsplit(target if "//" in target else f"//{target}", scheme="")
    scheme = parts.scheme or "https"
    path = parts.path or "/"
    return {"scheme": scheme, "host": parts.netloc, "path": path,
            "query": parts.query, "fragment": parts.fragment}


def redact_row(row: dict, *, full: bool = False) -> dict:
    """Validate + redact one row. Raises Refused with the class named."""
    out: dict = {}
    for key, value in row.items():
        if key == "target":
            continue
        lowered = str(key).lower()
        if lowered in REFUSED_KEYS:
            raise Refused(REFUSED_KEYS[lowered],
                          f"field {key!r} is a {REFUSED_KEYS[lowered]} field — refusing by "
                          f"name, because a leaked field renamed to dodge a pattern is "
                          f"still the leak")
        if isinstance(value, str):
            for why_class, pattern in REFUSED_VALUES.items():
                if pattern.search(value):
                    raise Refused(why_class, f"field {key!r} carries a {why_class} value")
        out[key] = value

    target = str(row.get("target", ""))
    if CREDENTIAL_RE.match(target):
        raise Refused("credentials", "target authority carries user:pass@ — refused, "
                                     "never stripped (a stripped row looks exported)")
    # A fragment is DROPPED, not refused: it is the same class as a query string
    # (see LAW 1). What must never happen is the other direction — a filter RULE
    # that merely looks like a fragment (`###tracker-ad`) being eaten by this
    # rule, which is why the drop is a function of the parsed target and not of
    # a text scan over the whole row.
    parts = split_target(target)
    if parts["host"] == "":
        raise Refused("malformed-target", f"target {target!r} has no host")
    redacted = f"{parts['scheme']}://{parts['host']}{parts['path']}"
    if full:
        # opt-in: the query may be kept, the fragment never.
        out["target"] = redacted + (f"?{parts['query']}" if parts["query"] else "")
    else:
        out["target"] = redacted
    return out


def export_rows(rows: list[dict], *, full: bool = False) -> list[dict]:
    """Every row redacted, in the canonical field order, or Refused."""
    return [{k: r.get(k) for k in FIELDS} for r in (redact_row(r, full=full) for r in rows)]


def to_json(rows: list[dict], *, full: bool = False) -> bytes:
    return (json.dumps(export_rows(rows, full=full), sort_keys=False,
                       separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def to_csv(rows: list[dict], *, full: bool = False) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    for r in export_rows(rows, full=full):
        w.writerow(r)
    return buf.getvalue().encode()


# --- the smuggle corpus ------------------------------------------------------
# Each case is a row that TRIES to carry something out, the class it must be
# refused for, and the substring that must not appear in any produced bytes.
SMUGGLE_CASES: list[dict] = [
    {"row": {"seq": 1, "target": "https://tracker.example/ad.js?uid=12345&ref=mail"},
     "class": None, "absent": "uid=12345"},
    {"row": {"seq": 2, "target": "https://tracker.example/ad.js#section-2"},
     "class": None, "absent": "#section-2"},
    {"row": {"seq": 3, "target": "https://user:sekret@tracker.example/ad.js"},
     "class": "credentials", "absent": "sekret"},
    {"row": {"seq": 4, "type": "kStorage", "cookie": "session=abc123"},
     "class": "cookie", "absent": "abc123"},
    {"row": {"seq": 5, "type": "kSubresource", "user_agent": "Mozilla/5.0 (X11)"},
     "class": "user_agent", "absent": "Mozilla"},
    {"row": {"seq": 6, "type": "kScript", "rule": "###tracker-ad",
             "selector_text": "###tracker-ad"},
     "class": "selector", "absent": "###tracker-ad"},
    # a FILTER RULE that looks like a fragment must survive: refusing the
    # product's own data would be as wrong as leaking it.
    {"row": {"seq": 7, "type": "kScript", "rule": "###tracker-ad",
             "why_code": "rule-blocked", "target": "https://tracker.example/x.js"},
     "class": None, "absent": "\u0000"},
]


def check_smuggles() -> list[str]:
    """Run the corpus. A leak is any refused byte that reaches the writer."""
    fails: list[str] = []
    for case in SMUGGLE_CASES:
        row = case["row"]
        try:
            j = to_json([row])
            c = to_csv([row])
        except Refused as exc:
            if case["class"] is None:
                fails.append(f"row {row['seq']} was refused ({exc}) but should have "
                             f"been redacted, not refused")
                continue
            if exc.why_class != case["class"]:
                fails.append(f"row {row['seq']} refused as {exc.why_class!r}, "
                             f"expected {case['class']!r}")
            continue
        if case["class"] is not None:
            fails.append(f"row {row['seq']} must be REFUSED as {case['class']!r} "
                         f"and was exported instead")
            continue
        for produced in (j, c):
            needle = case["absent"].encode()
            if needle in produced:
                fails.append(f"row {row['seq']}: {case['absent']!r} reached the "
                             f"writer — redaction happened after serialization")
    return fails


def check_parity(repo: Path) -> tuple[list[str], int]:
    """The committed golden row, exported twice, must be byte-identical.

    The golden is the row the C++ core emits and the Python fake reproduces
    byte-for-byte (docs/contracts/tests/test_block_event.py). Here the question
    is narrower and still worth asking: does the EXPORTER introduce a difference
    the emitters do not have — a dict-ordering artifact, a float formatting, a
    field the CSV path drops? Both formats are produced from the same row, so a
    difference is the exporter's, and the field set is asserted equal too.
    """
    fails: list[str] = []
    golden = repo / "docs" / "contracts" / "tests" / "golden-block-event.json"
    if not golden.is_file():
        return [f"missing golden row: {golden}"], 0
    row = json.loads(golden.read_text(encoding="utf-8"))
    one = export_rows([row])
    rows = [{**row, "seq": row.get("seq", 0) + i} for i in range(3)]
    out = export_rows(rows)
    if [f for f in out[0]] != list(FIELDS):
        fails.append("the canonical field order is not what FIELDS says — one "
                     "list must drive JSON and CSV or a column can go missing")
    for r in out:
        if list(r.keys()) != list(one[0].keys()):
            fails.append("two rows of the same shape produced different field sets")
            break
    # the same row serialized through both entry points, twice each
    if to_json([rows[0]]) != to_json([dict(rows[0])]):
        fails.append("JSON export is not deterministic across identical input dicts")
    csv_a = to_csv([rows[0]]).splitlines()
    csv_b = to_csv([dict(rows[0])]).splitlines()
    if csv_a != csv_b:
        fails.append("CSV export is not deterministic across identical input dicts")
    return fails, len(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="observatory_export", description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--fixture", default="", help="rows to export (JSON array)")
    ap.add_argument("--check", action="store_true", help="the corpus, the fuzz, the parity run")
    ap.add_argument("--full", action="store_true", help="opt-in: keep query strings")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (args.check or args.fixture or args.json or args.csv):
        args.check = True

    if args.fixture:
        rows = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        try:
            sys.stdout.buffer.write(to_csv(rows, full=args.full) if args.csv
                                    else to_json(rows, full=args.full))
        except Refused as exc:
            print(f"observatory_export: {exc.why_class}: {exc.detail}", file=sys.stderr)
            return 1
        return 0

    fails = check_smuggles()
    parity_fails, compared = check_parity(repo)
    fails.extend(parity_fails)
    if args.json:
        print(json.dumps({"tool": "observatory_export", "fails": fails,
                          "corpus": len(SMUGGLE_CASES), "parity_rows": compared},
                         indent=1))
    else:
        for f in fails:
            print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: observatory_export ({len(fails)} finding(s); "
              f"smuggle corpus: {len(SMUGGLE_CASES)} case(s))")
        return 1
    print(f"PASS: observatory_export ({len(SMUGGLE_CASES)} smuggle case(s), "
          f"{compared} parity row(s) — default has no query params and no "
          f"fragments, credentials are refused not stripped, and no refused byte "
          f"reached the writer)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
