"""Update-manifest profile conformance to Omaha protocol 3.1.

Offline field-set extracted from the fetched spec at pin d04cdb24, cited by
file:line in docs/contracts/update-manifest-31-json.md:
  response object       protocol_3_1.md:546-557
  app (response)        protocol_3_1.md:609-640
  updatecheck status    protocol_3_1.md:658-692
  manifest              protocol_3_1.md:693-705
  package               protocol_3_1.md:714-735
  url (codebase)        protocol_3_1.md:747-757
Client ACCEPTANCE of concrete bytes is PENDING-VERIFY-farm (P10).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CORE = REPO.parent / "xr-core"
EXAMPLE = CORE / "fakes/fixtures/update-manifest-example.json"

# The 3.1 response subset our profile serves (spec-mandated members).
REQUIRED_UPDATECHECK_STATUS = {"ok", "noupdate", "error-internal", "error-hash",
                               "error-osnotsupported", "error-hwnotsupported",
                               "error-unsupportedprotocol"}


def test_example_validates_against_schema():
    r = subprocess.run([sys.executable, str(REPO / "tools/xr_schema.py"),
                        "validate", "update-manifest", str(EXAMPLE)],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_example_conforms_to_3_1_shape():
    doc = json.loads(EXAMPLE.read_text())
    resp = doc["response"]
    assert resp["protocol"] == "3.1"          # :546-557
    app = resp["app"][0]
    assert "appid" in app                       # :609-640
    uc = app["updatecheck"]
    assert uc["status"] in REQUIRED_UPDATECHECK_STATUS  # :658-692
    if uc["status"] == "ok":
        assert "version" in uc["manifest"]      # :693-705
        pkg = uc["manifest"]["packages"]["package"][0]
        for member in ("name", "size", "hash_sha256"):
            assert member in pkg                 # :714-735
        url = uc["urls"]["url"][0]
        assert ("codebase" in url) ^ ("codebasediff" in url)  # :747-757
