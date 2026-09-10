"""P9-T0-b pseudo-locale tests: determinism, canaries, untranslatable, RTL."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
GRDP = REPO.parent / "xr-core" / "l10n" / "xr_strings.grdp"
ARTIFACT = REPO / "docs" / "qa" / "qyy" / "xr_strings.qyy.txt"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / "pseudo_locale.py"),
                           *args], capture_output=True, text=True)


def test_self_test_passes() -> None:
    r = _run("--self-test")
    assert r.returncode == 0, r.stdout + r.stderr


def test_render_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    for out in (a, b):
        r = _run("--in", str(GRDP), "--out", str(out), "--as-of", "2026-09-10")
        assert r.returncode == 0, r.stdout + r.stderr
    assert a.read_bytes() == b.read_bytes()


def test_committed_artifact_diff_clean() -> None:
    r = _run("--in", str(GRDP), "--out", str(ARTIFACT),
             "--as-of", "2026-09-10", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_untranslatable_tokens_verbatim() -> None:
    # every {TOKEN} program text in the source must survive verbatim in the
    # rendered artifact (untranslatable handling — never accented/expanded).
    import sys as _sys
    _sys.path.insert(0, str(TOOLS))
    import grdp_check  # noqa: F401
    import xml.etree.ElementTree as ET
    rendered = {}
    for line in ARTIFACT.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rendered[parts[0]] = parts[2]
    root = ET.parse(GRDP).getroot()
    checked = 0
    for m in root:
        if m.tag != "message":
            continue
        text, _phs, _exs = grdp_check.message_parts(m)
        xr_id = m.get("xr-id", "")
        for token in ("{" + ph.get("name", "") + "}" for ph in _phs):
            assert token in rendered.get(xr_id, ""), (
                f"{xr_id}: token {token} lost in render")
            checked += 1
    assert checked > 0, "no ph tokens found — fixture ineffective"


def test_fixed_width_break_detected(tmp_path: Path) -> None:
    r = _run("--in", str(GRDP), "--fixed-width", "30")
    assert r.returncode == 1
    assert "fixed-width" in r.stdout


def test_rtl_render_has_markers(tmp_path: Path) -> None:
    out = tmp_path / "rtl.txt"
    r = _run("--in", str(GRDP), "--out", str(out), "--dir", "rtl")
    assert r.returncode == 0, r.stdout + r.stderr
    text = out.read_text(encoding="utf-8")
    assert "\u202e" in text and "\u202c" in text and "\u200f" in text


def test_meta_reports_counts() -> None:
    meta = json.loads(ARTIFACT.with_suffix(".meta.json").read_text())
    assert meta["message_count"] >= 59
    assert meta["expansion_ratio"] >= 1.0
