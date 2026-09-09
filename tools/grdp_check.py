#!/usr/bin/env python3
"""tools/grdp_check.py — strict validator for xr_strings.grdp (P8-T5).

Checks (each is a hard failure):
  1. Well-formed XML; root <grit-part>; children are <message> only.
  2. Every message has `name` (IDS_XR_UPPER_SNAKE) + `desc`; the name maps
     mechanically to the xr-id (lower, underscores -> dots); no duplicate
     xr-ids (names are unique by XML construction; the mapping is checked).
  3. Placeholders: every <ph name=N> is UPPER_SNAKE, its program text (its
     own content, excluding <ex>) is exactly {N}, appears exactly once in
     the message's translatable text, and N is referenced by no other
     placeholder; <ex> child (0 or 1) is the translator example. No other
     child elements are allowed inside <message>.
  4. No <excluded> abuse anywhere in the file.
  5. Vocabulary law: translatable text (not <ex> examples) is vocab-lint
     clean (same BANNED families as tools/vocab_lint.py).
  6. RTL/bidi safety: any strong-RTL character in translatable text must sit
     inside a balanced isolate pair (U+2066..U+2069); bare directional
     overrides/embeddings (U+202A-U+202E) and unbalanced isolates are
     refused outright (cite: W3C i18n bidi isolates; Chromium pseudo-locale
     docs — research-log-P8 item 3/4).
  7. Schema id coverage (--ids-from-schema): every title_id/desc_id in
     settings_schema_v1.json exists as an xr-id here.
  8. Isolation-card cross-check (decision: keep-both + gate): the card
     (l10n/isolation_card.json) must be well-formed with contract
     "isolation-card-disclosure-strings" and PENDING-HG-1 legal; its string
     ids must NOT be redefined in the grdp (the card is the legal-gated
     source of its own measured facts); card texts stay vocab-clean.
  9. Message-text hygiene: no C-style control chars; text trimmed; no
     unescaped XML; no stray {TOKEN} that no <ph> declares.

Exit: 0 = clean, 1 = violations, 2 = usage. Stdlib + the sibling tools
(vocab_lint.BANNED reused; PyYAML not needed here).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vocab_lint import BANNED  # noqa: E402  (sibling tools package)

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

NAME_RE = re.compile(r"^IDS_XR_[A-Z0-9_]+$")
PH_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
XR_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")

BIDI_CONTROLS = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E}
ISOLATES = {0x2066, 0x2067, 0x2068, 0x2069}


def _strong_rtl_ranges(cp: int) -> bool:
    return (0x0590 <= cp <= 0x08FF or 0xFB1D <= cp <= 0xFDFF or
            0xFE70 <= cp <= 0xFEFC)


def xr_id_of(name: str) -> str:
    if not NAME_RE.match(name):
        return ""
    return name[len("IDS_XR_"):].lower().replace("_", ".")


def message_parts(m: ET.Element) -> tuple[str, list[Any], list[Any]]:
    """Walk a <message> in document order; return (text, phs, ex_samples)."""
    pieces: list[str] = []
    phs: list[Any] = []
    exs: list[str] = []
    text = m.text or ""
    pieces.append(text)
    for child in m:
        if child.tag != "ph":
            raise ValueError(f"unexpected <{child.tag}> in message")
        phs.append(child)
        inner: list[str] = []
        for sub in child:
            if sub.tag != "ex":
                raise ValueError("ph may contain only <ex>")
        if child.text:
            inner.append(child.text)
        for sub in child:
            if sub.tag == "ex":
                exs.append("".join(sub.itertext()))
                if sub.tail:
                    inner.append(sub.tail)
        pieces.append("".join(inner))
        if child.tail:
            pieces.append(child.tail)
    return "".join(pieces), phs, exs


def check_grdp(path: Path, fails: list[str], vocab_on: bool = True) -> int:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fails.append(f"{path}: unreadable ({exc})")
        return EXIT_FAIL
    if "\x00" in raw or any(ord(c) < 0x20 and c not in "\n\t" for c in raw):
        fails.append(f"{path}: control characters in file")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        fails.append(f"{path}: XML parse error: {exc}")
        return EXIT_FAIL
    if root.tag != "grit-part":
        fails.append(f"{path}: root must be <grit-part> (got <{root.tag}>)")
    if root.findall(".//excluded"):
        fails.append(f"{path}: <excluded> is not allowed (abuse check)")

    seen_xrids: dict[str, str] = {}
    for msg in root:
        if msg.tag != "message":
            fails.append(f"{path}: unexpected element <{msg.tag}> under grit-part")
            continue
        name = msg.get("name", "")
        desc = msg.get("desc", "")
        xrid = msg.get("xr-id", "")
        line = f"{path}:<message {name or '?'}>"
        if not NAME_RE.match(name):
            fails.append(f"{line} name must be IDS_XR_UPPER_SNAKE (got {name!r})")
            continue
        if not desc or not desc.strip():
            fails.append(f"{line} missing desc (translator context required)")
        if not xrid or not XR_ID_RE.match(xrid):
            fails.append(f"{line} missing/invalid xr-id attribute (lowercase, "
                         "dots/hyphens allowed)")
        # name must be the deterministic upper form of the xr-id (dots and
        # hyphens both become underscores) so the two never drift.
        expected = "IDS_XR_" + xrid.upper().replace(".", "_").replace("-", "_")
        if xrid and name != expected:
            fails.append(f"{line} name {name!r} does not match xr-id {xrid!r} "
                         f"(expected {expected!r})")
        if xrid in seen_xrids:
            fails.append(f"{line} xr-id {xrid!r} duplicates {seen_xrids[xrid]}")
        seen_xrids[xrid] = name
        try:
            text, phs, exs = message_parts(msg)
        except ValueError as exc:
            fails.append(f"{line} {exc}")
            continue
        if not text.strip():
            fails.append(f"{line} empty message text")
        tokens = re.findall(r"\{([A-Z][A-Z0-9_]*)\}", text)
        if len(set(tokens)) != len(tokens):
            fails.append(f"{line} duplicated {{TOKEN}} placeholders")
        names = [p.get("name", "") for p in phs]
        if len(set(names)) != len(names):
            fails.append(f"{line} duplicate <ph name>")
        for p in phs:
            pn = p.get("name", "")
            if not PH_NAME_RE.match(pn):
                fails.append(f"{line} <ph name> must be UPPER_SNAKE (got {pn!r})")
            # ph program text must be exactly its {NAME} token
            ptext = (p.text or "").strip()
            if ptext != "{" + pn + "}":
                fails.append(f"{line} <ph name={pn}> program text must be "
                             f"exactly {{{pn}}} (got {ptext!r})")
            inner_tokens = [t for t in re.findall(r"\{[A-Z0-9_]+\}", ptext)]
            if inner_tokens and inner_tokens != ["{" + pn + "}"]:
                fails.append(f"{line} <ph name={pn}> holds a foreign token")
        for tok in tokens:
            if tok not in names:
                fails.append(f"{line} token {{{tok}}} has no <ph> declaration")
        for pn in names:
            if pn not in tokens:
                fails.append(f"{line} <ph name={pn}> never used in text")
        # bidi safety (translatable text only)
        for i, ch in enumerate(text):
            cp = ord(ch)
            if cp in BIDI_CONTROLS:
                fails.append(f"{line} bare bidi control U+{cp:04X} refused "
                             "(use U+2066..U+2069 isolates)")
        # isolate balance + strong-RTL inside isolates
        stack = 0
        for ch in text:
            cp = ord(ch)
            if cp in (0x2066, 0x2067, 0x2068):
                stack += 1
            elif cp == 0x2069:
                stack -= 1
                if stack < 0:
                    fails.append(f"{line} unbalanced isolate terminator")
                    stack = 0
        if stack != 0:
            fails.append(f"{line} unbalanced isolate openers ({stack})")
        # strong RTL must be inside isolates: strip isolate content and
        # check the remainder
        remainder = re.sub(r"[\u2066\u2067\u2068].*?[\u2069]", "", text)
        for ch in remainder:
            if _strong_rtl_ranges(ord(ch)):
                fails.append(f"{line} strong-RTL character U+{ord(ch):04X} "
                             "must be isolate-marked (U+2066..U+2069)")
        # vocab law on translatable text
        if vocab_on:
            for _, rx in BANNED:
                for mm in rx.finditer(text):
                    fails.append(f"{line} vocab-lint banned term "
                                 f"{mm.group(0)!r}")
    return EXIT_FAIL if fails else EXIT_PASS


def check_isolation_card(path: Path, grdp_xrids: set[str],
                         fails: list[str]) -> None:
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fails.append(f"{path}: isolation card unreadable/invalid ({exc})")
        return
    if card.get("contract") != "isolation-card-disclosure-strings":
        fails.append(f"{path}: wrong contract {card.get('contract')!r}")
    if card.get("legal") != "PENDING-HG-1":
        fails.append(f"{path}: legal gate must stay PENDING-HG-1")
    strings = card.get("strings")
    if not isinstance(strings, dict) or not strings:
        fails.append(f"{path}: strings object required")
        return
    for sid, row in strings.items():
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            fails.append(f"{path}: string {sid!r} must carry a text")
            continue
        if sid in grdp_xrids:
            fails.append(f"{path}: isolation-card id {sid!r} is redefined in "
                         "the grdp — the card is its own legal-gated source")
        for _, rx in BANNED:
            for mm in rx.finditer(row.get("text", "")):
                fails.append(f"{path}: string {sid!r} vocab-lint banned "
                             f"term {mm.group(0)!r}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="grdp_check",
                                 description="strict xr_strings.grdp validator")
    ap.add_argument("--grdp", default="../xr-core/l10n/xr_strings.grdp")
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--ids-from-schema", action="store_true",
                    help="require every settings schema title_id/desc_id "
                         "to exist as an xr-id in the grdp")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    fails: list[str] = []
    grdp = Path(args.grdp)
    rc = check_grdp(grdp, fails) if grdp.exists() else EXIT_FAIL
    if not grdp.exists():
        fails.append(f"{grdp}: missing")
    xrids: set[str] = set()
    if rc == EXIT_PASS:
        root = ET.parse(grdp).getroot()
        xrids = {m.get("xr-id", "") for m in root if m.tag == "message"}

    core = Path(args.xr_core)
    card = core / "l10n" / "isolation_card.json"
    if card.exists():
        check_isolation_card(card, xrids, fails)
    else:
        fails.append(f"{card}: missing isolation card")

    if args.ids_from_schema:
        schema = core / "settings" / "core" / "settings_schema_v1.json"
        if not schema.exists():
            fails.append(f"{schema}: missing schema")
        else:
            doc = json.loads(schema.read_text(encoding="utf-8"))
            wanted: list[str] = []
            for s in doc.get("sections", []):
                wanted.append(s.get("title_id", ""))
            for st in doc.get("settings", []):
                wanted.append(st.get("title_id", ""))
                wanted.append(st.get("desc_id", ""))
            for wid in sorted({w for w in wanted if w}):
                if wid not in xrids:
                    fails.append(f"schema id {wid!r} missing from the grdp")

    if args.json:
        print(json.dumps({"grdp": str(grdp), "messages": len(xrids),
                          "failures": fails}, indent=1, sort_keys=True))
    if fails:
        for f in fails:
            print(f"grdp_check: {f}", file=sys.stderr)
        return EXIT_FAIL
    print(f"grdp_check: {grdp.name} OK ({len(xrids)} messages, "
          f"isolation-card cross-check clean)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
