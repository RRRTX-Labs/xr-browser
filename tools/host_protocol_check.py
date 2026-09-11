#!/usr/bin/env python3
"""tools/host_protocol_check.py — no host may dispatch methods nobody documented.

P11-T0-a. Root cause: the P10 registry row cited
`xr-core/update/host_protocol.md` — a file that did not exist — and
`tools/parity_completeness.py` happily printed "4 pair(s), 0 failure(s)"
because its pair list was a hand-written manifest: a fifth host that shipped
no protocol doc was not a violation, it was simply uncounted. That is the
P9-T0-a blind spot (correct verdicts, untested path) relocated one level up,
so the discovery itself is now derived from the tree.

Law (per host directory `xr-core/<name>/host/` whose `*.cc` dispatch on a
`method` string — the source is the truth):

  (i)   `<name>/host_protocol.md` MUST exist;
  (ii)  every method literal in the source (`method == "<lit>"`) MUST appear
        in the doc's `## Methods` table AND vice versa — a table entry with
        no code is as much a failure as code with no table entry;
  (iii) the doc MUST declare the response law: ONE canonical JSON line,
        sorted keys, non-ASCII `\\uXXXX`, exit `0`/`1`/`2`, and the
        unknown-method refusal (`kUnknownMethod`).

The same discovery feeds tools/parity_completeness.py (derived pair list), so
"host exists but nobody counted it" is structurally impossible. Negative
fixture: tools/negatives/p11_t0.sh plants a synthetic fifth host (methods,
no doc) and asserts BOTH gates redden.

Usage:  python3 tools/host_protocol_check.py [--xr-core PATH] [--json]
Exit: 0 pass · 1 fail · 2 usage. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# `method == "literal"` — the house dispatch shape (settings/themes/update/
# commands protocol.cc). String-literal comparisons only; subcommand hosts
# (policy_host) do not match and are accounted for in the parity manifest.
METHOD_LITERAL_RE = re.compile(r'\bmethod\s*==\s*"([A-Za-z0-9_.:-]+)"')

# Response-law markers, checked on whitespace-normalized text.
EXIT_LAW_RE = re.compile(
    r"[Ee]xit\s+`?0`?[^.\n]{0,140}`?1`?[^.\n]{0,100}`?2`?")


def discover_method_hosts(xr_core: Path) -> dict[str, list[str]]:
    """host dir name -> sorted method literals, for every dispatching host.

    Scans every `xr-core/*/host/*.cc`. A directory qualifies when at least
    one source compares a `method` string. Discovery order is sorted; the
    result is deterministic across runs and machines.
    """
    hosts: dict[str, list[str]] = {}
    for host_dir in sorted(xr_core.glob("*/host")):
        if not host_dir.is_dir():
            continue
        literals: set[str] = set()
        for src in sorted(host_dir.glob("*.cc")):
            try:
                text = src.read_text(encoding="utf-8")
            except OSError:
                continue
            literals.update(METHOD_LITERAL_RE.findall(text))
        if literals:
            hosts[host_dir.parent.name] = sorted(literals)
    return hosts


def parse_methods_table(md: Path) -> list[str]:
    """Method names from the `## Methods` table (P8 table convention)."""
    text = md.read_text(encoding="utf-8")
    out: list[str] = []
    in_methods = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("## ") and s.lower().endswith("methods"):
            in_methods = True
            continue
        if in_methods and s.startswith("## "):
            break
        if not in_methods or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].strip("`").split("\\")[0].strip()
        if first in ("", "method", "---") or set(first) <= {"-", " "}:
            continue
        out.append(first)
    return out


def check_response_law(md: Path) -> list[str]:
    """(iii): the doc must declare the canonical response + exit + refusal law."""
    text = re.sub(r"\s+", " ", md.read_text(encoding="utf-8"))
    fails: list[str] = []
    for marker, why in (
            ("canonical", "single canonical JSON line law"),
            ("sorted keys", "sorted-key canonicalization law"),
            ("uXXXX", "non-ASCII \\uXXXX escaping law"),
            ("kUnknownMethod", "unknown-method refusal")):
        if marker not in text:
            fails.append(f"{md.name}: response law undeclared — missing "
                         f"{marker!r} ({why})")
    if not EXIT_LAW_RE.search(text):
        fails.append(f"{md.name}: response law undeclared — no 'exit `0` … "
                     "`1` … `2`' code line")
    return fails


def check_host(xr_core: Path, name: str, methods: list[str]) -> list[str]:
    md = xr_core / name / "host_protocol.md"
    if not md.is_file():
        return [f"{name}: host dispatches methods {methods} but "
                f"{name}/host_protocol.md does not exist — an undocumented "
                f"host is invisible to the parity gate (P11-T0-a law)"]
    fails = check_response_law(md)
    table = parse_methods_table(md)
    src, doc = set(methods), set(table)
    undocumented = sorted(src - doc)
    phantom = sorted(doc - src)
    if undocumented:
        fails.append(f"{name}: methods in source but NOT in the ## Methods "
                     f"table: {undocumented} (source is the truth)")
    if phantom:
        fails.append(f"{name}: table entries with NO dispatching code: "
                     f"{phantom} (a doc-only method is a lie)")
    if not table:
        fails.append(f"{name}: ## Methods table empty or missing")
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_core = Path(__file__).resolve().parent.parent.parent / "xr-core"
    ap.add_argument("--xr-core", default=str(default_core),
                    help="xr-core checkout (default: ../xr-core sibling)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    xr_core = Path(args.xr_core).resolve()
    if not xr_core.is_dir():
        print(f"error: no xr-core checkout at {xr_core}", file=sys.stderr)
        return EXIT_USAGE

    hosts = discover_method_hosts(xr_core)
    if not hosts:
        print("FAIL: discovered ZERO method-dispatching hosts — a discovery "
              "that finds nothing certifies nothing (zero-case law)",
              file=sys.stderr)
        return EXIT_FAIL

    failures: list[str] = []
    for name, methods in sorted(hosts.items()):
        failures.extend(check_host(xr_core, name, methods))

    if args.json:
        print(json.dumps({
            "hosts": {k: v for k, v in sorted(hosts.items())},
            "failures": failures,
            "status": "pass" if not failures else "fail"}, indent=2))
    else:
        for name, methods in sorted(hosts.items()):
            print(f"  discovered host: {name} ({len(methods)} method(s): "
                  f"{', '.join(methods)})")
        for f in failures:
            print(f"FAIL: {f}")
        if not failures:
            print(f"PASS: host_protocol_check ({len(hosts)} host(s), every "
                  f"method literal documented, response law declared)")
        else:
            print(f"FAIL: host_protocol_check ({len(failures)} finding(s))")
    return EXIT_PASS if not failures else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
