"""P8-T2 tokens_gen tests: generator self-negatives + --check diff-clean gate.

tokens_gen (xr-browser tools/tokens_gen.py) turns ONE JSON source
(xr-core/ui/themes/tokens.json) into tokens.h (uint32_t 0xAARRGGBB, no
SkColor) and tokens.css. These tests prove the validator bites:

  * 'critical-red' is RESERVED in data + validator: a theme mapping it to a
    non-alarming color is REFUSED (the alarming family check);
  * unknown token names / unknown meta fields / unknown theme keys are
    refused (strict);
  * duplicate keys are refused (never last-wins);
  * every theme must cover every declared token (no partial themes);
  * unsafe font strings (url()/code) are refused;
  * `tokens_gen.py --check` on the real repo is diff-clean (committed
    outputs == generated outputs) — the drift gate.

Stdlib + pytest. Skip-policy: --check needs the ../xr-core sibling repo;
the validator tests are pure (temp files), no skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
XR_CORE = REPO.parent / "xr-core"
GEN = TOOLS / "tokens_gen.py"
SRC = XR_CORE / "ui" / "themes" / "tokens.json"

VALID = json.loads(SRC.read_text(encoding="utf-8")) if SRC.is_file() else None


def _fixture(tmp_path: Path, **mut) -> Path:
    """Mini xr-core tree under tmp_path with the REAL tokens.json mutated.

    Returns the tree root (tokens.json lives at root/ui/themes/tokens.json).
    """
    import shutil
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    if "themes" in mut:
        doc["themes"] = mut["themes"]
    if "tokens" in mut:
        doc["tokens"] = mut["tokens"]
    if "extra" in mut:
        doc.update(mut["extra"])
    core = tmp_path / "core"
    (core / "ui" / "themes").mkdir(parents=True)
    shutil.copy(SRC.parent.parent / "tokens.css", core / "ui" / "tokens.css")
    (core / "ui" / "themes" / "tokens.json").write_text(
        json.dumps(doc), encoding="utf-8")
    return core


def _run_on(core: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GEN), "--xr-core", str(core)],
                          capture_output=True, text=True)


@pytest.mark.skipif(VALID is None or not SRC.is_file(),
                    reason="xr-core sibling missing — skip-policy (visible)")
def test_real_source_is_valid_and_check_diff_clean() -> None:
    # The committed outputs must equal what the generator produces today.
    r = subprocess.run([sys.executable, str(GEN), "--xr-core", str(XR_CORE),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "diff-clean" in r.stdout


def test_critical_red_reserved_law(tmp_path: Path) -> None:
    # critical-red mapped to a calm blue must be refused.
    themes = json.loads(json.dumps(VALID["themes"]))
    themes["light"] = dict(themes["light"])
    themes["light"]["critical-red"] = "#1565c0"  # blue = not alarming family
    p = _fixture(tmp_path, themes=themes)
    r = _run_on(p)
    assert r.returncode == 1
    assert "critical-red" in r.stdout and "alarming" in r.stdout


def test_critical_red_missing_rejected(tmp_path: Path) -> None:
    themes = json.loads(json.dumps(VALID["themes"]))
    themes["light"] = {k: v for k, v in themes["light"].items()
                       if k != "critical-red"}
    p = _fixture(tmp_path, themes=themes)
    r = _run_on(p)
    assert r.returncode == 1
    assert "missing value" in r.stdout


def test_unknown_token_rejected(tmp_path: Path) -> None:
    themes = json.loads(json.dumps(VALID["themes"]))
    themes["light"] = dict(themes["light"])
    themes["light"]["brand-new-token"] = "#123456"
    p = _fixture(tmp_path, themes=themes)
    r = _run_on(p)
    assert r.returncode == 1
    assert "unknown token" in r.stdout


def test_unknown_meta_field_rejected(tmp_path: Path) -> None:
    tokens = json.loads(json.dumps(VALID["tokens"]))
    tokens["surface"] = dict(tokens["surface"])
    tokens["surface"]["shiny"] = True
    p = _fixture(tmp_path, tokens=tokens)
    r = _run_on(p)
    assert r.returncode == 1
    assert "unknown meta field" in r.stdout


def test_duplicate_keys_rejected(tmp_path: Path) -> None:
    # A duplicated top-level token name must be REFUSED (never last-wins):
    # the object_pairs_hook refuses it before any validator runs.
    text = SRC.read_text(encoding="utf-8")
    doc = json.loads(text)
    name = next(iter(doc["tokens"]))
    dup = text[:text.index('"tokens": {') + len('"tokens": {') + 1] + \
        '"' + name + '": {"type": "color", "usage": "evil duplicate"},' + \
        text[text.index('"tokens": {') + len('"tokens": {') + 1:]
    import shutil
    core = tmp_path / "dup-core"
    (core / "ui" / "themes").mkdir(parents=True)
    shutil.copy(SRC.parent.parent / "tokens.css", core / "ui" / "tokens.css")
    (core / "ui" / "themes" / "tokens.json").write_text(dup, encoding="utf-8")
    r = subprocess.run([sys.executable, str(GEN), "--xr-core", str(core)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "duplicate key" in (r.stdout + r.stderr)


def test_unsafe_font_rejected(tmp_path: Path) -> None:
    themes = json.loads(json.dumps(VALID["themes"]))
    themes["light"] = dict(themes["light"])
    themes["light"]["font-family-ui"] = "url(https://evil.example/x.woff)"
    p = _fixture(tmp_path, themes=themes)
    r = _run_on(p)
    assert r.returncode == 1
    assert "unsafe font" in r.stdout


def test_partial_theme_rejected(tmp_path: Path) -> None:
    themes = json.loads(json.dumps(VALID["themes"]))
    themes["light"] = {"surface": "#ffffff"}  # far from full coverage
    p = _fixture(tmp_path, themes=themes)
    r = _run_on(p)
    assert r.returncode == 1
    assert "missing value" in r.stdout
