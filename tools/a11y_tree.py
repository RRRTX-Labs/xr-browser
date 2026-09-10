#!/usr/bin/env python3
"""tools/a11y_tree.py — AXTree snapshot harness over the Lit templates (P9-T7).

The decision (recorded in docs/qa/a11y-contract.md): axe-core needs a real
DOM, and the only DOM shim (jsdom) is a SECOND package — not authorized. So
the in-sandbox a11y lane runs against an AXTree *snapshot* generated from the
Lit templates by the documented transform below; the browser-side axe run is
a farm row (HG-31, build/qa/a11y/axe_run.mjs).

The transform is a HEURISTIC, stated plainly: it extracts elements with an
interactive role / aria attributes / tabindex from the .ts templates and
records {role, name, focusable, order}. It is NOT a DOM; the real
Accessibility tree comes from the browser via CDP Accessibility.getFullAXTree
on the farm. What the transform catches is real and useful: a nameless
button, a combobox missing aria-activedescendant, a listbox without a name —
the exact structural failures the plan's §11.6 blocks on.

Invariants (each with a fixture proving it bites):
  1. every interactive node (button/combobox/textbox/link/option) has an
     accessible name (aria-label | label-for | aria-labelledby | text);
  2. a combobox carries aria-expanded + aria-controls + aria-activedescendant;
  3. a listbox carries a name.

--gen writes the committed golden (docs/qa/axtree-snapshot.json); --check
regenerates and diffs; --self-test plants a nameless button and proves the
checker turns red. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, stable_json  # noqa: E402

UI_DIR = "../xr-core/ui"
OUT = "docs/qa/axtree-snapshot.json"

NL = "\n"

ROLE_RE = re.compile(r'role="([a-z]+)"')
ARIA_LABEL_RE = re.compile(r'aria-label\s*=\s*(?:\$\{([^}]*)\}|"([^"]*)")')
ARIA_LABELLEDBY_RE = re.compile(r'aria-labelledby\s*=\s*(?:\$\{([^}]*)\}|"([^"]*)")')
TAG_RE = re.compile(r'<(\/)?(button|input|a|li|ul|label)\b')
LABEL_FOR_RE = re.compile(r'<label[^>]*for="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')
HAS_TEXT_RE = re.compile(r'(\$\{[^}]+\}|[A-Za-z][A-Za-z .-]{1,40})')

INTERACTIVE_ROLES = {"button", "combobox", "textbox", "link", "option"}
TAG_ROLES = {"input": "textbox", "button": "button", "a": "link"}


def extract_nodes(source: str, path: str) -> list[dict]:
    """Heuristic AXTree extraction from one Lit template file.

    Multiline Lit templates are the norm, so the transform is element-block
    based: a ``role="X"`` line takes its id/name from the surrounding lines;
    a bare ``<input``/``<button``/``<a`` whose element carries a role a few
    lines below is NOT double-counted.
    """
    ids_from_labels = {m for m in LABEL_FOR_RE.findall(source)}
    lines = source.splitlines()
    nodes: list[dict] = []
    order = 0
    for i, line in enumerate(lines):
        roles = ROLE_RE.findall(line)
        tagm = TAG_RE.search(line)
        if roles:
            role = roles[0]
        elif tagm and not tagm.group(1) and tagm.group(2) in TAG_ROLES:
            role = TAG_ROLES[tagm.group(2)]
            # opening tag of an element whose role= sits a few lines below:
            if 'role="' in NL.join(lines[i + 1:i + 4]):
                continue
        else:
            continue
        ctx = NL.join(lines[max(0, i - 3):i + 1])
        idm = ID_RE.search(line) or ID_RE.search(ctx)
        elid = idm.group(1) if idm else ""
        al = ARIA_LABEL_RE.search(line)
        alb = ARIA_LABELLEDBY_RE.search(line)
        name = None
        if al:
            name = al.group(1) or al.group(2)
        elif alb:
            name = f"labelledby:{alb.group(1) or alb.group(2)}"
        elif elid in ids_from_labels:
            name = f"label-for:{elid}"
        else:
            ahead = NL.join(lines[i + 1:i + 5])
            if "${" in ahead or HAS_TEXT_RE.search(ahead):
                name = "content"
        focusable = ("tabindex" in line or role in ("textbox", "button",
                                                    "link"))
        order += 1
        nodes.append({"role": role, "name": name, "focusable": focusable,
                      "order": order, "source": f"{path}:{i + 1}"})
    return nodes


def check_sources(root: Path) -> tuple[list[dict], list[str]]:
    nodes: list[dict] = []
    combobox_src: list[str] = []
    listbox_src: list[str] = []
    for f in sorted(root.rglob("*.ts")):
        if "node_modules" in f.parts or "build" in f.parts or \
                f.suffix == ".d.ts":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if 'role="combobox"' in text:
            combobox_src.append(str(f.relative_to(root)))
        if 'role="listbox"' in text:
            listbox_src.append(str(f.relative_to(root)))
        nodes.extend(extract_nodes(text, str(f.relative_to(root))))
    fails: list[str] = []
    if not nodes:
        return nodes, ["a11y_tree: zero AXTree nodes extracted "
                       "(empty-run law)"]
    for n in nodes:
        if n["role"] in INTERACTIVE_ROLES and not n["name"]:
            fails.append(f"{n['source']}: role={n['role']} has no accessible "
                         f"name (aria-label | label-for | aria-labelledby | "
                         f"text)")
    for rel in combobox_src:
        text = (root / rel).read_text(encoding="utf-8")
        for attr in ("aria-expanded", "aria-controls",
                     "aria-activedescendant"):
            if attr not in text:
                fails.append(f"{rel}: combobox missing {attr}")
    for rel in listbox_src:
        text = (root / rel).read_text(encoding="utf-8")
        if "aria-label" not in text and "aria-labelledby" not in text:
            fails.append(f"{rel}: listbox has no accessible name")
    return nodes, fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="a11y_tree", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--ui-dir", default=UI_DIR)
    p.add_argument("--out", default=OUT)
    p.add_argument("--gen", action="store_true", help="write the golden")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed snapshot drifted")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()

    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "good.ts").write_text(
                '<label for="b1">Go</label><button id="b1" '
                'role="button">Go</button>', encoding="utf-8")
            _n, fails = check_sources(d)
            ok_good = not any("no accessible name" in f for f in fails)
            (d / "bad.ts").write_text(
                '<button role="button"></button>', encoding="utf-8")
            _n2, fails2 = check_sources(d)
            caught = any("no accessible name" in f for f in fails2)
            if not (ok_good and caught):
                print(f"FAIL: a11y_tree self-test — good={ok_good} "
                      f"caught={caught}")
                return EXIT_FAIL
        print("PASS: a11y_tree self-test (labelled button clean; nameless "
              "button caught)")
        return EXIT_PASS

    root = Path(args.ui_dir)
    if not root.is_absolute():
        root = repo / root
    nodes, fails = check_sources(root)
    doc = {"schema_version": 1, "nodes": nodes}
    new = stable_json(doc) + NL

    out = Path(args.out)
    if not out.is_absolute():
        out = repo / out
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != new:
            print(f"FAIL: {out} drifted from the ui templates — regenerate "
                  f"with --gen")
            return EXIT_FAIL
        if fails:
            for f in fails:
                print(f"FAIL: {f}")
            return EXIT_FAIL
        print(f"PASS: a11y_tree --check ({len(nodes)} nodes, diff-clean)")
        return EXIT_PASS
    if args.gen:
        out.write_text(new, encoding="utf-8")
        print(f"wrote {out} ({len(nodes)} nodes)")
        if fails:
            for f in fails:
                print(f"FAIL: {f}")
            return EXIT_FAIL
        return EXIT_PASS
    for f in fails:
        print(f"FAIL: {f}")
    if args.json:
        print(json.dumps({"tool": "a11y_tree", "nodes": len(nodes),
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        print(f"a11y_tree: {len(nodes)} node(s), {len(fails)} violation(s) "
              f"({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
