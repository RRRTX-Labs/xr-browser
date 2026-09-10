"""build/qa/visual/engine.py — snapshot diff engine (P9-T6, research #8).

The comparison half that is REAL here (the capture half is farm-side Gold).
Two RGBA8 images are compared pixel-by-pixel with a fixed-point sRGB delta
(max per-channel difference), a global threshold for AA tolerance, and
per-region ignore lists (AA-edges). Returns a machine-readable diff record:

  {"identical": bool, "differing_pixels": n, "max_delta": int,
   "mean_delta": float, "ignored_pixels": n}

The snapshot format (name, view, theme, locale, dir, identity-mark, hash,
size, provenance) is the metadata envelope the manifest carries; the engine
compares pixels, the manifest decides which pixels belong together.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from . import pngcodec


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int


@dataclass
class SnapshotMeta:
    name: str
    view: str = ""
    theme: str = ""
    locale: str = ""
    direction: str = "ltr"
    identity_mark: str = ""
    hash: str = ""
    size: tuple[int, int] = (0, 0)
    provenance: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "view": self.view, "theme": self.theme,
                "locale": self.locale, "direction": self.direction,
                "identity_mark": self.identity_mark, "hash": self.hash,
                "size": list(self.size), "provenance": self.provenance}


def sha256_png(png_bytes: bytes) -> str:
    return hashlib.sha256(png_bytes).hexdigest()


def in_region(x: int, y: int, regions: list[Region]) -> bool:
    return any(r.x <= x < r.x + r.w and r.y <= y < r.y + r.h
               for r in regions)


def diff(ref: pngcodec.Image, cand: pngcodec.Image, *,
         threshold: int = 0,
         ignore: list[Region] | None = None) -> dict[str, Any]:
    """Compare two RGBA8 images; returns the diff record (never raises on
    size mismatch — a size mismatch is itself a maximal difference)."""
    ignore = ignore or []
    if ref.width != cand.width or ref.height != cand.height:
        area = max(ref.width * ref.height, cand.width * cand.height, 1)
        return {"identical": False, "differing_pixels": area,
                "max_delta": 255, "mean_delta": 255.0,
                "ignored_pixels": 0, "size_mismatch": True}
    differing = 0
    ignored = 0
    total_delta = 0
    max_delta = 0
    n = ref.width * ref.height
    for i in range(n):
        x, y = i % ref.width, i // ref.width
        if in_region(x, y, ignore):
            ignored += 1
            continue
        dr = abs(ref.rgba[i * 4] - cand.rgba[i * 4])
        dg = abs(ref.rgba[i * 4 + 1] - cand.rgba[i * 4 + 1])
        db = abs(ref.rgba[i * 4 + 2] - cand.rgba[i * 4 + 2])
        da = abs(ref.rgba[i * 4 + 3] - cand.rgba[i * 4 + 3])
        d = max(dr, dg, db, da)
        if d > threshold:
            differing += 1
            total_delta += d
            max_delta = max(max_delta, d)
    compared = n - ignored
    return {"identical": differing == 0 and not _size_mismatch(ref, cand),
            "differing_pixels": differing,
            "max_delta": max_delta,
            "mean_delta": round(total_delta / compared, 4) if compared else 0.0,
            "ignored_pixels": ignored, "size_mismatch": False}


def _size_mismatch(ref: pngcodec.Image, cand: pngcodec.Image) -> bool:
    return ref.width != cand.width or ref.height != cand.height
