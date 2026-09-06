import json
from pathlib import Path

from emit_sbom import build_sbom
from sbom_gate import validate

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE.parent / "cyclonedx-schema-1.6.json").read_text())


def _sample():
    ver = {"full": "152.0.7977.82", "channel": "dev", "chromium_rev": "d04cdb24d67b081f6cf80200ffc5233f44b61109"}
    return build_sbom(ver, "xr_release.gn", ["//base:base", "//xr:xr_all"],
                      [{"name": "third_party/abseil-cpp", "has_license_file": True}], [])


def test_fixture_sbom_valid_per_schema():
    sbom = _sample()
    assert validate(sbom, SCHEMA) == []


def test_deterministic_serial():
    a, b = _sample(), _sample()
    assert a["serialNumber"] == b["serialNumber"]


def test_malformed_rejected():
    assert validate({"components": []}, SCHEMA) != []


def test_cargo_empty_tolerant(tmp_path):
    from emit_sbom import cargo_components
    assert cargo_components(None) == []
    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert cargo_components(empty) == []
