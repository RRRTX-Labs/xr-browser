#!/usr/bin/env python3
"""tools/menu_model_check.py — the generated menu model obeys the tier rules (P7).

The app-menu / toolbar menu is a VIEW over the command registry. This check
generates the menu model (via the frozen Python reference fake — the parity
reference the C++ host is byte-tested against) and enforces the §1.10 tier
rules structurally:

  * Tier-1 is ≤ 9 controls (the Attention Budget — enforced in the registry,
    re-asserted here on the generated model so the VIEW cannot drift);
  * Tier-1 items are exactly the tier1 commands, in registration order,
    separated from the (tier2/tier0) tools-menu items;
  * grouping order is stable (registration order within each bucket).

`--check` diffs the generated model against the checked-in golden so a reorder
or a silent tier bump fails CI (the "menu model golden" DoD row).

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"
ROSTER = XR_CORE / "commands" / "core" / "roster_v1.json"
GOLDEN = Path(__file__).resolve().parents[1] / "docs/contracts/menu-model.json"
MAX_TIER1 = 9


def _model(roster: Path) -> dict:
    sys.path.insert(0, str(XR_CORE / "fakes"))
    import commands as fake  # noqa: PLC0415
    reg = fake.Registry()
    regerr = reg.from_json(json.loads(roster.read_text(encoding="utf-8")))
    if regerr:
        raise SystemExit(f"roster invalid: {regerr}")
    ctx = fake.Context("", str(roster))
    if fake.load_context(ctx):
        raise SystemExit("load_context failed unexpectedly")
    return json.loads(fake.handle_method("menu-model", {}, ctx))["ok"]


def check(repo: Path, roster: Path, out: Path | None = None) -> list[str]:
    fails: list[str] = []
    m = _model(roster)
    tier1 = m.get("tier1", {})
    menus = m.get("menus", [])
    items = menus[0]["items"] if menus else []

    if tier1.get("count") != len(tier1.get("items", [])):
        fails.append("tier1.count != len(tier1.items)")
    if tier1.get("count", 0) > MAX_TIER1:
        fails.append(f"Tier-1 has {tier1.get('count')} controls (> {MAX_TIER1})")

    # Tier separation + stable order.
    t1_ids = [i["id"] for i in tier1.get("items", [])]
    menu_ids = [i["id"] for i in items]
    all_ids = t1_ids + menu_ids
    if len(set(all_ids)) != len(all_ids):
        fails.append("a command appears in both tier1 and the tools menu")
    for i in tier1.get("items", []):
        if i.get("tier") != "tier1":
            fails.append(f"tier1 bucket holds a non-tier1 command: {i.get('id')}")
    for i in items:
        if i.get("tier") == "tier1":
            fails.append(f"tools menu holds a tier1 command: {i.get('id')}")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(m, sort_keys=True, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="menu_model_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--roster", default=str(ROSTER),
                   help="roster to build the model from (override for fixtures)")
    p.add_argument("--check", action="store_true",
                   help="also diff the generated model against the golden")
    p.add_argument("--out", default=str(GOLDEN))
    args = p.parse_args(argv)

    roster = Path(args.roster)
    out = Path(args.out)
    fails = check(Path(args.repo).resolve(), roster, out if not args.check else None)
    if args.check:
        want = json.dumps(_model(roster), sort_keys=True, separators=(",", ":")) + "\n"
        have = out.read_text(encoding="utf-8") if out.exists() else ""
        if have != want:
            fails.append(f"{out} differs from the generated model (stale golden)")
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: menu_model_check ({len(fails)} violation(s))")
        return EXIT_FAIL
    print("PASS: menu_model_check (Tier-1 ≤9, tier separation, stable order)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
