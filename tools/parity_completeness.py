#!/usr/bin/env python3
"""tools/parity_completeness.py — the parity-completeness gate (P9-T0-a).

Root cause T0-a closed: the byte-parity corpus fed `import` two inputs
('not-json' and '{}'), so the whole hostile-palette path was unparity-tested
and the two backends drifted on refusal text. \"We forgot to test this method\"
is a scope-drift class that must be structurally impossible, so this gate
auto-discovers the method set from each host_protocol.md `## Methods` table
and fails when a method has zero parity-corpus cases.

The zero-case law applies to the gate itself: zero pairs, a pair with no
discoverable methods, or a corpus with no cases are all FAILURES — a
completeness gate that can pass on nothing certifies nothing.

Pairs live in tools/parity/manifest.json (the same manifest the differential
oracle and the parity test read). A pair whose protocol md has no Methods
table (the policy subcommand host) is accounted for in the manifest with a
`covered_by` note and is never silently skipped.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parity import _corpus as corpus  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
MANIFEST = Path(__file__).resolve().parent / "parity" / "manifest.json"


def _load_manifest() -> dict[str, Any]:
    try:
        doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: parity manifest invalid JSON: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FAIL)
    pairs = doc.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        print("error: parity manifest has no pairs (zero-case law)", file=sys.stderr)
        raise SystemExit(EXIT_FAIL)
    return doc


def check_pair(repo: Path, entry: dict[str, Any]) -> list[str]:
    """Return failure strings for one manifest pair (empty == pass)."""
    fails: list[str] = []
    pid = entry.get("id", "<no id>")
    proto = entry.get("protocol")
    cpath = entry.get("corpus")
    if proto is None:
        # A pair with no protocol table must be accounted for (covered_by).
        if not entry.get("covered_by"):
            fails.append(f"{pid}: no protocol and no covered_by note — "
                         "unaccounted surface")
        return fails
    md = (repo / proto).resolve()
    try:
        methods = corpus.protocol_methods(md)
    except corpus.CorpusError as exc:
        return [f"{pid}: {exc}"]
    if not methods:
        fails.append(f"{pid}: protocol {proto} has no discoverable Methods "
                     "table (zero-case law)")
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repo", default=".", help="repository root (default: cwd)")
    ap.add_argument("--manifest", default=str(MANIFEST),
                    help="manifest path (default: tools/parity/manifest.json)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    try:
        doc = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: cannot read manifest: {exc}", file=sys.stderr)
        return EXIT_FAIL
    pairs = doc.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        print("error: parity manifest has no pairs (zero-case law)", file=sys.stderr)
        return EXIT_FAIL

    results: dict[str, list[str]] = {}
    for entry in pairs:
        results[entry.get("id", "<no id>")] = check_pair(repo, entry)
    total = sum(len(v) for v in results.values())
    if args.json:
        print(json.dumps({"pairs": list(results), "failures": results,
                          "status": "pass" if total == 0 else "fail"}, indent=2))
    else:
        for pid, fails in results.items():
            if fails:
                for f in fails:
                    print(f"FAIL: {pid}: {f}")
            else:
                print(f"PASS: {pid}: methods covered by parity corpus")
        print(f"{'PASS' if total == 0 else 'FAIL'}: parity_completeness "
              f"({len(pairs)} pair(s), {total} failure(s))")
    return EXIT_PASS if total == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
