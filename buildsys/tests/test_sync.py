from pathlib import Path

import pytest

from _common import ToolError
from sync import synthesize_gclient


def test_synthesize_requires_40char_shas():
    with pytest.raises(ToolError, match="40-char"):
        synthesize_gclient({"chromium_rev": "short", "xr_core_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109",
                            "gclient_url_scheme": "https"})
    with pytest.raises(ToolError, match="40-char"):
        synthesize_gclient({"chromium_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109", "xr_core_rev": "x",
                            "gclient_url_scheme": "https"})


def test_synthesize_https_only():
    with pytest.raises(ToolError, match="https"):
        synthesize_gclient({"chromium_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109",
                            "xr_core_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109",
                            "gclient_url_scheme": "ssh"})


def test_synthesize_mounts_xr_at_src_xr():
    g = synthesize_gclient({"chromium_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109",
                            "xr_core_rev": "6416bf16a47f53b616d38b8cc6172633c5f3c8b9",
                            "gclient_url_scheme": "https"})
    assert '"src/xr"' in g
    assert "xr-core.git@6416bf16a47f53b616d38b8cc6172633c5f3c8b9" in g
    assert "chromium/src.git@d04cdb24d67b081f6cf80200ffc5233f44b61109" in g
