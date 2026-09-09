#!/usr/bin/env python3
"""tools/tokens_gen.py — token pipeline: one JSON source, two consumers (P8-T2).

`xr-core/ui/themes/tokens.json` (40 tokens, schema_version 1) is the SINGLE
source. This tool generates:

  * `xr-core/ui/themes/tokens.h` — C++20 header with `inline constexpr`
    `uint32_t` colors in **0xAARRGGBB** order and name accessors, PLUS the
    dimension (int) and font (constexpr char[]) tokens. Deliberately NOT
    SkColor and with no Skia/Chromium include: views that consume the header
    must not pull Skia (recorded decision — the header is std-only).
  * `xr-core/ui/tokens.css` — the `--xr-*` custom-property block + the static
    chrome rules the P7 views rely on (values converted from the P7
    hand-written file 1:1; P7's file is now GENERATED, diff-checked).

Strictness (never weakened):
  * unknown `schema`/`schema_version` => refuse (rollback law: versioning);
  * unknown token names / token fields / theme keys => refuse;
  * duplicate keys anywhere => refuse (json object_pairs_hook);
  * every declared token must have a value in EVERY shipped theme, and no
    extra values may exist;
  * type checks: colors `#rrggbb`/`#rrggbbaa`, dimensions int 0..4096,
    fonts a safe system-font stack string (no `url(`, no `;`/`{`/`}`);
  * `critical-red` is RESERVED in data AND validator: its value must be in
    the canonical alarming family (red-dominant, high red channel) — a theme
    mapping it to a non-alarming color is refused here for built-in data and
    by the theme import validator (T4) for hostile input;
  * color hexes are written to the header as uint32 0xAARRGGBB (never
    SkColor), so web/native semantics never fork.

`--check` makes the committed generated files diff-clean in CI (same pattern
as descriptors_to_docs.py --check). CSS generation (static rules + gen_css)
lives in tools/tokens_gen_css.py (split under the 400-LOC law).

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from tokens_gen_css import gen_css  # split module (400-LOC law)

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
EXPECTED_SCHEMA = "xr-design-tokens"
EXPECTED_VERSION = 1
DEFAULT_XR_CORE = "../xr-core"

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
FONT_BAD = re.compile(r"[;{}]|url\(|\n")
DIMENSION_MAX = 4096


def _load_no_dups(path: Path) -> dict:
    """json.load with duplicate-key refusal (never last-wins on OUR source)."""
    text = path.read_text(encoding="utf-8")

    def hook(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"duplicate key {k!r} in {path}")
            obj[k] = v
        return obj

    return json.loads(text, object_pairs_hook=hook)


def _camel(name: str) -> str:
    return "k" + "".join(p.capitalize() for p in name.split("-"))


def _hex_to_argb(hexv: str) -> int:
    h = hexv[1:]
    if len(h) == 6:
        h += "ff"
    # h = rrggbbaa -> 0xAARRGGBB
    rr, gg, bb, aa = h[0:2], h[2:4], h[4:6], h[6:8]
    return int(aa + rr + gg + bb, 16)


def validate(doc: dict, path: Path) -> list[str]:
    """Returns failure strings (empty = the data is valid + strict-clean)."""
    fails: list[str] = []
    if not isinstance(doc, dict):
        return [f"{path}: top level must be an object"]
    if doc.get("schema") != EXPECTED_SCHEMA:
        fails.append(f"{path}: unknown schema {doc.get('schema')!r} "
                     f"(expected {EXPECTED_SCHEMA!r})")
    if doc.get("schema_version") != EXPECTED_VERSION:
        fails.append(f"{path}: unknown schema_version "
                     f"{doc.get('schema_version')!r} (v{EXPECTED_VERSION} only — "
                     "rollback law: tokens_gen refuses unknown versions)")
    meta = doc.get("tokens")
    themes = doc.get("themes")
    reserved = doc.get("reserved", {})
    if not isinstance(meta, dict) or not meta:
        fails.append(f"{path}: 'tokens' object required")
    if not isinstance(themes, dict) or not themes:
        fails.append(f"{path}: 'themes' object required (at least one theme)")
    if fails:
        return fails

    names = list(meta)
    for name, row in meta.items():
        if not isinstance(row, dict):
            fails.append(f"token {name}: meta must be an object")
            continue
        bad = set(row) - {"type", "usage", "pairing", "security_critical",
                          "reserved"}
        if bad:
            fails.append(f"token {name}: unknown meta field {sorted(bad)[0]!r}")
        typ = row.get("type")
        if typ not in ("color", "dimension", "font"):
            fails.append(f"token {name}: unknown type {typ!r}")
        for p in row.get("pairing", []) or []:
            if p not in names:
                fails.append(f"token {name}: pairing {p!r} is not a token")
    # values: every theme covers every token, nothing extra (a theme-level
    # "waivers" key carries the machine-readable contrast waivers — T3).
    for tname, values in themes.items():
        if not isinstance(values, dict):
            fails.append(f"theme {tname}: values must be an object")
            continue
        wv = values.get("waivers")
        if wv is not None:
            if not isinstance(wv, list):
                fails.append(f"theme {tname}: waivers must be a list")
            else:
                for row in wv:
                    if not isinstance(row, dict) or not all(
                            k in row for k in ("token", "pair", "best",
                                               "reason")):
                        fails.append(f"theme {tname}: waiver row must carry "
                                     "token/pair/best/reason")
        for name in names:
            if name not in values:
                fails.append(f"theme {tname}: missing value for token {name!r}")
        for name in values:
            if name == "waivers":
                continue
            if name not in meta:
                fails.append(f"theme {tname}: value for unknown token {name!r}")
            elif name in meta:
                row = meta[name]
                v = values[name]
                if row["type"] == "color":
                    if not isinstance(v, str) or not HEX_RE.match(v):
                        fails.append(f"theme {tname}: {name} not a hex color: {v!r}")
                elif row["type"] == "dimension":
                    if not isinstance(v, int) or isinstance(v, bool) or \
                            not (0 <= v <= DIMENSION_MAX):
                        fails.append(f"theme {tname}: {name} not a dimension "
                                     f"int 0..{DIMENSION_MAX}: {v!r}")
                elif row["type"] == "font":
                    if not isinstance(v, str) or not v.strip() or \
                            FONT_BAD.search(v):
                        fails.append(f"theme {tname}: {name} unsafe font string")
    # system resolution (T3): the System built-in is a resolver, not a
    # palette; modes must point at shipped built-ins.
    sysr = doc.get("system_resolution")
    if not isinstance(sysr, dict):
        fails.append("system_resolution object required (System resolver)")
    else:
        sd = sysr.get("default")
        modes = sysr.get("modes")
        if not isinstance(sd, str) or not isinstance(modes, dict):
            fails.append("system_resolution.default/modes required")
        else:
            for mode, target in modes.items():
                if mode not in ("light", "dark", "high-contrast"):
                    fails.append(f"unknown system mode {mode!r}")
                if not isinstance(target, str) or target not in themes:
                    fails.append(f"system mode {mode!r} target must be a "
                                 "shipped built-in theme")
            if sd not in modes:
                fails.append("system_resolution.default must name a mode")
    # reserved law: critical-red reserved in data + validator.
    cr = meta.get("critical-red")
    if cr is None:
        fails.append("critical-red token missing (reserved — must exist)")
    elif not cr.get("reserved"):
        fails.append("critical-red must carry reserved:true in data")
    elif not cr.get("security_critical"):
        fails.append("critical-red must carry security_critical:true")
    if "critical-red" not in reserved:
        fails.append("top-level 'reserved' must document critical-red "
                     "(data, not a comment)")
    for tname, values in themes.items():
        v = values.get("critical-red")
        if isinstance(v, str) and HEX_RE.match(v):
            h = v[1:]
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
            # Recorded alarming-family law (identical in theme.cc +
            # fakes/themes.py): r >= 0x60, red-dominant, and the gap
            # r - min(g,b) >= 0x60 (pale pastels and calm colors refused).
            if not (r >= 0x60 and r >= max(g, b) and
                    (r - min(g, b)) >= 0x60):
                fails.append(f"theme {tname}: critical-red {v} is not in the "
                             "canonical alarming family (reserved law)")
    return fails


def gen_header(doc: dict) -> str:
    meta = doc["tokens"]
    order = list(meta)
    L: list[str] = []
    L.append("// Copyright 2026 RRRTX Labs")
    L.append("// Use of this source code is governed by the MPL-2.0 license that can be")
    L.append("// found in the LICENSE file.")
    L.append("//")
    L.append("// GENERATED FILE — do not hand-edit. Regenerate with")
    L.append("//   python3 tools/tokens_gen.py   (xr-browser)")
    L.append("// and keep `tools/tokens_gen.py --check` diff-clean in CI.")
    L.append("//")
    L.append("// Token pipeline (P8-T2): one JSON source (ui/themes/tokens.json)")
    L.append("// -> tokens.h (C++ uint32_t 0xAARRGGBB) + tokens.css (--xr-* vars).")
    L.append("// Colors are uint32_t 0xAARRGGBB, NEVER SkColor and with NO")
    L.append("// Skia/Chromium include — consumers must not pull Skia (the")
    L.append("// recorded header-type decision, research-log-P8). 'critical-red'")
    L.append("// is reserved in data + validator.")
    L.append("#pragma once")
    L.append("")
    L.append("#include <cstdint>")
    L.append("")
    L.append("namespace xr {")
    L.append("namespace tokens {")
    L.append("")
    theme = doc["themes"]["light"]  # header ships the v1 baseline (light)
    for name in order:
        row = meta[name]
        v = theme[name]
        c = _camel(name)
        if row["type"] == "color":
            L.append(f"// {name}: {v} ({row['usage']})")
            L.append(f"inline constexpr uint32_t {c} = 0x{_hex_to_argb(v):08X};")
            if row.get("reserved"):
                L.append(f"// RESERVED token — never themeable to a non-alarming color.")
        elif row["type"] == "dimension":
            L.append(f"// {name}: {v}px ({row['usage']})")
            L.append(f"inline constexpr int {c} = {int(v)};")
        else:
            L.append(f"// {name} ({row['usage']})")
            L.append(f'inline constexpr char {c}[] = "{v}";')
        L.append("")
    L.append("}  // namespace tokens")
    L.append("}  // namespace xr")
    return "\n".join(L) + "\n"


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="tokens_gen", description=__doc__)
    p.add_argument("--xr-core", default=DEFAULT_XR_CORE)
    p.add_argument("--check", action="store_true",
                   help="fail when the generated files are not diff-clean")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    core = Path(args.xr_core).resolve()
    src = core / "ui/themes/tokens.json"
    if not src.is_file():
        print(f"error: tokens source not found: {src}", file=sys.stderr)
        return EXIT_USAGE
    try:
        doc = _load_no_dups(src)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"error: tokens source unparseable: {e}", file=sys.stderr)
        return EXIT_FAIL
    fails = validate(doc, src)
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"tokens_gen: {len(fails)} violation(s) (FAIL)")
        return EXIT_FAIL

    header = gen_header(doc)
    css = gen_css(doc)
    h_path = core / "ui/themes/tokens.h"
    c_path = core / "ui/tokens.css"
    h_dirty = write_if_changed(h_path, header)
    c_dirty = write_if_changed(c_path, css)

    if args.check:
        if h_dirty or c_dirty:
            print("FAIL: tokens.h/tokens.css drifted from tokens.json — "
                  "run tools/tokens_gen.py")
            return EXIT_FAIL
        print("tokens_gen --check: diff-clean (tokens.h + tokens.css)")
        return EXIT_PASS
    if h_dirty or c_dirty:
        print(f"wrote {h_path}")
        print(f"wrote {c_path}")
    else:
        print("tokens.h + tokens.css already up to date")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
