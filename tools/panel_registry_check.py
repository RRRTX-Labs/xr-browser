#!/usr/bin/env python3
"""tools/panel_registry_check.py — the panel tab registry lane (P13-T6 / C-5).

`panel-tab-registration-v1` is the contract that makes a panel tab a DECLARED
thing. xr-core's `ui/panel/tab-registry.ts` is its runtime half (typed refusals:
`unknown-tab-id`, `order-collision`, `order-mismatch`, `order-out-of-range`,
`duplicate-id`, `duplicate-order`, `bad-shape`) and this tool is its gate half —
the half that reads the inventory, the sibling's message table, the roster and
the §10 allowlist together, which no single file can do for itself.

WHAT IT CHECKS, one rule per failure mode:

  T1 every tab record in `ui/panel/tabs.json` validates against
     `panel-tab-registration-v1.schema.json` — same validator as the CLI
     (`xr_schema.validate_document`), never a second copy;
  T2 the vector suite agrees with the schema: each `accept` payload validates,
     each `refuse` payload fails WITH the reason the vector names. A vector file
     nothing runs is prose;
  T3 the inventory's own laws: ids are slugs, ids and orders are unique, and
     every order sits inside the reserved band the inventory declares. (The
     registry refuses these at runtime; a hand-edited JSON bypasses the runtime,
     which is why the gate re-derives them.)
  T4 every `title_msgid` exists in the sibling's `l10n/xr_strings.grdp` — a tab
     whose title is missing renders as its own id, a machine token in the tab
     strip, which is exactly the class of defect L24 keeps paying for;
  T5 the §10 CLAIM: every declared tab has an allowlist entry (`unit: tab`,
     `target: <id>`) carrying at least one `sources:` file. The bijection itself
     is R4 of tools/coverage_check.py, which walks the same two files; repeating
     it here would be a second home for one law. What is NOT checked anywhere
     else is the claim: a declared tab with no `sources:` line is a placeholder,
     and a placeholder that passes a gate is how a phase reports a tab it never
     built;
  T6 the §10 COMMAND is DECLARED: each tab's allowlist entry carries a
     `command`. Whether that command is in the roster is R1 of
     `tools/coverage_check.py` — the same law is not implemented twice here, and
     the two lanes are run together, so the pair is what makes the link real;
  T7 the BYPASS law: no declared tab id appears as a quoted literal in
     `ui/panel/panel-frame.ts` or `ui/panel/tab-strip.ts`. A frame that names a
     tab has stopped being registry-driven, and every later tab it fails to
     mention disappears without an error. The frame may know the REGISTRY; it
     may not know the tabs.

Sibling: the inventory, the grdp and the roster all live in xr-core, so the
checkout must be AT THE PIN (tools/xr_sibling.py). Absent / stale / dirty =>
typed BLOCKED-LAYOUT / STALE-SIBLING / DIRTY-SIBLING, exit 2 — never a vacuous
pass, never an ImportError.

Negatives: tools/negatives/p13_c5.sh (bypass, stale claim, undeclared tab).

Exit: 0 pass · 1 fail · 2 usage/BLOCKED-SIBLING. Stdlib only (PyYAML is the
pinned dev dep, as in tools/coverage_check.py).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xr_sibling  # noqa: E402
import xr_schema  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

REPO = Path(__file__).resolve().parents[1]
SCHEMA_REL = "docs/contracts/panel-tab-registration-v1.schema.json"
VECTORS_REL = "docs/contracts/vectors/panel-tab-registration-v1.json"
ALLOWLIST_REL = "docs/contracts/coverage-allowlist.yaml"
INVENTORY_REL = "ui/panel/tabs.json"
GRDP_REL = "l10n/xr_strings.grdp"
# The files that must stay ignorant of tab ids (the bypass law, T7).
FRAME_FILES = ("ui/panel/panel-frame.ts", "ui/panel/tab-strip.ts")

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _allowlist(path: Path) -> list[dict]:
    import yaml
    if not path.exists():
        return []
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return d.get("surfaces", []) or []


def check(repo: Path, override: str | None = None, ui_root: Path | None = None,
          allowlist: Path | None = None) -> list[str]:
    """Run every rule. `ui_root`/`allowlist` are FIXTURE overrides (negatives);
    a gate passes neither, so the pin check cannot be sidestepped in CI."""
    fails: list[str] = []
    if ui_root is None:
        sib = xr_sibling.check(repo, override=override)
        ui_root = sib.sub("ui")
    core = ui_root.parent

    schema_file = repo / SCHEMA_REL
    if not schema_file.exists():
        return [f"{SCHEMA_REL} is missing — the contract has no schema to be"]
    schema = _load_json(schema_file)

    # T2: the vectors must agree with the schema, in both directions.
    vectors_file = repo / VECTORS_REL
    if not vectors_file.exists():
        fails.append(f"{VECTORS_REL} is missing — the contract has no vectors")
    else:
        vectors = _load_json(vectors_file)
        for case in vectors.get("accept", []):
            errs = xr_schema.validate_document(case.get("payload"), schema)
            if errs:
                fails.append(f"vector accept/{case.get('case')} must validate: {errs}")
        for case in vectors.get("refuse", []):
            errs = xr_schema.validate_document(case.get("payload"), schema)
            want = case.get("expect_refusal", "")
            if not errs:
                fails.append(f"vector refuse/{case.get('case')} validated — it "
                             f"claims to be refused by the schema")
            elif want and want not in "\n".join(errs):
                fails.append(f"vector refuse/{case.get('case')} was refused for "
                             f"the wrong reason (wanted {want!r}): {errs}")

    # T1/T3: the inventory itself.
    inv_file = ui_root / "panel" / "tabs.json"
    if not inv_file.exists():
        return fails + [f"{INVENTORY_REL} is missing — there is no inventory to check"]
    inv = _load_json(inv_file)
    tabs = inv.get("tabs", []) or []
    reserved = inv.get("reserved_orders", {}) or {}
    lo, hi = reserved.get("min", 1), reserved.get("max", 9999)
    seen_ids: set[str] = set()
    seen_orders: dict[int, str] = {}
    for t in tabs:
        tid = str(t.get("id", "<no-id>"))
        errs = xr_schema.validate_document(t, schema)
        if errs:
            fails.append(f"inventory tab {tid} does not validate: {errs}")
        if not SLUG_RE.match(tid):
            fails.append(f"inventory tab id {tid!r} is not a slug")
        if tid in seen_ids:
            fails.append(f"inventory tab id {tid!r} is declared twice")
        seen_ids.add(tid)
        order = t.get("order")
        if isinstance(order, int):
            if order in seen_orders and seen_orders[order] != tid:
                fails.append(f"inventory order {order} is claimed by "
                             f"{seen_orders[order]!r} and {tid!r}")
            seen_orders[order] = tid
            if order < lo or order > hi:
                fails.append(f"inventory tab {tid!r} order {order} is outside "
                             f"the reserved band {lo}-{hi}")
        name = t.get("title_msgid")
        if isinstance(name, str) and f'xr-id="{name}"' not in (core / GRDP_REL).read_text(encoding="utf-8"):
            fails.append(f"tab {tid!r} title_msgid {name!r} is not in {GRDP_REL} "
                         f"— the strip would render the id instead of a title")

    # T5/T6: the §10 bijection and the covering command.
    allow = _allowlist(allowlist if allowlist is not None else repo / ALLOWLIST_REL)
    by_tab = {a.get("target"): a for a in allow
              if a.get("unit") == "tab" and a.get("target")}
    if not by_tab:
        fails.append(f"{ALLOWLIST_REL} declares no `unit: tab` surface — the "
                     f"inventory and the allowlist cannot be compared")
    for tid in sorted(seen_ids):
        entry = by_tab.get(tid)
        if entry is None:
            fails.append(f"tab {tid!r} is declared in {INVENTORY_REL} but no "
                         f"allowlist surface covers it (unit: tab, target: {tid})")
            continue
        if not entry.get("sources"):
            fails.append(f"tab {tid!r} is declared and allowlisted but claims no "
                         f"`sources:` file — a tab with no implementation is a "
                         f"placeholder, and a placeholder is not a feature")
        if not entry.get("command"):
            fails.append(f"tab {tid!r} claims no `command:` — a tab that maps to "
                         f"no command is a tab §10 does not ship (coverage_check "
                         f"R1 proves the command is in the roster)")
    # T7: the bypass law.
    for rel in FRAME_FILES:
        f = core / rel
        if not f.exists():
            fails.append(f"{rel} is missing (the bypass law has nothing to check)")
            continue
        src = f.read_text(encoding="utf-8")
        for tid in sorted(seen_ids):
            if re.search(rf"""['"]{re.escape(tid)}['"]""", src):
                fails.append(f"{rel} names the tab id {tid!r} as a literal — the "
                             f"frame is registry-driven or it is not (route it "
                             f"through ui/panel/tab-registry.ts)")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="panel_registry_check", description=__doc__)
    p.add_argument("--repo", default=".", help="xr-browser checkout (default .)")
    p.add_argument("--xr-core", default=None,
                   help="sibling xr-core checkout (default: ../xr-core)")
    p.add_argument("--ui-root", default=None,
                   help="fixture override: the WebUI root to read instead of "
                        "the sibling's (default: the pinned sibling's ui/)")
    p.add_argument("--allowlist", default=None,
                   help="fixture override: the coverage allowlist to read "
                        "(default: docs/contracts/coverage-allowlist.yaml)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    ui_root = Path(args.ui_root).resolve() if args.ui_root else None
    allow = Path(args.allowlist) if args.allowlist else None
    try:
        fails = check(repo, override=args.xr_core, ui_root=ui_root, allowlist=allow)
    except xr_sibling.SiblingError as err:
        print(xr_sibling.format_error(err), file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps({"tool": "panel_registry_check",
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: panel_registry_check "
              f"(inventory ↔ schema ↔ grdp ↔ allowlist claim, bypass law; "
              f"{len(fails)} failure(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
