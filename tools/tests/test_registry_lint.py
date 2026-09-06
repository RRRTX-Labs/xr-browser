"""registry_lint.py / gen_registry.py: plan → registry derivation + drift gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]

PIN = "a74b2aa4e8fd6f427c71cadfe932489249afe208a10413bf78c04734fd343e1b"

SYNTHETIC_PLAN = """# XR BROWSER — MASTER IMPLEMENTATION & EXECUTION PLAN (synthetic test copy)

# 2. CANONICAL FEATURE & SUBSYSTEM INVENTORY (THE FEATURE REGISTRY)

## 2.1 Test foundation

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Alpha feature | BUILD | A | P2 | P3–P5 | P0 | S0 | some risk | some proof |
| Beta feature | **DROP** | — | — | — | — | — | reason | — |
| Gamma deferred | DEFER | A | P39+ | P39+ | P2 | — | cost | gate |

## 2.2 Test shield

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Delta adapter | ADAPT (upstream) | B | — | P16 | P0 | S0 | inherit | upstream defaults asserted |

## 2.10 Explicitly-reserved interfaces (synthetic)

At the P5 contract freeze, the following ship as **typed interfaces + fakes + fixtures even though implementation lands later**: AlphaService (covers X) · BetaLedger (covers Y). A phase may not invent a parallel path around these; extending requires an approved contract-amendment RFC (L14; procedure ships with P5-T10).

# 3. DEPENDENCY GRAPH
(none)
"""


def run_tool(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / script), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def synth_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    plan = tmp_path / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
    plan.write_text(SYNTHETIC_PLAN, encoding="utf-8")
    pin = hashlib.sha256(SYNTHETIC_PLAN.encode()).hexdigest()
    (tmp_path / "docs/master-plan.sha256").write_text(pin + "\n", encoding="utf-8")
    return tmp_path


def test_write_then_check_passes(synth_repo: Path) -> None:
    proc = run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    feat = yaml.safe_load((synth_repo / "docs/registry/features.yaml").read_text())
    assert len(feat["features"]) == 4
    counts = json.loads((synth_repo / "docs/registry/COUNTS.json").read_text())
    assert counts["total_rows"] == 4
    assert counts["by_status"] == {"active": 2, "deferred": 1, "dropped": 1}
    reserved = yaml.safe_load((synth_repo / "docs/registry/reserved-interfaces.yaml").read_text())
    assert [i["id"] for i in reserved["interfaces"]] == ["alpha_service", "beta_ledger"]
    assert reserved["freeze_phase"] == "P5"
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = run_tool("registry_lint.py", "--repo", ".", "--json", cwd=synth_repo)
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["rows"] == 4
    assert data["reserved"] == 2


def test_field_tamper_fails(synth_repo: Path) -> None:
    run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    p = synth_repo / "docs/registry/features.yaml"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("Alpha feature", "Alpha feature (renamed)"), encoding="utf-8")
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "feature" in proc.stdout
    assert "F-001" in proc.stdout


def test_row_deletion_fails(synth_repo: Path) -> None:
    run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    feat = yaml.safe_load((synth_repo / "docs/registry/features.yaml").read_text())
    del feat["features"][1]
    (synth_repo / "docs/registry/features.yaml").write_text(
        yaml.safe_dump(feat, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "row count differs" in proc.stdout


def test_counts_tamper_fails(synth_repo: Path) -> None:
    run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    p = synth_repo / "docs/registry/COUNTS.json"
    counts = json.loads(p.read_text())
    counts["total_rows"] = 99
    p.write_text(json.dumps(counts), encoding="utf-8")
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "COUNTS.json" in proc.stdout and "total_rows" in proc.stdout


def test_reserved_tamper_fails(synth_repo: Path) -> None:
    run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    p = synth_repo / "docs/registry/reserved-interfaces.yaml"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("AlphaService", "GammaService"), encoding="utf-8")
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "reserved-interfaces.yaml" in proc.stdout


def test_missing_registry_fails(synth_repo: Path) -> None:
    (synth_repo / "docs/registry").mkdir()
    (synth_repo / "docs/registry/features.yaml").write_text("schema_version: 1\nfeatures: []\n", encoding="utf-8")
    (synth_repo / "docs/registry/reserved-interfaces.yaml").write_text(
        "schema_version: 1\ninterfaces: []\nfreeze_phase: P5\nrule: r\nplan_line: 1\n", encoding="utf-8"
    )
    (synth_repo / "docs/registry/COUNTS.json").write_text("{}", encoding="utf-8")
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "row count differs" in proc.stdout


def test_missing_pin_fails_closed(synth_repo: Path) -> None:
    run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    (synth_repo / "docs/master-plan.sha256").unlink()
    proc = run_tool("registry_lint.py", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "missing plan pin file" in (proc.stdout + proc.stderr)


def test_malformed_row_fails_parse(synth_repo: Path) -> None:
    plan = synth_repo / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
    text = plan.read_text(encoding="utf-8")
    # break a row's column count (merge two middle cells)
    text = text.replace("some risk | some proof", "some risk some proof")
    plan.write_text(text, encoding="utf-8")
    (synth_repo / "docs/master-plan.sha256").write_text(
        hashlib.sha256(text.encode()).hexdigest() + "\n", encoding="utf-8"
    )
    proc = run_tool("gen_registry.py", "--write", "--repo", ".", cwd=synth_repo)
    assert proc.returncode == 1
    assert "expected 9 columns" in (proc.stdout + proc.stderr)


def test_real_repo_registry_is_in_sync() -> None:
    proc = run_tool("registry_lint.py", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["rows"] == 122
    assert data["reserved"] == 6
    assert data["pin_verified"] is True
    counts = json.loads((REPO / "docs/registry/COUNTS.json").read_text())
    assert counts["plan_sha256"] == PIN
    assert counts["total_rows"] == 122
    assert counts["by_section"] == {
        "2.1": 7, "2.2": 14, "2.3": 15, "2.4": 13, "2.5": 16,
        "2.6": 10, "2.7": 19, "2.8": 14, "2.9": 14,
    }
    assert counts["by_status"] == {"active": 100, "deferred": 3, "dropped": 19}


def test_real_repo_gen_check_no_drift() -> None:
    proc = run_tool("gen_registry.py", "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
