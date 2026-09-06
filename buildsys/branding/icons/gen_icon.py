"""buildsys/branding/icons/gen_icon.py — generate the interim XR mark (own-work, CC0).

The mark is a real, minimal geometric "XR" monogram — NOT a placeholder gray
box. Status: interim marks pending HG-5 trademark filings; replacement is
HUMAN-GATED (HG-14) after trademark outcomes. Deterministic: the SVG embeds no
timestamp; rasterization (png/ico/icns at packaging sizes) needs a rasterizer
(rsvg-convert/inkscape) and honors SOURCE_DATE_EPOCH where relevant.
"""

from __future__ import annotations

import sys
from pathlib import Path

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="28" fill="#10141f"/>
  <g fill="none" stroke="#7dd3fc" stroke-width="14" stroke-linecap="round">
    <path d="M34 34 L64 64 L94 34"/>
    <path d="M94 34 L70 78 L58 94"/>
  </g>
  <g fill="none" stroke="#e0f2fe" stroke-width="14" stroke-linecap="round">
    <path d="M34 94 L64 64 L94 94"/>
    <path d="M64 64 L78 44 L92 56"/>
  </g>
</svg>
"""


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "xr-mark.svg"
    out.write_text(SVG, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
