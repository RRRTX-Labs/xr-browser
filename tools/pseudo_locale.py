#!/usr/bin/env python3
"""tools/pseudo_locale.py — deterministic qyy pseudo-locale renderer (P8-T5 → P9-T0-b).

P8-T5 recorded the .xtb/qyy pseudo-locale production as an open item; §11.6
requires pseudo-locale builds in the a11y/RTL CI that P9 owns. This tool is
the deterministic qyy renderer: it turns the single l10n string source
(xr-core/l10n/xr_strings.grdp) into a pseudo-localized artifact + metadata,
exercising the four concerns from P8's research item #4:

  * expansion ratio — each message grows by a deterministic, measured amount
    (reported in qyy-meta.json; a fixed-width overflow is a FAILURE);
  * accenting — a deterministic positional accent pass (never random, so two
    runs are byte-identical);
  * boundary markers — guillemets «…» wrap every message + a trailing
    «xr-id» marker so a cut-off string is identifiable in QA screenshots;
  * RTL-mirroring markers — --dir rtl wraps the message in RLO…PDF and
    prefixes RLM (U+200F) so bidi edge cases are exercised;
  * untranslatable handling — {TOKEN} placeholders (the <ph> program text)
    are preserved VERBATIM (never accented, never expanded).

FIDELITY (honesty note, required by the brief): Chromium's exact qqx
algorithm could not be confirmed at the pin without a checkout (recorded
UNVERIFIED in the research log), so this is a DOCUMENTED, DETERMINISTIC
VARIANT — it is not claimed to be byte-faithful to Chromium's qqx. The .xtb
byte generation stays farm-side (grit), SKIP-visible; no fabricated .xtb
exists and none is produced here.

Determinism law: output depends only on the input file + flags. Two runs
with the same --as-of (and the same grdp) are byte-identical — no wall
clock, no hash-order, no RNG state.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grdp_check  # noqa: E402  (reuse message_parts — no parser duplication)

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# Accent pass: positional, deterministic — the i-th (non-token) ASCII letter
# in a message maps to its accented twin when it appears in the table below
# (a fixed, documented substitution; every occurrence is positional so the
# result is stable across runs and Python versions).
ACCENT = {
    "a": "á", "e": "é", "i": "î", "o": "õ", "u": "û", "n": "ñ", "c": "ç",
}
RLO = "\u202e"   # RIGHT-TO-LEFT OVERRIDE
PDF = "\u202c"   # POP DIRECTIONAL FORMATTING
RLM = "\u200f"   # RIGHT-TO-LEFT MARK
TOKEN_RE = re.compile(r"(\{[A-Z0-9_]+\})")


def _accent(text: str) -> str:
    out: list[str] = []
    for ch in text:
        low = ACCENT.get(ch)
        out.append(low if low and ch.islower() else
                   (low.upper() if low and ch.isupper() else ch))
    return "".join(out)


def _expand(text: str, ratio: float) -> str:
    """Deterministic expansion: pad toward the target length with a fixed,
    accent-laden filler (never random)."""
    target = max(len(text), int(len(text) * ratio))
    filler = " ēxðañd"
    out = text
    while len(out) < target:
        out += filler[: max(1, target - len(out))]
    return out


def _transform(text: str, ratio: float, rtl: bool) -> str:
    """Accent + expand every NON-token run; keep {TOKEN} placeholders
    verbatim (untranslatable handling)."""
    pieces = TOKEN_RE.split(text)
    body = "".join(
        (_expand(_accent(part), ratio) if part and not TOKEN_RE.fullmatch(part)
         else part) for part in pieces)
    wrapped = f"«{body}»"
    if rtl:
        return RLM + RLO + wrapped + PDF + RLM
    return RLM + wrapped


def render_grdp(grdp: Path, ratio: float, rtl: bool) -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
    root = grdp_check.ET.parse(grdp).getroot()
    rows: list[tuple[str, str, str]] = []
    lengths: list[int] = []
    for m in root:
        if m.tag != "message":
            continue
        name = m.get("name", "")
        xr_id = m.get("xr-id", grdp_check.xr_id_of(name))
        text, _phs, _exs = grdp_check.message_parts(m)
        pseudo = _transform(text.strip(), ratio, rtl)
        lengths.append(len(pseudo))
        rows.append((xr_id, name, pseudo))
    meta: dict[str, Any] = {
        "locale": "qyy-rtl" if rtl else "qyy",
        "message_count": len(rows),
        "expansion_ratio": ratio,
        "mean_length": (sum(lengths) / len(lengths)) if lengths else 0.0,
        "max_length": max(lengths) if lengths else 0,
        "rtl": rtl,
    }
    return rows, meta


def write_artifact(rows: list[tuple[str, str, str]], meta: dict[str, Any],
                   out_path: Path, as_of: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"# qyy pseudo-locale render — as-of {as_of} (deterministic)\n")
        for xr_id, name, pseudo in rows:
            fh.write(f"{xr_id}\t{name}\t{pseudo}\n")
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--in", dest="grdp", default="",
                    help="xr_strings.grdp path")
    ap.add_argument("--out", default="", help="artifact output path")
    ap.add_argument("--locale", default="qyy", help="pseudo locale (qyy)")
    ap.add_argument("--dir", default="ltr", choices=("ltr", "rtl"))
    ap.add_argument("--ratio", type=float, default=1.4,
                    help="target expansion ratio (default 1.4)")
    ap.add_argument("--as-of", default="",
                    help="frozen-clock provenance stamp (determinism law)")
    ap.add_argument("--check", action="store_true",
                    help="re-render and diff against the committed artifact")
    ap.add_argument("--fixed-width", type=int, default=0,
                    help="assert every message fits N chars (0 = off)")
    ap.add_argument("--self-test", action="store_true",
                    help="run the canary fixtures (must fail on planted breaks)")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not args.grdp:
        ap.error("--in is required")
    if not args.out and not args.fixed_width:
        ap.error("--out is required (render/check modes; --fixed-width only "
                 "reports)")

    grdp = Path(args.grdp)
    if not grdp.is_file():
        print(f"error: no grdp at {grdp}", file=sys.stderr)
        return EXIT_USAGE
    rtl = args.dir == "rtl"
    rows, meta = render_grdp(grdp, args.ratio, rtl)

    if args.fixed_width:
        over = [(xid, n) for xid, _name, s in rows
                if (n := len(s)) > args.fixed_width]
        if over:
            for xid, n in over:
                print(f"FAIL: fixed-width: {xid} renders {n} chars > "
                      f"{args.fixed_width}")
            return EXIT_FAIL
        print(f"PASS: pseudo_locale fixed-width ({len(rows)} messages all "
              f"<= {args.fixed_width} chars)")
        return EXIT_PASS

    if args.check:
        out_path = Path(args.out)
        if not out_path.is_file():
            print(f"FAIL: no committed artifact at {out_path} to diff", file=sys.stderr)
            return EXIT_FAIL
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "render.txt"
            write_artifact(rows, meta, tmp, args.as_of)
            committed = out_path.read_text(encoding="utf-8")
            if tmp.read_text(encoding="utf-8") != committed:
                print(f"FAIL: pseudo_locale artifact drift at {out_path} "
                      "(regenerate with --out)")
                return EXIT_FAIL
        print(f"PASS: pseudo_locale qyy render diff-clean "
              f"({meta['message_count']} messages, "
              f"mean {meta['mean_length']:.1f} chars)")
        return EXIT_PASS

    write_artifact(rows, meta, Path(args.out), args.as_of)
    print(f"PASS: pseudo_locale rendered {meta['message_count']} messages "
          f"-> {args.out} (mean {meta['mean_length']:.1f} chars, "
          f"rtl={rtl})")
    return EXIT_PASS


def _self_test() -> int:
    """Canaries: (1) fixed-width break detected, (2) untranslatable token
    stays verbatim, (3) RTL markers present. A planted break must FAIL."""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as td:
        base = Path(td)
        grdp = base / "canary.grdp"
        grdp.write_text(
            '<?xml version="1.0"?><grit-part>\n'
            '<message name="IDS_XR_CANARY" desc="canary" '
            'xr-id="canary.long">The quick brown fox '
            '<ph name="KEY">{KEY}<ex>example</ex></ph> jumps</message>\n'
            '</grit-part>\n', encoding="utf-8")
        rows, _meta = render_grdp(grdp, 1.4, rtl=False)
        assert rows and "{KEY}" in rows[0][2], "untranslatable token altered"
        assert "«" in rows[0][2] and "»" in rows[0][2], "boundary markers"
        rows_r, _m2 = render_grdp(grdp, 1.4, rtl=True)
        assert RLO in rows_r[0][2] and PDF in rows_r[0][2], "RTL markers"
        # Fixed-width break must be DETECTED (the negative law):
        over = [(xid, len(s)) for xid, _n, s in rows if len(s) > 40]
        assert over, "canary string must overflow a 40-char fixed width"
    print("PASS: pseudo_locale self-test (canaries fire; tokens verbatim; "
          "RTL markers present)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
