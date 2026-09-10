"""tools/tests/test_p9_visual.py — P9-T6 visual diff engine (stdlib PNG)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from build.qa.visual import engine, pngcodec  # noqa: E402

TOOL = REPO / "tools" / "visual_diff.py"


def img(w: int, h: int, color: tuple[int, int, int]) -> pngcodec.Image:
    rgba = bytearray()
    for _ in range(w * h):
        rgba += bytes(color) + b"\xff"
    return pngcodec.Image(w, h, rgba)


def test_codec_roundtrip_rgba() -> None:
    im = img(8, 5, (10, 20, 30))
    back = pngcodec.decode(pngcodec.encode(im))
    assert (back.width, back.height) == (8, 5)
    assert bytes(back.rgba) == bytes(im.rgba)


def test_codec_writes_valid_signature_and_reads_grayscale() -> None:
    im = img(4, 4, (77, 77, 77))
    data = pngcodec.encode(im)
    assert data.startswith(pngcodec.SIGNATURE)
    assert b"IEND" in data
    back = pngcodec.decode(data)
    assert back.width == 4 and back.height == 4


def test_decode_rejects_garbage() -> None:
    with pytest.raises(pngcodec.PngError):
        pngcodec.decode(b"not a png")


def test_engine_identical_and_one_pixel() -> None:
    a, b = img(16, 16, (200, 30, 30)), img(16, 16, (200, 30, 30))
    assert engine.diff(a, b)["identical"]
    b.rgba[0] = 201
    rec = engine.diff(a, b)
    assert not rec["identical"] and rec["differing_pixels"] == 1
    assert rec["max_delta"] == 1


def test_engine_ignore_regions() -> None:
    a, b = img(8, 8, (0, 0, 0)), img(8, 8, (0, 0, 0))
    for i in range(4):
        b.rgba[i] = 255
    rec = engine.diff(a, b, ignore=[engine.Region(0, 0, 1, 1)])
    assert rec["identical"] and rec["ignored_pixels"] == 1


def test_engine_size_mismatch_is_maximal() -> None:
    rec = engine.diff(img(4, 4, (0, 0, 0)), img(8, 8, (0, 0, 0)))
    assert not rec["identical"] and rec["size_mismatch"]


def test_cli_self_test_passes() -> None:
    r = subprocess.run([sys.executable, str(TOOL), "--self-test"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_flags_different_pair(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(pngcodec.encode(img(8, 8, (1, 2, 3))))
    b = img(8, 8, (1, 2, 3))
    b.rgba[0] = 9
    (tmp_path / "b.png").write_bytes(pngcodec.encode(b))
    r = subprocess.run([sys.executable, str(TOOL), "--ref",
                        str(tmp_path / "a.png"), "--cand",
                        str(tmp_path / "b.png")], capture_output=True, text=True)
    assert r.returncode == 1
    assert "DIFFERENT" in r.stdout
