"""build/qa/visual/pngcodec.py — minimal stdlib PNG codec (P9-T6, research #8).

A real PNG reader/writer in pure stdlib (zlib + struct), enough to drive the
snapshot comparison engine without new dependencies. Scope, stated plainly:

  * read: 8-bit grayscale (0), RGB (2), palette (3), gray+alpha (4), RGBA (6),
    filters 0–4, interlace 0 — expanded to RGBA8;
  * write: RGBA8 (color type 6, filter 0, zlib level 6);
  * not implemented (and why it doesn't matter here): 16-bit depth, interlace
    1, ancillary chunk validation (tEXt/gAMA are skipped, not trusted), and
    iCCP profile handling. Real Gold captures are 8-bit RGBA screenshots; if
    the farm ever feeds a 16-bit or interlaced capture, decode raises a clear
    error instead of guessing.

Deterministic: encode() is a pure function of the pixel array (no timestamps
in the emitted chunks).
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(Exception):
    """Malformed/unsupported PNG — fail loud, never guess."""


@dataclass
class Image:
    width: int
    height: int
    rgba: bytearray  # width*height*4 bytes, RGBA8


def _chunk(tag: bytes, data: bytes) -> bytes:
    c = tag + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))


def encode(img: Image) -> bytes:
    """Encode an RGBA8 image to PNG bytes (color type 6, filter 0)."""
    if img.width <= 0 or img.height <= 0:
        raise PngError(f"bad dimensions {img.width}x{img.height}")
    if len(img.rgba) != img.width * img.height * 4:
        raise PngError("rgba buffer length != width*height*4")
    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 6, 0, 0, 0)
    raw = bytearray()
    stride = img.width * 4
    for y in range(img.height):
        raw.append(0)  # filter none
        raw += img.rgba[y * stride:(y + 1) * stride]
    return SIGNATURE + _chunk(b"IHDR", ihdr) + \
        _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b"")


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(ftype: int, line: bytearray, prev: bytearray, bpp: int) -> bytearray:
    out = bytearray(line)
    if ftype == 0:
        return out
    if ftype == 1:  # Sub
        for i in range(bpp, len(out)):
            out[i] = (out[i] + out[i - bpp]) & 0xFF
    elif ftype == 2:  # Up
        for i in range(len(out)):
            out[i] = (out[i] + prev[i]) & 0xFF
    elif ftype == 3:  # Average
        for i in range(len(out)):
            left = out[i - bpp] if i >= bpp else 0
            out[i] = (out[i] + ((left + prev[i]) >> 1)) & 0xFF
    elif ftype == 4:  # Paeth
        for i in range(len(out)):
            left = out[i - bpp] if i >= bpp else 0
            up = prev[i]
            ul = prev[i - bpp] if i >= bpp else 0
            out[i] = (out[i] + _paeth(left, up, ul)) & 0xFF
    else:
        raise PngError(f"bad filter type {ftype}")
    return out


def decode(data: bytes) -> Image:
    """Decode PNG bytes to an RGBA8 Image."""
    if not data.startswith(SIGNATURE):
        raise PngError("not a PNG (bad signature)")
    pos = 8
    width = height = bitdepth = colortype = 0
    idat = bytearray()
    palette: list[tuple[int, int, int, int]] = []
    trns: list[int] = []
    ihdr_seen = False
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if pos + 12 + length > len(data):
            raise PngError("truncated chunk")
        if tag == b"IHDR":
            if ihdr_seen or length != 13:
                raise PngError("bad IHDR")
            ihdr_seen = True
            width, height, bitdepth, colortype, comp, filt, inter = \
                struct.unpack(">IIBBBBB", body)
            if comp != 0 or filt != 0 or inter != 0:
                raise PngError("unsupported compression/filter/interlace")
            if bitdepth != 8:
                raise PngError(f"unsupported bit depth {bitdepth} (8 only)")
        elif tag == b"IDAT":
            idat += body
        elif tag == b"PLTE":
            for i in range(0, length, 3):
                palette.append((body[i], body[i + 1], body[i + 2], 255))
        elif tag == b"tRNS":
            trns = list(body)
        elif tag == b"IEND":
            break
        pos += 12 + length
    if not ihdr_seen:
        raise PngError("no IHDR")
    if colortype not in (0, 2, 3, 4, 6):
        raise PngError(f"unsupported color type {colortype}")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colortype]
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise PngError(f"bad IDAT ({exc})") from exc
    stride = width * channels
    expect = height * (stride + 1)
    if len(raw) < expect:
        raise PngError("scanline data short")

    rgba = bytearray(width * height * 4)
    prev = bytearray(stride)
    off = 0
    for y in range(height):
        ftype = raw[off]
        off += 1
        line = bytearray(raw[off:off + stride])
        if len(line) != stride:
            raise PngError("scanline truncated")
        off += stride
        line = _unfilter(ftype, line, prev, channels)
        prev = line
        for x in range(width):
            p = y * width * 4 + x * 4
            if colortype == 0:
                g = line[x]
                rgba[p:p + 4] = bytes((g, g, g, 255))
            elif colortype == 2:
                rgba[p:p + 3] = line[x * 3:x * 3 + 3]
                rgba[p + 3] = 255
            elif colortype == 3:
                idx = line[x]
                if idx >= len(palette):
                    raise PngError("palette index out of range")
                r, g, b, a = palette[idx]
                if idx < len(trns):
                    a = trns[idx]
                rgba[p:p + 4] = bytes((r, g, b, a))
            elif colortype == 4:
                g = line[x * 2]
                a = line[x * 2 + 1]
                rgba[p:p + 4] = bytes((g, g, g, a))
            else:  # 6
                rgba[p:p + 4] = line[x * 4:x * 4 + 4]
    return Image(width, height, rgba)
