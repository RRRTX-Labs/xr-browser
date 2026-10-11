#!/usr/bin/env python3
"""tools/assumption_drift_check.py — prove an assumptions row reddens on drift (P15-CLOSE C4).

The §12.4 runner (build/upstream/assumptions.py) reads upstream LIVE at a rev. A
negative cannot depend on the network, so this probe runs the SAME row logic
(`run_rows`) offline against a scratch copy of the row's file:

  * the scratch file is either `--upstream-file PATH` (a real copy, e.g. from
    work/upstream-cache after a live run) or, by default, the row's own
    `contains` anchors (which the live run proves present at the pin);
  * `--rename OLD=NEW` plants drift in the scratch copy (an upstream rename);
  * with no rename the row must PASS (the positive control), and with a rename
    it must FAIL with the runner's own "P0 to <owner> BEFORE promotion" line.

Usage: assumption_drift_check.py --row A4 [--rename OLD=NEW] [--upstream-file P]
Exit: 0 row PASS · 1 row FAIL (drift detected) · 2 usage. Stdlib + PyYAML.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build" / "upstream"))
sys.path.insert(0, str(REPO / "build"))

from assumptions import load_registry, run_rows  # noqa: E402
from fetch import FixtureFetchSource  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--row", required=True)
    ap.add_argument("--rename", default=None, help="OLD=NEW, planted in the scratch copy")
    ap.add_argument("--upstream-file", default=None)
    ap.add_argument("--registry", default=None)
    a = ap.parse_args()
    reg = load_registry(Path(a.registry)) if a.registry else load_registry()
    rows = [r for r in reg["rows"] if r.get("id") == a.row]
    if len(rows) != 1 or rows[0].get("check_type") != "file-contract":
        print(f"usage error: {a.row} is not exactly one file-contract row", file=sys.stderr)
        return 2
    row = rows[0]
    rev = row["since_rev"]
    if a.upstream_file:
        text = Path(a.upstream_file).read_text(encoding="utf-8")
    else:
        text = "\n".join(row["contains"]) + "\n"
    if a.rename:
        old, sep, new = a.rename.partition("=")
        if not sep or not old or old not in text:
            print(f"usage error: --rename {a.rename!r}: OLD not in the scratch copy",
                  file=sys.stderr)
            return 2
        text = text.replace(old, new)
    source = FixtureFetchSource(files={(rev, row["file"]): text})
    results, failures = run_rows(source, rev, {"rows": [row]})
    r = results[0]
    print(f"{r['status']} {row['id']} ({row['assumption']}) scratch copy of {row['file']}"
          f"{' with planted rename ' + a.rename if a.rename else ''}")
    for f in failures:
        print(f"FAIL: {f}")
    return 0 if r["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
