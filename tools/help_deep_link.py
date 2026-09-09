#!/usr/bin/env python3
"""tools/help_deep_link.py — Help <-> Settings deep-link contract lint (P8-T7).

Machine-checks docs/contracts/help-deep-link-v1.md against the two
authorities it cites:

  L1  settings -> help: every settings-schema section S has a registered
      command `settings.S` in docs/contracts/commands.md and it is enabled;
  L2  help -> settings: every registered `settings.*` command maps back to
      an existing schema section;
  L3  the schema anchor_root is exactly `xr://settings`;
  L4  the contract doc exists and cites both schemes (marker check), so the
      doc can never silently stop describing what the gate enforces.

commands.md rows are parsed mechanically from the markdown table
(`| `id` | scope | tier | danger | predicate | status |`); a settings
command counts as enabled only when its status column begins with
`enabled`.

Exit: 0 = pass, 1 = violations, 2 = usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

ROW_RE = re.compile(r"^\|\s*`([a-z0-9][a-z0-9.-]*)`\s*\|\s*[^|]+\|\s*[^|]+\|"
                    r"\s*[^|]+\|\s*[^|]+\|\s*([a-z][a-z0-9 ().,-]*)\s*\|")


def load_commands(path: Path) -> dict[str, bool]:
    """id -> enabled (True/False) from the generated roster table."""
    out: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2).startswith("enabled")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="help_deep_link",
                                 description="settings<->help anchor lint")
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--commands", default="docs/contracts/commands.md")
    ap.add_argument("--contract", default="docs/contracts/help-deep-link-v1.md")
    args = ap.parse_args(argv)

    root = Path.cwd().resolve()
    fails: list[str] = []

    schema = (Path(args.xr_core).resolve()
              / "settings/core/settings_schema_v1.json")
    if not schema.exists():
        fails.append(f"schema missing: {schema}")
        return EXIT_FAIL
    doc = json.loads(schema.read_text(encoding="utf-8"))

    if doc.get("anchor_root") != "xr://settings":
        fails.append(f"schema anchor_root must be 'xr://settings' "
                     f"(got {doc.get('anchor_root')!r})")  # L3

    sections = [s.get("id", "") for s in doc.get("sections", [])]
    if not sections:
        fails.append("schema has no sections")
    cmds = load_commands(Path(args.commands).resolve())
    if not cmds:
        fails.append(f"no commands parsed from {args.commands}")

    # L1: every section has an enabled settings.<S> command.
    for s in sections:
        cid = f"settings.{s}"
        if cid not in cmds:
            fails.append(f"L1: section '{s}' has no command '{cid}'")
        elif not cmds[cid]:
            fails.append(f"L1: command '{cid}' exists but is disabled "
                         "(help anchor must be enabled)")

    # L2: every settings.* command maps to an existing section.
    for cid, enabled in cmds.items():
        if not cid.startswith("settings."):
            continue
        s = cid[len("settings."):]
        if s not in sections:
            fails.append(f"L2: command '{cid}' has no schema section '{s}'")
        if not enabled:
            fails.append(f"L2: '{cid}' is disabled — deep-link target "
                         "unreachable per contract")

    # L4: contract doc present with both schemes cited.
    cp = Path(args.contract).resolve()
    if not cp.exists():
        fails.append(f"contract missing: {cp}")
    else:
        t = re.sub(r"\s+", " ", cp.read_text(encoding="utf-8"))
        for marker in ("xr://help/", "xr://settings/"):
            if marker not in t:
                fails.append(f"L4: contract {cp.name} no longer cites "
                             f"{marker!r}")

    if fails:
        for f in fails:
            print(f"help_deep_link: {f}", file=sys.stderr)
        return EXIT_FAIL
    print(f"help_deep_link: OK ({len(sections)} sections, "
          f"{sum(1 for c in cmds.values() if c)} enabled commands, "
          f"contract markers present)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
