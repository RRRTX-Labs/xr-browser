#!/usr/bin/env python3
"""tools/keyboard_tasks_permissions_check.py — the prompt-focus task law (P15-CLOSE C6).

docs/qa/keyboard-tasks-permissions.yaml carries the permission-prompt keyboard
tasks as data (option (a) of the ADR-0051 addendum: a SEPARATE file, so the
plan §11.6 12-task law in tools/keyboard_tasks_check.py stays untouched). This
gate enforces:

  K1 exactly one task per capability of the overlay core — the set is DERIVED
     from xr-core/fakes/permissions.py CAPS (held byte-identical to the C++
     host by tools/permission_host_parity.py); no count literal, no extras;
  K2 unique ids; non-empty id / task / surface / owner;
  K3 `buttons` is a permutation of the four buttons (none missing, none twice);
  K4 `focus_first` is present and equals buttons[0] (focus lands on the first);
  K5 a sensitive capability puts ONE-TIME first (plan line 808);
  K6 every prompt carries the identity scope-copy key (plan line 809).

That each row equals the C++ core (ButtonOrder / IsSensitive / BuildPrompt) is
asserted by xr-core/permissions/tests/test_present.cc, which reads this file.

Stdlib + PyYAML. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

TASKS_YAML = "docs/qa/keyboard-tasks-permissions.yaml"
BUTTONS = {"once", "session", "7d", "deny"}
SCOPE_COPY_KEY = "perm.scope.only_in_identity"


def core_caps(xr_core: Path) -> tuple[str, ...]:
    path = xr_core / "fakes" / "permissions.py"
    spec = importlib.util.spec_from_file_location("xr_fake_permissions", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return tuple(mod.CAPS)


def check(tasks_path: Path, caps: tuple[str, ...]) -> tuple[list[str], int]:
    import yaml
    if not tasks_path.exists():
        return [f"missing {tasks_path}"], 0
    doc = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
    tasks = doc.get("tasks") or []
    fails: list[str] = []
    if not caps:
        fails.append("the core reports no capabilities (zero-case law)")
    seen_ids: set[str] = set()
    seen_caps: list[str] = []
    for t in tasks:
        tid = t.get("id") or "?"
        if tid in seen_ids:
            fails.append(f"{tid}: duplicate id")
        seen_ids.add(tid)
        for field in ("id", "task", "surface", "owner"):
            if not t.get(field):
                fails.append(f"{tid}: missing/empty {field!r}")
        cap = t.get("capability")
        seen_caps.append(cap)
        if cap not in caps:
            fails.append(f"{tid}: capability {cap!r} is not a core capability {list(caps)}")
        buttons = t.get("buttons")
        if not isinstance(buttons, list) or len(buttons) != len(BUTTONS) or \
                set(map(str, buttons)) != BUTTONS:
            fails.append(f"{tid}: buttons {buttons!r} is not a permutation of {sorted(BUTTONS)}")
            continue
        first = t.get("focus_first")
        if not first:
            fails.append(f"{tid}: missing focus_first (where keyboard focus lands)")
        elif str(first) != str(buttons[0]):
            fails.append(f"{tid}: focus_first {first!r} != the first button {buttons[0]!r}")
        if t.get("sensitive") is True and str(buttons[0]) != "once":
            fails.append(f"{tid}: sensitive capability {cap}: first button "
                         f"{buttons[0]!r} != 'once' (plan line 808)")
        if not isinstance(t.get("sensitive"), bool):
            fails.append(f"{tid}: 'sensitive' must be true or false")
        if t.get("scope_copy_key") != SCOPE_COPY_KEY:
            fails.append(f"{tid}: scope_copy_key must be {SCOPE_COPY_KEY!r} (plan line 809)")
    for cap in caps:
        n = seen_caps.count(cap)
        if n != 1:
            fails.append(f"capability {cap}: {n} task(s), the law is exactly one")
    return fails, len(tasks)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="keyboard_tasks_permissions_check",
                                description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=".")
    p.add_argument("--xr-core", default="../xr-core")
    p.add_argument("--tasks", default="", help="override path (fixtures/negatives)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    repo = Path(a.repo).resolve()
    try:
        caps = core_caps(Path(a.xr_core).resolve())
    except (OSError, AttributeError) as exc:
        print(f"usage error: cannot read the core capability set: {exc}", file=sys.stderr)
        return 2
    fails, n = check(Path(a.tasks) if a.tasks else repo / TASKS_YAML, caps)
    if a.json:
        print(json.dumps({"tool": "keyboard_tasks_permissions_check", "tasks": n,
                          "capabilities": list(caps), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"keyboard_tasks_permissions_check: {n} task(s) for {len(caps)} core "
              f"capabilities, {len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
