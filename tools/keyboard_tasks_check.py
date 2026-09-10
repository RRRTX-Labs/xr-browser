#!/usr/bin/env python3
"""tools/keyboard_tasks_check.py — the 12-tasks-as-data gate (P9-T7).

docs/qa/keyboard-tasks.yaml carries the plan's "keyboard-only completion of
the 12 core tasks" list (§11.6) as data with owners. This gate enforces:
exactly 12 tasks, each with a non-empty task/surface/owner, and unique ids —
so the list cannot silently shrink (empty-run law) and no task is unowned.
Execution of the tasks is farm work (HG-31); this gate protects the LIST.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE  # noqa: E402

TASKS_YAML = "docs/qa/keyboard-tasks.yaml"
REQUIRED_COUNT = 12


def check(repo: Path) -> tuple[list[str], int]:
    import yaml
    path = repo / TASKS_YAML
    if not path.exists():
        return [f"missing {TASKS_YAML}"], 0
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    tasks = doc.get("tasks") or []
    fails: list[str] = []
    if len(tasks) != REQUIRED_COUNT:
        fails.append(f"{TASKS_YAML}: {len(tasks)} tasks != the plan's "
                     f"{REQUIRED_COUNT} core tasks")
    seen: set[str] = set()
    for t in tasks:
        tid = t.get("id")
        if tid in seen:
            fails.append(f"{tid}: duplicate id")
        seen.add(tid)
        for field in ("id", "task", "surface", "owner"):
            if not t.get(field):
                fails.append(f"{tid or '?'}: missing/empty {field!r}")
    return fails, len(tasks)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="keyboard_tasks_check",
                                description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    fails, n = check(repo)
    if args.json:
        print(json.dumps({"tool": "keyboard_tasks_check", "tasks": n,
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"keyboard_tasks_check: {n} task(s), {len(fails)} violation(s) "
              f"({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
