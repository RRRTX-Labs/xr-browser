#!/usr/bin/env python3
"""tools/npm_allowlist_check.py — the audited npm allowlist gate (P9-T7).

Replaces the stale "exactly three packages" prose in
ui/toolchain/package.json with an audited control: every package in
package-lock.json must match an entry in ui/toolchain/npm-allowlist.json
(exact name or glob). A package in the lock tree outside the allowlist is a
failure — converting a magic number into the control future phases
(P13/P21/P29/P30) need anyway.

Laws:
  * empty lock or empty allowlist is a FAILURE (empty-run law);
  * a lockfile package that matches nothing is a FAILURE (with the offender);
  * an allowlist entry that matches nothing in the lock is a FAILURE (a
    stale allowance is drift).

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError  # noqa: E402

LOCKFILE = "../xr-core/ui/toolchain/package-lock.json"
ALLOWLIST = "../xr-core/ui/toolchain/npm-allowlist.json"


def matches(name: str, entry: dict) -> bool:
    pat = entry["name"]
    if entry.get("match") == "glob":
        return fnmatch.fnmatch(name, pat)
    return name == pat


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="npm_allowlist_check",
                                description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--lockfile", default=LOCKFILE)
    p.add_argument("--allowlist", default=ALLOWLIST)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()

    lock = Path(args.lockfile)
    if not lock.is_absolute():
        lock = repo / lock
    allow = Path(args.allowlist)
    if not allow.is_absolute():
        allow = repo / allow

    doc = json.loads(lock.read_text(encoding="utf-8")) if lock.exists() else {}
    packages = [k[len("node_modules/"):] for k in doc.get("packages", {})
                if k.startswith("node_modules/") and k != "node_modules/"]
    if not packages:
        print("FAIL: lockfile: zero packages (empty-run law)")
        return EXIT_FAIL
    allowdoc = json.loads(allow.read_text(encoding="utf-8"))
    entries = allowdoc.get("packages") or []
    fails: list[str] = []
    for pkg in packages:
        if not any(matches(pkg, e) for e in entries):
            fails.append(f"lockfile package {pkg!r} is not in the allowlist")
    matched = {e["name"] for e in entries
               for pkg in packages if matches(pkg, e)}
    for e in entries:
        if e["name"] not in matched:
            fails.append(f"allowlist entry {e['name']!r} matches nothing "
                         f"(stale allowance)")

    if args.json:
        print(json.dumps({"tool": "npm_allowlist_check",
                          "packages": len(packages),
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"npm_allowlist_check: {len(packages)} package(s) checked, "
              f"{len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
