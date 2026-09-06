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
                            "xr_core_rev": "6fb5411bab4d95800a3e56848cecb3013f9bd33f",
                            "gclient_url_scheme": "https"})
    assert '"src/xr"' in g
    assert "xr-core.git@6fb5411bab4d95800a3e56848cecb3013f9bd33f" in g
    assert "chromium/src.git@d04cdb24d67b081f6cf80200ffc5233f44b61109" in g
