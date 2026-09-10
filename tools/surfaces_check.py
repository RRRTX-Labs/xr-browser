#!/usr/bin/env python3
"""tools/surfaces_check.py — the §11 surface-completeness gate (P9-T12).

Plan P9's objective is that every §11 verification surface EXISTS as
automated infrastructure before the feature phases need it, and a "§11
surface without a home" is a stop-condition. This gate enforces both, over
docs/qa/surfaces.yaml:

  1. COMPLETE — every §11 surface id (11.1..11.15) is present.
  2. HOMED — every surface has a home: a tool path that EXISTS, a farm row,
     a manual surface whose rows all have owner+cadence, or a not_yet row
     with an owner phase. No home => red.
  3. HONEST — a listed tool path must resolve; a farm/not_yet home must
     name its row/owner.
  4. GREEN-DEFINED — every surface states its machine-side `green` clause
     ("green" is computed by the runners, never hand-asserted).
  5. EMPTY-RUN — zero surfaces is red.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE  # noqa: E402

SURFACES_YAML = "docs/qa/surfaces.yaml"
REQUIRED = [f"11.{i}" for i in range(1, 16)]


def check(repo: Path, *, surfaces_path: Path | None = None) -> list[str]:
    import yaml
    p = surfaces_path or (repo / SURFACES_YAML)
    if not p.exists():
        return [f"missing {SURFACES_YAML}"]
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        return [f"{p}: unsupported schema_version"]
    surfaces = list(doc.get("surfaces") or [])
    fails: list[str] = []
    if not surfaces:
        return ["zero surfaces (empty-run law)"]

    ids = [s.get("id") for s in surfaces]
    for req in REQUIRED:
        if req not in ids:
            fails.append(f"missing surface {req}")

    for s in surfaces:
        sid = s.get("id")
        if not s.get("green"):
            fails.append(f"{sid}: no machine-side green clause")
        home = s.get("home")
        if home == "tool":
            paths = s.get("tools") or []
            if not paths:
                fails.append(f"{sid}: tool home with no tools")
            for t in paths:
                tp = Path(t)
                if not tp.is_absolute():
                    tp = repo / tp
                if not tp.exists():
                    fails.append(f"{sid}: tool path missing: {t}")
        elif home == "farm":
            if not s.get("farm"):
                fails.append(f"{sid}: farm home with no farm row")
        elif home == "not_yet":
            if not s.get("owner_phase"):
                fails.append(f"{sid}: not_yet with no owner_phase")
        elif home == "manual":
            rows = s.get("rows") or []
            if not rows:
                fails.append(f"{sid}: manual home with no rows")
            for r in rows:
                if not r.get("owner") or not r.get("cadence"):
                    fails.append(f"{sid}: manual row missing owner/cadence: "
                                 f"{r.get('item')}")
        else:
            fails.append(f"{sid}: no home (stop-condition)")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="surfaces_check",
                                description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--surfaces", default="", help="override path (fixtures)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    sp = Path(args.surfaces) if args.surfaces else None
    fails = check(repo, surfaces_path=sp)
    if args.json:
        print(json.dumps({"tool": "surfaces_check", "count": len(fails),
                          "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"surfaces_check: {len(REQUIRED)} surface(s), "
              f"{len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
