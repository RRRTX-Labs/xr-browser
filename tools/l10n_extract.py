#!/usr/bin/env python3
"""tools/l10n_extract.py — string-extraction lint (P8-T5).

L10n law: every user-visible string in the XR views is a message id from
xr-core/l10n/xr_strings.grdp; no raw user-visible string literals live in
ui/**/*.ts or in the xr payload .cc files (the plan's "every label
localizable from day one").

Scanned text surfaces (each is a hard failure):
  R1 html template TEXT NODES — literal text between tags/expressions that
     contains letters.
  R2 user-visible ATTRIBUTES — literal (non-${}) values of aria-label,
     aria-placeholder, placeholder, title, alt containing letters.
  R3 textContent/innerText assignments with string literals containing
     letters.
  R4 any quoted literal ('.ts' and payload '.cc') containing a SPACE plus
     at least one letter, outside the explicit code-token allowlist.

Code-domain tokens are never user-visible and are allowed: id-like strings
(^[a-z0-9][a-z0-9._-]*$), URLs (scheme://), true/false/null/undefined,
pure numbers, 'xr-*'/'lit/*'/'chrome://*' prefixes, and empty strings.
Single-word all-lowercase literals are NOT flagged (documented limitation:
they are code tokens; copy review covers the rest — see the tool header).

Cross-check (--grdp PATH, on by default): every message id referenced from
the scanned TS files as text(..)/_text(..) or via a strings['...']/['...']
literal must exist in the grdp's xr-id set.

Exit: 0 = clean, 1 = violations, 2 = usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

VISUAL_ATTRS = ("aria-label", "aria-placeholder", "placeholder", "title",
                "alt", "aria-description")

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://|^xr://|^chrome://|^data:")


def _collapsed(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _looks_visible(text: str) -> bool:
    """R4 classifier for a quoted literal's content."""
    if not re.search(r"[A-Za-z]", text):
        return False
    if " " not in text:
        return False
    if _ID_RE.match(text) or _URL_RE.match(text):
        return False
    if text.startswith(("xr-", "lit/", "chrome://")):
        return False
    return True


def _skip_string(src: str, i: int, q: str) -> int:
    j = i + 1
    n = len(src)
    while j < n:
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == q:
            return j + 1
        j += 1
    return n


def _strip_comments(src: str) -> str:
    """Remove // and /* */ comments, but never inside quoted strings
    (URLs like https:// carry // and must survive)."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            j = _skip_string(src, i, c)
            out.append(src[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n:
            if src[i + 1] == "/":
                nl = src.find("\n", i)
                if nl < 0:
                    break
                out.append("\n")
                i = nl + 1
                continue
            if src[i + 1] == "*":
                end = src.find("*/", i + 2)
                i = end + 2 if end >= 0 else n
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _extract_html(src: str) -> list[str]:
    """Bodies of every html`...` occurrence (balanced; tolerates nested
    backticks inside ${...}). Each occurrence is consumed independently, so
    nested html` inside an expression is itself scanned as a template."""
    bodies: list[str] = []
    n = len(src)
    for m in re.finditer(r"html`", src):
        j = m.start() + 5
        depth = 0
        while j < n:
            ch = src[j]
            if ch == "$" and j + 1 < n and src[j + 1] == "{":
                depth += 1
                j += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            elif ch == "`" and depth == 0:
                break
            j += 1
        bodies.append(src[m.start() + 5:j])
    return bodies


def _split_template(tpl: str) -> list[str]:
    """Split an html template body into text-node candidates.

    <tags> (attribute values may embed ${...}; quotes and braces balanced)
    and ${expressions} are consumed opaque; everything else is text.
    """
    texts: list[str] = []
    buf: list[str] = []
    i, n = 0, len(tpl)
    while i < n:
        c = tpl[i]
        if c == "<" and i + 1 < n and (tpl[i + 1].isalpha()
                                       or tpl[i + 1] in "/!?#"):
            j = i + 1
            quote = ""
            depth = 0
            while j < n:
                ch = tpl[j]
                if quote:
                    if ch == quote:
                        quote = ""
                elif ch in "\"'":
                    quote = ch
                elif ch == "$" and j + 1 < n and tpl[j + 1] == "{":
                    depth += 1
                    j += 1
                elif ch == "}":
                    if depth:
                        depth -= 1
                    else:
                        break
                elif ch == ">" and depth == 0:
                    break
                j += 1
            i = j + 1
            if buf:
                texts.append("".join(buf))
                buf = []
        elif c == "$" and i + 1 < n and tpl[i + 1] == "{":
            depth = 1
            j = i + 2
            while j < n and depth:
                if tpl[j] == "{":
                    depth += 1
                elif tpl[j] == "}":
                    depth -= 1
                j += 1
            i = j
            if buf:
                texts.append("".join(buf))
                buf = []
        else:
            buf.append(c)
            i += 1
    if buf:
        texts.append("".join(buf))
    return texts


def _quote_literals(code: str):
    """Yield (content, preceding_context) per quoted literal in code.

    Sequential scan so adjacent/empty literals cannot pair across code;
    backtick template spans (non-html) are skipped whole (their quotes are
    code, not user-visible).
    """
    n = len(code)
    i = 0
    while i < n:
        c = code[i]
        if c == "`":
            depth = 0
            j = i + 1
            while j < n:
                if code[j] == "$" and j + 1 < n and code[j + 1] == "{":
                    depth += 1
                    j += 1
                elif code[j] == "}":
                    depth = max(0, depth - 1)
                elif code[j] == "`" and depth == 0:
                    break
                j += 1
            i = j + 1
            continue
        if c in "\"'":
            q = c
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == q:
                    break
                j += 1
            yield code[i + 1:j], code[max(0, i - 80):i]
            i = j + 1
            continue
        i += 1


def _skip(path: Path) -> bool:
    return any(part in ("node_modules", "toolchain", ".venv", "build")
               for part in path.parts)


def _scan_ts(path: Path, findings: list[dict]) -> None:
    raw = path.read_text(encoding="utf-8")
    src = _strip_comments(raw)
    for tpl in _extract_html(src):
        for node in _split_template(tpl):
            node = _collapsed(node)
            if node and re.search(r"[A-Za-z]", node):
                findings.append({"rule": "R1", "file": str(path),
                                 "detail": f"raw text node: {node[:80]!r}"})
        for attr in VISUAL_ATTRS:
            for am in re.finditer(
                    attr + r'\s*=\s*(?:"([^"$]+)"|\'([^\'$]+)\')', tpl):
                val = _collapsed(am.group(1) or am.group(2) or "")
                if val and re.search(r"[A-Za-z]", val):
                    findings.append({"rule": "R2", "file": str(path),
                                     "detail": f"{attr}={val[:60]!r}"})
    code = src
    for tpl in _extract_html(src):
        code = code.replace("html`" + tpl + "`", "html``")
    for val, ctx in _quote_literals(code):
        if not re.search(r"[A-Za-z]", val):
            continue
        if re.search(r"(?:textContent|innerText)\s*(?:=|\+=)\s*['\"]?$",
                     ctx, flags=re.M) and "textContent|innerText" not in val:
            if re.search(r"textContent|innerText", ctx):
                findings.append({"rule": "R3", "file": str(path),
                                 "detail": f"textContent literal: "
                                           f"{_collapsed(val)[:60]!r}"})
        if _looks_visible(_collapsed(val)):
            findings.append({"rule": "R4", "file": str(path),
                             "detail": f"literal: {_collapsed(val)[:80]!r}"})


def _scan_cc(path: Path, findings: list[dict]) -> None:
    body = _strip_comments(path.read_text(encoding="utf-8"))
    for val, _ in _quote_literals(body):
        val = _collapsed(val)
        if _looks_visible(val):
            findings.append({"rule": "R4", "file": str(path),
                             "detail": f"literal: {val[:80]!r}"})


def _referenced_ts_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for ts in root.glob("ui/**/*.ts"):
        if _skip(ts):
            continue
        src = ts.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:text|_text)\(\s*(?:"
                             r"(?:this\.strings|[A-Za-z_$][\w$]*)\s*,)?"
                             r"\s*['\"]([a-z][a-z0-9._-]*)['\"]", src):
            ids.add(m.group(1))
        for m in re.finditer(r"strings\[['\"]([a-z][a-z0-9._-]*)['\"]\]", src):
            ids.add(m.group(1))
        # id literals passed to the local text()-alias helper t(...)
        for m in re.finditer(r"\bt\(\s*['\"]([a-z][a-z0-9._-]*)['\"]", src):
            ids.add(m.group(1))
    return ids


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="l10n_extract",
                                 description="raw user-visible string lint")
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--grdp", default="../xr-core/l10n/xr_strings.grdp")
    ap.add_argument("--check", action="store_true",
                    help="exit 0/1 (diff-clean style gate)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    core = Path(args.xr_core).resolve()
    findings: list[dict] = []
    files = 0
    for ts in sorted(core.glob("ui/**/*.ts")):
        if _skip(ts):
            continue
        files += 1
        _scan_ts(ts, findings)
    for cc in sorted(core.glob("patches/**/payload/**/*.cc")):
        if _skip(cc):
            continue
        files += 1
        _scan_cc(cc, findings)

    missing: list[str] = []
    grdp = Path(args.grdp).resolve()
    if grdp.exists():
        root = ET.parse(grdp).getroot()
        have = {m.get("xr-id") for m in root if m.tag == "message"}
        for ref in sorted(_referenced_ts_ids(core)):
            if ref not in have:
                missing.append(ref)
    else:
        missing.append(f"(grdp missing: {grdp})")

    if args.json:
        print(json.dumps({"files": files, "violations": findings,
                          "missing_ids": missing}, indent=1, sort_keys=True))
    for f in findings:
        print(f"l10n_extract: {f['rule']} {f['file']}: {f['detail']}",
              file=sys.stderr)
    for mid in missing:
        print(f"l10n_extract: referenced id {mid!r} missing from the grdp",
              file=sys.stderr)
    ok = not findings and not missing
    print(f"l10n_extract: {files} files, {len(findings)} raw-string "
          f"violations, {len(missing)} missing ids -> "
          f"{'CLEAN' if ok else 'FAIL'}")
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
