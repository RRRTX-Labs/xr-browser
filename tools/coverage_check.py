#!/usr/bin/env python3
"""tools/coverage_check.py — §10 command-coverage gate (P7-T9).

Law (Plan §10, verbatim): "any feature without a command does not ship (CI
check: every `Settings` section and panel tab maps to a command)."

Settings pages (P8) and XR Panel tabs (P13) don't exist yet, so this ships
with the **not-yet-built allowlist** (`docs/contracts/coverage-allowlist.yaml`):
each future surface is declared with its landing phase + the command that must
cover it (the P7 roster pre-registers the settings jumps + panel open). The
check does two things, both structural so they bite from P8/P13 first-land
(mode_lint precedent — enforce structurally now):

  1. every declared surface has a covering command that IS registered in the
     roster (the covering command must not drift out of the registry);
  2. any surface that has LANDED in the tree (a `ui/settings/<x>` or
     `ui/panel/<x>` source) must be covered — a phase that ships a section/tab
     without registering a command FAILS (the "future-bite", fixture-proven).

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"
ALLOWLIST = Path(__file__).resolve().parents[1] / "docs/contracts/coverage-allowlist.yaml"


def _registry_ids() -> set[str]:
    sys.path.insert(0, str(XR_CORE / "fakes"))
    import commands as fake  # noqa: PLC0415
    reg = fake.Registry()
    reg.from_json(json.loads(
        (XR_CORE / "commands/core/roster_v1.json").read_text(encoding="utf-8")))
    return set(reg.order)


def _load_allowlist(path: Path) -> list[dict]:
    import yaml
    if not path.exists():
        return []
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return d.get("surfaces", []) or []


def _landed_surfaces(ui_root: Path) -> dict[str, list[str]]:
    """Scan the WebUI tree for LANDED settings sections / panel tabs.

    The WebUI lives in xr-core/ui (not the browser repo), so this scans the
    ui-root, not the browser repo.
    """
    landed: dict[str, list[str]] = {}
    for base, kind in (("settings", "settings"), ("panel", "panel")):
        d = ui_root / base
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.ts")):
            name = f.stem
            if name in ("index",):
                continue
            landed.setdefault(f"{kind}/{name}", []).append(str(f.relative_to(ui_root)))
    return landed


def check(ui_root: Path) -> list[str]:
    fails: list[str] = []
    ids = _registry_ids()
    surfaces = _load_allowlist(ALLOWLIST)

    declared: dict[str, str] = {}
    for s in surfaces:
        surf = s.get("surface")
        cmd = s.get("command")
        if not surf or not cmd:
            fails.append(f"allowlist surface missing surface/command: {s}")
            continue
        declared[surf] = cmd
        if cmd not in ids:
            fails.append(f"surface {surf}: covering command {cmd} is not registered "
                         "in the roster (§10: a feature without a command does not ship)")

    # Future-bite: a LANDED surface must be covered.
    for surf, paths in _landed_surfaces(ui_root).items():
        if surf not in declared:
            fails.append(f"landed surface {surf} ({paths[0]}) has no command "
                         f"registered (§10) — declare it in the allowlist with a command")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="coverage_check", description=__doc__)
    p.add_argument("--repo", default=".",
                   help="(accepted for house-style consistency; the WebUI ui-root is what's scanned)")
    p.add_argument("--ui-root", default=str(XR_CORE / "ui"),
                   help="WebUI root to scan for landed surfaces (override for fixtures)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    fails = check(Path(args.ui_root).resolve())
    if args.json:
        print(json.dumps({"tool": "coverage_check",
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: coverage_check")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
