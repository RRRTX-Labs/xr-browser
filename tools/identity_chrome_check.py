#!/usr/bin/env python3
"""tools/identity_chrome_check.py — the identity-chrome state law + snapshots.

P14-T4 (P14-CLOSE C-1). The state -> visual mapping is data
(xr-core/ui/identity-chrome/states.json), and this gate holds it to a law:

  1. every state has a unique `xr-idc--` class, an accessible-name message,
     an SR string (announced on tab focus) and a route message, and each of
     those messages exists in xr-core/l10n/xr_strings.grdp (by xr-id);
  2. every state has at least one sample, and every sample's name, color and
     glyph equal the identity core's template table
     (xr-core/identity/core/templates.cc, read live). The chrome cannot drift
     from what provisioning actually mints;
  3. every state x theme has its contrast pairs, computed from
     ui/themes/tokens.json (never typed in):
     * mark (bar or dot) against the tab strip, 3:1 for a non-text graphic.
       Below that, a text-token edge is REQUIRED and must itself reach 3:1;
     * pill text against the pill background, 4.5:1. There is no fallback;
       a miss is a FAIL;
     * window border against the strip, 3:1, else the same edge rule;
  4. per-layout x per-theme STRUCTURAL snapshots (DOM/AX shape, never pixels)
     under xr-core/ui/identity-chrome/snapshots/ are exactly this generator's
     output. `--check` is diff-clean or FAIL; `--write` is the deliberate
     regeneration and the gate never passes it. tests/identity-chrome.test.mjs
     (build/webui/identity-chrome-tests.sh) holds the TypeScript core to the
     same files, so the two implementations cannot drift.

Negatives: tools/negatives/p14c_c1.sh (a planted state with no SR string, a
missing grdp message, a template color drift, a hand-edited snapshot).

Exit: 0 pass · 1 fail · 2 usage/layout. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xr_sibling import resolve_or_exit  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
REPO = Path(__file__).resolve().parents[1]
CHROME = Path("ui") / "identity-chrome"
REQUIRED_STATE_KEYS = ("class", "accessible_name", "sr", "route", "window_border")


def _channel(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")[:6]
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"color-not-hex: {hexcolor!r}")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG ratio, rounded half-up to 2 decimals (the TS core's exact rule)."""
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return math.floor(((hi + 0.05) / (lo + 0.05)) * 100 + 0.5) / 100


def _edge(table: dict, theme: dict, ratio: float) -> dict | None:
    if ratio >= table["contrast_min"]["non_text"]:
        return None
    color = theme[table["tokens"]["edge"]]
    return {"token": table["tokens"]["edge"], "px": table["edge_px"], "color": color,
            "ratio": contrast(color, theme[table["tokens"]["strip_surface"]])}


def structure(table: dict, theme: dict, ident: dict, layout_id: str) -> dict:
    """Python port of chrome-core.ts structure(); the TS test pins equality."""
    state = table["states"][ident["state"]]
    layout = table["layouts"][layout_id]
    surface = theme[table["tokens"]["strip_surface"]]
    mark_ratio = contrast(ident["color"], surface)
    if layout["mark"] == "dot":
        mark = {"part": "dot", "px": table["dot_px"], "color": ident["color"],
                "edge": _edge(table, theme, mark_ratio)}
        glyph = ident["name"][:1].upper()
    else:
        mark = {"part": "bar", "side": layout["bar_side"], "px": table["bar_px"],
                "color": ident["color"], "edge": _edge(table, theme, mark_ratio)}
        glyph = ident["glyph"]
    children = [mark]
    if layout["glyph"]:
        children.append({"part": "glyph", "text": glyph, "aria_hidden": True})
    if layout["label"]:
        children.append({"part": "label", "text": ident["name"]})
    border, border_ratio = None, None
    spec = state["window_border"]
    if spec:
        color = ident["color"] if spec["color"] == "identity" else \
            theme[spec["color"].removeprefix("token:")]
        border_ratio = contrast(color, surface)
        border = {"part": "window-border", "style": spec["style"], "px": spec["px"],
                  "color": color, "edge": _edge(table, theme, border_ratio),
                  "aria_hidden": True}
    route = {"msg": state["route"]}
    return {
        "sample": ident["template"], "state": ident["state"],
        "class": ["xr-idc", state["class"]],
        "tab": {"role": "tab",
                "description": {"msg": state["sr"], "params": {"NAME": ident["name"]}},
                "children": children},
        "pill": {"role": "button",
                 "name": {"msg": state["accessible_name"],
                          "params": {"NAME": ident["name"], "ROUTE": route}},
                 "children": [
                     {"part": "swatch", "color": ident["color"], "aria_hidden": True},
                     {"part": "glyph", "text": ident["glyph"], "aria_hidden": True},
                     {"part": "name", "text": ident["name"]},
                     {"part": "route", "msg": state["route"]}]},
        "window_border": border,
        "contrast": {"mark": mark_ratio,
                     "pill_text": contrast(theme[table["tokens"]["pill_text"]],
                                           theme[table["tokens"]["pill_bg"]]),
                     "window_border": border_ratio},
    }


def snapshots(table: dict, themes: dict) -> dict[str, str]:
    """{filename: bytes} for every layout x theme. Deterministic."""
    out: dict[str, str] = {}
    for layout_id in sorted(table["layouts"]):
        for theme_id in sorted(themes):
            doc = {"schema": "identity-chrome-snapshot-v1", "layout": layout_id,
                   "theme": theme_id,
                   "nodes": [structure(table, themes[theme_id], s, layout_id)
                             for s in table["samples"]]}
            out[f"{layout_id}.{theme_id}.json"] = \
                json.dumps(doc, indent=1, sort_keys=True) + "\n"
    return out


def check_snapshots(snap_dir: Path, want: dict[str, str]) -> list[str]:
    """Committed snapshot files vs the generator: byte drift, missing, stale."""
    have = {p.name for p in snap_dir.glob("*.json")} if snap_dir.is_dir() else set()
    fails = [f"snapshot {n} differs from the generator (regenerate with --write, "
             f"deliberately; a gate never rewrites)"
             for n in sorted(want) if n not in have or
             (snap_dir / n).read_text(encoding="utf-8") != want[n]]
    fails += [f"snapshot {n} has no layout x theme (stale file)"
              for n in sorted(have - set(want))]
    return fails


def grdp_ids(grdp_text: str) -> set[str]:
    return set(re.findall(r'xr-id="([^"]+)"', grdp_text))


def templates(templates_cc: str) -> dict[str, dict]:
    rows = re.findall(r't\.push_back\(\{"([a-z]+)", "([^"]+)", "(#[0-9a-fA-F]{6})", "([^"]+)"',
                      templates_cc)
    return {r[0]: {"name": r[1], "color": r[2].lower(), "glyph": r[3]} for r in rows}


def laws(table: dict, themes: dict, ids: set[str], tmpl: dict[str, dict]) -> list[str]:
    fails: list[str] = []
    states = table.get("states", {})
    if not states:
        return ["states.json declares no states (zero-case law)"]
    seen_classes: set[str] = set()
    for sid, st in sorted(states.items()):
        for k in REQUIRED_STATE_KEYS:
            if k not in st or (k != "window_border" and not st[k]):
                fails.append(f"state {sid}: no {k}")
        cls = st.get("class", "")
        if cls and (not cls.startswith("xr-idc--") or cls in seen_classes):
            fails.append(f"state {sid}: class {cls!r} must be unique and start xr-idc--")
        seen_classes.add(cls)
        for k in ("accessible_name", "sr", "route"):
            if st.get(k) and st[k] not in ids:
                fails.append(f"state {sid}: {k} message {st[k]!r} is not in xr_strings.grdp")
        if not any(s.get("state") == sid for s in table.get("samples", [])):
            fails.append(f"state {sid}: no sample renders it (every state gets a case)")
    for s in table.get("samples", []):
        if s.get("state") not in states:
            fails.append(f"sample {s.get('template')}: unknown state {s.get('state')!r}")
            continue
        t = tmpl.get(s["template"])
        if t is None:
            fails.append(f"sample {s['template']}: not a template in identity/core/templates.cc")
        elif (s["name"], s["color"].lower(), s["glyph"]) != (t["name"], t["color"], t["glyph"]):
            fails.append(f"sample {s['template']}: drifted from templates.cc "
                         f"({s['name']}/{s['color']}/{s['glyph']} vs "
                         f"{t['name']}/{t['color']}/{t['glyph']})")
    if fails:
        return fails
    mins = table["contrast_min"]
    for theme_id, theme in sorted(themes.items()):
        for s in table["samples"]:
            node = structure(table, theme, s, next(iter(sorted(table["layouts"]))))
            where = f"{theme_id}/{s['template']}"
            c = node["contrast"]
            if c["pill_text"] < mins["text"]:
                fails.append(f"{where}: pill text contrast {c['pill_text']} < {mins['text']}")
            for part in ("mark", "window_border"):
                ratio = c[part]
                if ratio is None:
                    continue
                edge = (node["tab"]["children"][0] if part == "mark"
                        else node["window_border"])["edge"]
                if ratio < mins["non_text"] and (edge is None or edge["ratio"] < mins["non_text"]):
                    fails.append(f"{where}: {part} contrast {ratio} < {mins['non_text']} "
                                 f"and no edge that reaches it")
    return fails


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default=None)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="the gate (default)")
    mode.add_argument("--write", action="store_true", help="deliberate regeneration")
    args = ap.parse_args(argv)
    if args.write:
        core = Path(args.xr_core or REPO.parent / "xr-core").resolve()
    else:
        core = resolve_or_exit(REPO, override=args.xr_core, tool="identity_chrome_check").path
    table = json.loads((core / CHROME / "states.json").read_text(encoding="utf-8"))
    themes = json.loads((core / "ui" / "themes" / "tokens.json")
                        .read_text(encoding="utf-8"))["themes"]
    ids = grdp_ids((core / "l10n" / "xr_strings.grdp").read_text(encoding="utf-8"))
    tmpl = templates((core / "identity" / "core" / "templates.cc").read_text(encoding="utf-8"))
    fails = laws(table, themes, ids, tmpl)
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: identity_chrome_check ({len(fails)} law failure(s))")
        return EXIT_FAIL
    snap_dir = core / CHROME / "snapshots"
    want = snapshots(table, themes)
    if args.write:
        snap_dir.mkdir(parents=True, exist_ok=True)
        for old in snap_dir.glob("*.json"):
            if old.name not in want:
                old.unlink()
        for name, body in want.items():
            (snap_dir / name).write_text(body, encoding="utf-8")
        print(f"identity_chrome_check: wrote {len(want)} snapshot(s) to {snap_dir}")
        return EXIT_PASS
    drift = check_snapshots(snap_dir, want)
    for f in drift:
        print(f"FAIL: {f}")
    if drift:
        return EXIT_FAIL
    edges = sum(1 for body in want.values() for n in json.loads(body)["nodes"]
                if n["tab"]["children"][0]["edge"] is not None)
    print(f"PASS: identity_chrome_check ({len(table['states'])} states, "
          f"{len(table['samples'])} samples, {len(table['layouts'])} layouts x "
          f"{len(themes)} themes = {len(want)} snapshots; {edges} mark(s) carry a "
          f"text-token edge for contrast)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
