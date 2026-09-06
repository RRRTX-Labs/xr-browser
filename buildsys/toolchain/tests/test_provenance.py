import json
from pathlib import Path

from provenance import verify

HERE = Path(__file__).resolve().parent
PINS = HERE.parent / "pins.json"


def test_real_pins_verify_clean():
    pins = json.loads(PINS.read_text())
    assert verify(pins) == []


def test_bad_sha256_rejected():
    pins = json.loads(PINS.read_text())
    pins["sysroot"][0]["sha256"] = "not-a-sha"
    assert any("sha256" in f for f in verify(pins))


def test_missing_clang_version_rejected():
    pins = json.loads(PINS.read_text())
    del pins["clang"]["version"]
    assert any("clang.version" in f for f in verify(pins))
