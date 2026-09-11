#!/usr/bin/env python3
"""tools/parity_completeness.py — the parity-completeness gate (P9-T0-a, derived P11-T0-a).

Root cause T0-a (P9) closed: the byte-parity corpus fed `import` two inputs
('not-json' and '{}'), so the whole hostile-palette path was unparity-tested
and the two backends drifted on refusal text. \"We forgot to test this method\"
is a scope-drift class that must be structurally impossible, so this gate
auto-discovers the method set from each host_protocol.md `## Methods` table
and fails when a method has zero parity-corpus cases.

Root cause T0-a (P11) closed: the PAIR LIST ITSELF was a hand-written
manifest — `xr-core/update/host` shipped a fifth stdio host with no
host_protocol.md and this gate still printed "4 pair(s), 0 failure(s)",
because a host nobody listed is not a violation, it is simply uncounted.
The pair list is now DERIVED: tools/host_protocol_check.discover_method_hosts
scans every `xr-core/*/host/*.cc` for `method == "<literal>"` dispatch, and

  * every discovered host MUST have a manifest pair with protocol + corpus
    (an unaccounted host FAILS — undiscoverable-by-omission is dead);
  * every manifest pair naming a protocol MUST correspond to a discovered
    host (a phantom pair FAILS — the manifest cannot lie the other way);
  * a discovered method host may NOT hide behind a covered_by exception —
    exceptions are for hosts with no {method,args} table at all (policy's
    subcommand host), recorded as data rows in tools/parity/manifest.json,
    never as code comments;
  * discovered ZERO hosts FAILS (a discovery that finds nothing certifies
    nothing — the zero-case law applied to the gate's own input).

The zero-case law applies per pair as before: a pair with no discoverable
methods, or a corpus with no cases, are FAILURES.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_protocol_check import discover_method_hosts  # noqa: E402
from parity import _corpus as corpus  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
MANIFEST = Path(__file__).resolve().parent / "parity" / "manifest.json"


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: cannot read manifest: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FAIL)
    pairs = doc.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        print("error: parity manifest has no pairs (zero-case law)",
              file=sys.stderr)
        raise SystemExit(EXIT_FAIL)
    return doc


def derive_failures(xr_core: Path, pairs: list[dict[str, Any]]) -> list[str]:
    """P11-T0-a: cross-check the manifest against tree-derived discovery."""
    hosts = discover_method_hosts(xr_core)
    if not hosts:
        return [f"discovered ZERO method-dispatching hosts under {xr_core} — "
                "a derived pair list that finds nothing certifies nothing "
                "(zero-case law)"]
    by_id = {e.get("id", "<no id>"): e for e in pairs}
    fails: list[str] = []
    for name, methods in sorted(hosts.items()):
        entry = by_id.get(name)
        if entry is None:
            fails.append(f"{name}: DISCOVERED host dispatching {methods} has "
                         "no manifest pair — an unaccounted host is invisible "
                         "to parity (P11-T0-a derivation law)")
            continue
        if entry.get("protocol") is None:
            fails.append(f"{name}: discovered method host may not claim a "
                         "covered_by exception — a host with method literals "
                         "needs protocol + corpus rows")
            continue
        if not entry.get("corpus"):
            fails.append(f"{name}: manifest pair has a protocol but no "
                         "corpus path")
    for pid, entry in by_id.items():
        if entry.get("protocol") is not None and pid not in hosts:
            fails.append(f"{pid}: manifest names a protocol but no host "
                         f"dispatches methods in {pid}/host/*.cc — phantom "
                         "pair (the manifest cannot lie in either direction)")
        if entry.get("protocol") is None:
            if not entry.get("covered_by"):
                fails.append(f"{pid}: no protocol and no covered_by note — "
                             "unaccounted surface")
            elif not (xr_core / pid / "host").is_dir():
                fails.append(f"{pid}: covered_by exception names a host dir "
                             f"that does not exist ({pid}/host) — stale "
                             "exception row")
    return fails


def check_pair(repo: Path, entry: dict[str, Any]) -> list[str]:
    """Return failure strings for one manifest pair (empty == pass)."""
    fails: list[str] = []
    pid = entry.get("id", "<no id>")
    proto = entry.get("protocol")
    cpath = entry.get("corpus")
    if proto is None:
        # A pair with no protocol table must be accounted for (covered_by);
        # the derivation layer above checks the exception row itself.
        return fails
    md = (repo / proto).resolve()
    try:
        methods = corpus.protocol_methods(md)
    except corpus.CorpusError as exc:
        return [f"{pid}: {exc}"]
    if not methods:
        fails.append(f"{pid}: protocol {proto} has no discoverable Methods "
                     f"table (zero-case law)")
        return fails
    if not cpath:
        fails.append(f"{pid}: protocol present but no corpus path")
        return fails
    cfile = (repo / cpath).resolve()
    try:
        doc = corpus.load_corpus(cfile)
    except corpus.CorpusError as exc:
        return [f"{pid}: {exc}"]
    counts = corpus.methods_in_corpus(doc)
    missing = [m for m in methods if m not in counts]
    if missing:
        fails.append(f"{pid}: methods with ZERO parity cases: {missing} "
                     f"(protocol table: {methods})")
    orphans = [m for m in counts if m not in methods]
    if orphans:
        fails.append(f"{pid}: corpus cases for methods absent from the "
                     f"protocol table (orphan cases): {orphans}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="repository root (default: cwd)")
    ap.add_argument("--xr-core", default=None,
                    help="xr-core checkout (default: <repo>/../xr-core)")
    ap.add_argument("--manifest", default=str(MANIFEST),
                    help="manifest path (default: tools/parity/manifest.json)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    xr_core = Path(args.xr_core).resolve() if args.xr_core \
        else repo.parent / "xr-core"
    if not xr_core.is_dir():
        print(f"error: no xr-core checkout at {xr_core}", file=sys.stderr)
        return EXIT_USAGE
    doc = _load_manifest(Path(args.manifest))
    pairs = doc["pairs"]

    results: dict[str, list[str]] = {}
    derived = derive_failures(xr_core, pairs)
    if derived:
        results["<derived>"] = derived
    for entry in pairs:
        results[entry.get("id", "<no id>")] = check_pair(repo, entry)
    total = sum(len(v) for v in results.values())
    if args.json:
        print(json.dumps({"pairs": [e.get("id") for e in pairs],
                          "failures": results,
                          "status": "pass" if total == 0 else "fail"},
                         indent=2))
    else:
        for pid, fails in results.items():
            if fails:
                for f in fails:
                    print(f"FAIL: {pid}: {f}")
            elif pid != "<derived>":
                print(f"PASS: {pid}: methods covered by parity corpus")
        if "<derived>" not in results:
            print(f"PASS: derived pair list == manifest "
                  f"({len(pairs)} row(s) cross-checked against "
                  f"{xr_core.name}/*/host discovery)")
        print(f"{'PASS' if total == 0 else 'FAIL'}: parity_completeness "
              f"({len(pairs)} pair(s), {total} failure(s))")
    return EXIT_PASS if total == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
