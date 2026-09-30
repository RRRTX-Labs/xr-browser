#!/usr/bin/env python3
"""tools/coverage_check.py — §10 command-coverage gate (P7-T9; unit fixed P13-C-P0.1).

Law (Plan §10, verbatim): "any feature without a command does not ship (CI
check: every `Settings` section and panel tab maps to a command)."

THE UNIT IS A DECLARED TAB OR SECTION — NOT A FILE.
---------------------------------------------------
Until P13-C-P0.1 this tool treated every `ui/panel/<name>.ts` as a surface and
demanded a command for it. Measured at e503f9e that produced two red lanes:

    FAIL: landed surface panel/focus-trap (panel/focus-trap.ts) has no command
    registered (§10)
    FAIL: landed surface panel/panel-frame (panel/panel-frame.ts) has no ...

A focus trap and a frame are not tabs; they are the *implementation* of the
`panel/xr` surface. The law was right and the unit was wrong, so the fix is a
declaration mechanism, not an exemption: this tool now reads

  * the panel's tab inventory  — `ui/panel/tabs.json` (xr-core), the same file
    `ui/panel/tab-registry.ts` refuses unknown ids against at runtime;
  * the settings sections      — `settings/core/settings_schema_v1.json`;
  * `docs/contracts/coverage-allowlist.yaml`, whose every entry now carries a
    `sources:` membership list naming the files that implement it.

WHAT IT CHECKS (each rule with a registered negative in tools/negatives/):
  R1 every declared surface's covering command is IN the roster;
  R2 every landed `.ts` source under `ui/{settings,panel}/` is CLAIMED by
     exactly one declared surface's `sources:` — an unaccounted file fails, and
     so does a file claimed twice (the old "any .ts under ui/panel" scan is
     gone; not knowing which surface a file belongs to is the finding);
  R3 a `sources:` entry that does not exist in the tree fails (a stale claim);
  R4 the tab inventory and the allowlist's `unit: tab` entries are a BIJECTION:
     a tab that is registered without a declared covering surface fails, and a
     declared tab surface with no inventory entry fails;
  R5 the settings schema's sections and the allowlist's `unit: section`
     entries are a bijection, the same way.

Symmetry is the point of R4/R5: an inventory that may drift from the allowlist
in one direction only is how a `.ts` file came to be treated as a feature.

The forbidden fixes, named so a future edit cannot take them: a `skip:` pattern
for `focus-trap`, a synthetic command for a trap, a synthetic tab in the
inventory, or widening this file. All four are negatives.

Sibling: the roster lives in xr-core, so this gate needs the sibling AT THE PIN
(tools/xr_sibling.py). Absent/old/dirty => typed BLOCKED-LAYOUT / STALE-SIBLING
/ DIRTY-SIBLING and **exit 2**, never an ImportError and never a silent pass —
the vacuous local PASS that let this red reach the pin was exactly that.

Exit: 0 pass · 1 fail · 2 usage/BLOCKED-SIBLING.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xr_sibling  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

REPO = Path(__file__).resolve().parents[1]
XR_CORE = REPO.parent / "xr-core"
ALLOWLIST = REPO / "docs/contracts/coverage-allowlist.yaml"
UI_KINDS = ("settings", "panel")


def _registry_ids(repo: Path, xr_core: str | None = None) -> set[str]:
    """Roster ids, from a sibling that has been PROVEN to be at the pin."""
    sib = xr_sibling.check(repo, override=xr_core)
    sys.path.insert(0, str(sib.fakes))
    import commands as fake  # noqa: PLC0415

    reg = fake.Registry()
    reg.from_json(json.loads(
        sib.sub("commands/core/roster_v1.json").read_text(encoding="utf-8")))
    return set(reg.order)


def _load_allowlist(path: Path) -> list[dict]:
    import yaml
    if not path.exists():
        return []
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return d.get("surfaces", []) or []


def _landed_sources(ui_root: Path) -> set[str]:
    """Every non-test `.ts` under ui/{settings,panel}/, as ui-root-relative paths.

    Descent skips `tests/` and `index.ts`: a node:test file is not a surface and
    `index.ts` is a barrel. Everything else must be claimed (R2) — the honest
    answer to "which surface does this file implement?" is a declaration, and
    "I cannot tell" must fail rather than pass. The §10 law names Settings
    sections and panel tabs, so only those two subtrees are scanned; other
    subsystems (`ui/shield`, `ui/about`, ...) are governed by their own phase's
    lanes and are not silently swept in here.
    """
    landed: set[str] = set()
    for kind in UI_KINDS:
        d = ui_root / kind
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.ts")):
            rel = f.relative_to(ui_root)
            if "tests" in rel.parts or f.stem == "index":
                continue
            landed.add(rel.as_posix())
    return landed


def _tab_inventory(ui_root: Path) -> tuple[list[dict], list[str]]:
    """(tabs, findings) from ui/panel/tabs.json. Absent file => no tabs, no finding."""
    path = ui_root / "panel" / "tabs.json"
    if not path.is_file():
        return [], []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [], [f"{path.name} is not valid JSON ({exc}) — the tab inventory "
                    f"is the unit of the §10 law and cannot be unreadable"]
    tabs = doc.get("tabs")
    if not isinstance(tabs, list):
        return [], [f"{path.name} has no `tabs` array — declare the panel's tabs "
                    f"or there is no unit to check"]
    fails: list[str] = []
    orders: dict[int, str] = {}
    for i, t in enumerate(tabs):
        if not isinstance(t, dict) or not t.get("id"):
            fails.append(f"{path.name}: tabs[{i}] is not a tab declaration")
            continue
        for key in ("title_msgid", "order", "requires_identity_scope"):
            if key not in t:
                fails.append(f"{path.name}: tab {t['id']!r} is missing {key!r} "
                             f"(panel-tab-registration-v1)")
        o = t.get("order")
        if isinstance(o, int):
            if o in orders:
                fails.append(f"{path.name}: order {o} claimed by both "
                             f"{orders[o]!r} and {t['id']!r} — two tabs claiming "
                             f"one order is a validation failure")
            orders[o] = str(t["id"])
    return tabs, fails


def _section_inventory(ui_root: Path) -> set[str] | None:
    """Settings schema section ids, or None when the schema is not readable."""
    p = ui_root.parent / "settings" / "core" / "settings_schema_v1.json"
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return {str(s.get("id")) for s in doc.get("sections", []) if s.get("id")}


def check(ui_root: Path, allowlist_path: Path | None = None,
          registry_ids: set[str] | None = None,
          xr_core: str | None = None, repo: Path | None = None) -> list[str]:
    """Findings for one ui-root; [] == pass. Never raises for a missing input."""
    fails: list[str] = []
    root = Path(ui_root)
    ids = (registry_ids if registry_ids is not None
           else _registry_ids(repo or REPO, xr_core))
    surfaces = _load_allowlist(Path(allowlist_path or ALLOWLIST))

    declared: dict[str, str] = {}
    claimed: dict[str, list[str]] = {}
    for s in surfaces:
        surf = s.get("surface")
        cmd = s.get("command")
        if not surf or not cmd:
            fails.append(f"allowlist surface missing surface/command: {s}")
            continue
        declared[surf] = cmd
        if cmd not in ids:
            fails.append(f"surface {surf}: covering command {cmd} is not "
                         f"registered in the roster (§10: a feature without a "
                         f"command does not ship)")
        sources = s.get("sources") or []
        if not isinstance(sources, list):
            fails.append(f"surface {surf}: sources must be a list of ui-root "
                         f"relative paths")
            sources = []
        for src in sources:
            claimed.setdefault(str(src), []).append(str(surf))

    # R2/R3: file membership, both directions.
    landed = _landed_sources(root)
    for path in sorted(landed):
        owners = claimed.get(path, [])
        if not owners:
            fails.append(f"unaccounted source {path} — §10's unit is a declared "
                         f"tab/section, so name the surface this file implements "
                         f"in docs/contracts/coverage-allowlist.yaml `sources:` "
                         f"(a file is not a unit; silence is not a claim)")
        elif len(owners) > 1:
            fails.append(f"source {path} is claimed by {len(owners)} surfaces "
                         f"({', '.join(sorted(owners))}) — one file, one surface")
    for path, owners in sorted(claimed.items()):
        if not (root / path).is_file():
            fails.append(f"surface {owners[0]} claims source {path}, which is "
                         f"not in the tree — a stale claim is a coverage hole "
                         f"with a citation")

    # R4: the tab inventory <-> the allowlist's tab surfaces are a bijection.
    tabs, tab_fails = _tab_inventory(root)
    fails.extend(tab_fails)
    inventory = {f"panel/{t['id']}" for t in tabs if isinstance(t, dict) and t.get("id")}
    declared_tabs = {str(x.get("surface")) for x in surfaces if x.get("unit") == "tab"}
    for surf in sorted(inventory - declared_tabs):
        tab_id = surf.split("/", 1)[1]
        fails.append(f"tab {tab_id!r} ({surf}) is registered in the panel's tab "
                     f"inventory with no declared covering surface in the "
                     f"allowlist — §10: a feature without a command does not ship")
    for surf in sorted(declared_tabs - inventory):
        fails.append(f"allowlist declares tab surface {surf} but the panel's tab "
                     f"inventory (ui/panel/tabs.json) has no such tab — a "
                     f"declaration that outruns the inventory is untestable")

    # R5: same bijection for settings sections.
    sections = _section_inventory(root)
    if sections is not None:
        declared_sections = {str(x.get("surface")) for x in surfaces
                             if x.get("unit") == "section"}
        inv_sections = {f"settings/{s}" for s in sections}
        for surf in sorted(inv_sections - declared_sections):
            fails.append(f"settings section {surf} is in the settings schema "
                         f"with no declared covering surface in the allowlist (§10)")
        for surf in sorted(declared_sections - inv_sections):
            fails.append(f"allowlist declares settings section {surf}, which the "
                         f"settings schema does not define")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="coverage_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--xr-core", default=None,
                   help="sibling xr-core checkout (default: ../xr-core)")
    p.add_argument("--ui-root", default=None,
                   help="WebUI root to scan for landed surfaces (override for "
                        "fixtures; default: the sibling's ui/)")
    p.add_argument("--allowlist", default=None,
                   help="coverage allowlist to read (default: "
                        "docs/contracts/coverage-allowlist.yaml). Gates never "
                        "pass this; fixture negatives do.")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    ui_root = Path(args.ui_root).resolve() if args.ui_root else None
    try:
        if ui_root is None:
            sib = xr_sibling.check(repo, override=args.xr_core)
            ui_root = sib.sub("ui")
        allow = Path(args.allowlist) if args.allowlist else None
        fails = check(ui_root, allow, xr_core=args.xr_core, repo=repo) if ui_root else []
    except xr_sibling.SiblingError as err:
        print(xr_sibling.format_error(err), file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps({"tool": "coverage_check",
                          "status": "pass" if not fails else "fail",
                          "unit": "declared tab/section",
                          "failures": fails}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: coverage_check "
              f"(unit: declared tab/section; {len(fails)} failure(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
