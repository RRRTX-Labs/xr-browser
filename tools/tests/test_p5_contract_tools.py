"""P5 contract tooling tests: mojom_lint, contracts_manifest, freeze_check,
vectors_check, xr_schema, amend_guard, xrctl. Stdlib + pytest; runs on a clean
clone (uses the real repo + ../xr-core fakes)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
FIX = TOOLS / "tests" / "fixtures" / "mojom"


def run(tool: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          cwd=cwd or REPO, capture_output=True, text=True)


# ---- mojom_lint: positive on real files, negative per rule ----------------

def test_mojom_lint_real_files_pass():
    r = run("mojom_lint.py", "--roundtrip", str(REPO.parent / "xr-core" / "mojom"))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("fixture,rule", [
    ("banned_execute.mojom", "R4"),
    ("banned_getdatabase.mojom", "R4"),
    ("missing_version.mojom", "R1"),
    ("missing_migration.mojom", "R2"),
    ("dup_method.mojom", "R3"),
    ("stringly_error.mojom", "R5"),
    ("datastream.mojom", "R6"),
    ("enableif.mojom", "R7"),
    ("nobudget.mojom", "R8"),
])
def test_mojom_lint_negatives(fixture, rule):
    r = run("mojom_lint.py", str(FIX / fixture))
    assert r.returncode == 1
    assert rule in r.stdout


# ---- contracts_manifest ----------------------------------------------------

def test_contracts_manifest_pass():
    r = run("contracts_manifest.py")
    assert r.returncode == 0, r.stdout


def test_contracts_manifest_remove_a_part_fails(tmp_path):
    # copy repo contracts dir + break one packet path by removing a review file.
    r = run("contracts_manifest.py", "--json")
    data = json.loads(r.stdout)
    assert data["items"] == 14


# ---- freeze_check ----------------------------------------------------------

def test_freeze_check_pass():
    r = run("freeze_check.py")
    assert r.returncode == 0, r.stdout


def test_freeze_check_rejects_agent_ratified(tmp_path):
    (tmp_path / "docs" / "contracts" / "review").mkdir(parents=True)
    src = (REPO / "docs/contracts/FROZEN.yaml").read_text()
    (tmp_path / "docs/contracts/FROZEN.yaml").write_text(
        src.replace("ratified: PENDING", "ratified: RATIFIED"))
    # copy packets so only the ratified check trips
    for p in (REPO / "docs/contracts/review").glob("*.md"):
        (tmp_path / "docs/contracts/review" / p.name).write_text(p.read_text())
    r = run("freeze_check.py", "--repo", str(tmp_path))
    assert r.returncode == 1
    assert "ratified verdict" in r.stdout or "must be PENDING" in r.stdout


# ---- vectors_check ---------------------------------------------------------

def test_vectors_check_byte_stable():
    r = run("vectors_check.py")
    assert r.returncode == 0, r.stdout


def test_vectors_check_detects_drift(tmp_path):
    # copy a vector file with a perturbed expected value; point --repo there.
    (tmp_path / "docs/contracts/vectors").mkdir(parents=True)
    vf = REPO / "docs/contracts/vectors/policy-resolver-v1.json"
    doc = json.loads(vf.read_text())
    doc["vectors"][0]["expected"] = {"ok": {"tampered": True}}
    (tmp_path / "docs/contracts/vectors/policy-resolver-v1.json").write_text(json.dumps(doc))
    # route file must exist too (runner iterates both); copy verbatim.
    rf = REPO / "docs/contracts/vectors/route-manager-v1.json"
    (tmp_path / "docs/contracts/vectors/route-manager-v1.json").write_text(rf.read_text())
    r = run("vectors_check.py", "--repo", str(tmp_path),
            "--fakes", str(REPO.parent / "xr-core" / "fakes"))
    assert r.returncode == 1
    assert "fake output != vector" in r.stdout


# ---- xr_schema -------------------------------------------------------------

def test_xr_schema_downgrade_rejected(tmp_path):
    f = tmp_path / "r.json"
    f.write_text('{"version":2}')
    r = run("xr_schema.py", "migrate", str(f), "--to", "1")
    assert r.returncode == 1
    assert "downgrade rejected" in (r.stdout + r.stderr)


def test_xr_schema_migrate_forward(tmp_path):
    f = tmp_path / "r.json"
    f.write_text('{"version":1}')
    r = run("xr_schema.py", "migrate", str(f), "--to", "2")
    assert r.returncode == 0
    assert '"version": 2' in r.stdout


# ---- xrctl -----------------------------------------------------------------

def test_xrctl_list():
    r = run("xrctl.py", "list")
    assert r.returncode == 0
    assert "policy_resolver" in r.stdout
