#!/usr/bin/env python3
"""tools/a11y_lint.py — structural a11y gate over the WebUI (P7).

A11y is security-adjacent here: the palette is a screen-reader user's ONLY path
to commands (§10). The gate encodes the ARIA APG combobox pattern + focus +
empty-state live-region laws structurally (the linter is ours — cite: ARIA APG
"Combobox with Listbox Popup", focus-visible, aria-live):

  * The palette (ui/palette/**) implements the ARIA APG combobox:
    role="combobox" (the input), role="listbox" (the popup),
    aria-activedescendant, aria-expanded, aria-controls, aria-selected — all
    must be present. `aria-activedescendant` is the SR-critical one (the
    highlighted-but-not-focused option is announced through it).
  * Every empty state (no results / no identity) is a live region: at least one
    `aria-live=` in ui/**.
  * Focus is visible: `:focus-visible` in the ui CSS (keyboard users must see
    where focus is; "no coming-soon rails" includes no invisible focus).

Fixtures (tools/tests) prove each rule fails one bad file. Exit: 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"

# ARIA APG combobox: the input is role=combobox driving a role=listbox popup,
# with aria-activedescendant announcing the highlighted option to SRs.
REQUIRED_COMBO_ARIA = [
    'role="combobox"',
    'role="listbox"',
    "aria-activedescendant",
    "aria-expanded",
    "aria-controls",
    "aria-selected",
]
ARIALIVE_RE = re.compile(r'aria-live\s*=\s*["\'](polite|assertive)["\']')
FOCUS_RE = re.compile(r":focus-visible")


def _read(root: Path) -> str:
    out = []
    if root.is_dir():
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix in {".ts", ".tsx", ".js", ".mjs", ".html", ".css"}:
                out.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def check(repo: Path) -> list[str]:
    fails: list[str] = []
    palette_dir = XR_CORE / "ui" / "palette"
    palette = _read(palette_dir)
    if not palette.strip():
        fails.append("ui/palette: no palette sources found")
    else:
        for token in REQUIRED_COMBO_ARIA:
            if token not in palette:
                fails.append(f"ui/palette: missing ARIA APG combobox token {token!r}")
    allui = _read(XR_CORE / "ui")
    if not ARIALIVE_RE.search(allui):
        fails.append("ui/**: no aria-live (polite|assertive) empty-state live region")
    css = _read(XR_CORE / "ui")
    if not FOCUS_RE.search(css):
        fails.append("ui/** css: missing :focus-visible (keyboard focus must be visible)")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="a11y_lint", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--palette-dir", default=str(XR_CORE / "ui" / "palette"),
                   help="override palette dir (for fixtures)")
    p.add_argument("--ui-dir", default=str(XR_CORE / "ui"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    palette_dir = Path(args.palette_dir)
    ui_dir = Path(args.ui_dir)
    fails: list[str] = []
    palette = _read(palette_dir)
    if not palette.strip():
        fails.append(f"{palette_dir}: no palette sources found")
    else:
        for token in REQUIRED_COMBO_ARIA:
            if token not in palette:
                fails.append(f"{palette_dir}: missing ARIA APG combobox token {token!r}")
    allui = _read(ui_dir)
    if not ARIALIVE_RE.search(allui):
        fails.append(f"{ui_dir}: no aria-live (polite|assertive) empty-state live region")
    if not FOCUS_RE.search(allui):
        fails.append(f"{ui_dir} css: missing :focus-visible")
    if args.json:
        print(json.dumps({"tool": "a11y_lint", "count": len(fails),
                          "violations": fails}, sort_keys=True, indent=1))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"a11y_lint: {len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
