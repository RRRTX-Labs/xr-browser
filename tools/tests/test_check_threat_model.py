"""check_threat_model.py: structural gate for docs/threat-model.md v0."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]

PLAN_BODY = "# plan (synthetic)\n"


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "check_threat_model.py"), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
    )


def threat_model_body() -> str:
    return """# XR Browser — Threat model v0

- **Version:** v0 (test)
- **Bound to:** `XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md`
  (SHA-256 __SHA__)

**Update rule:** shipping a feature that changes the model without
updating the model is a blocked merge.

## How to read this document

placeholder

## Assets

| # | Asset | Why |
|---|---|---|
| A1 | credentials | existential |
| A2 | identity isolation | core promise |
| A3 | user data | local-first |

## Adversaries

| ID | Adversary class | XR posture | Does NOT protect against |
|---|---|---|---|
| T1 | trackers | block (P11) | shields-down sites |
| T2 | linkage | partition (P14) | unexercised vectors |
| T3 | malicious sites | inherited | zero-days |
| T4 | phishing | SB (P16) | brand-new URLs |
| T5 | extensions | Guard (P21) | declared-permission behavior |
| T6 | observers | DoH/Tor (P17/P31) | path operators |
| T7 | fingerprinters | reduction (P20) | determined operators |
| T8 | local malware | out of scope — stated | everything on a compromised host |
| T9 | state-level | out of scope — stated | state correlation |
| T10 | own channels | signed (P10) | signing-key compromise |
| T11 | supply chain | L9 + SBOM (P10) | vetted malicious upstream |

## Invariants

1. **Storage:** isolated. [Plan §1.12-1](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
2. **Processes:** no sharing. [Plan §1.12-2](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
3. **Vault:** no plaintext. [Plan §1.12-3](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
4. **License:** no copyleft linked. [Plan §1.12-4](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
5. **Route integrity:** bound egress. [Plan §1.12-5](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
6. **Ephemeral:** zero bytes. [Plan §1.12-6](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
7. **Accountability:** ledger rows. [Plan §1.12-7](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
8. **Upstream posture:** no weakening. [Plan §1.12-8](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
9. **Honesty:** no overclaim. [Plan §1.12-9](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
10. **Consent:** default-off. [Plan §1.12-10](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
11. **No intent claims:** observations only. [Plan §1.12-11](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
12. **AI boundary:** none. [Plan §1.12-12](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)

## Out of scope

- **T8 — local malware / compromised OS:** out of scope, stated.
- **T9 — state-level deanonymization:** out of scope, stated.
"""


@pytest.fixture()
def tm_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md").write_text(PLAN_BODY, encoding="utf-8")
    sha = hashlib.sha256(PLAN_BODY.encode()).hexdigest()
    (tmp_path / "docs/threat-model.md").write_text(
        threat_model_body().replace("__SHA__", sha), encoding="utf-8"
    )
    return tmp_path


def test_real_repo_passes() -> None:
    proc = run_tool("--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"
    assert data["assets"] >= 3
    assert len(data["adversaries_present"]) == 11
    assert data["invariants_linked"] >= 12


def test_valid_synthetic_passes(tm_repo: Path) -> None:
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_empty_honesty_cell_fails(tm_repo: Path) -> None:
    p = tm_repo / "docs/threat-model.md"
    p.write_text(p.read_text().replace("| unexercised vectors |", "| — |"), encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 1
    assert "T2" in proc.stdout and "Does NOT protect against" in proc.stdout


def test_missing_adversary_row_fails(tm_repo: Path) -> None:
    p = tm_repo / "docs/threat-model.md"
    p.write_text(p.read_text().replace("| T11 | supply chain | L9 + SBOM (P10) | vetted malicious upstream |\n", ""), encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 1
    assert "T11: row missing" in proc.stdout


def test_wrong_plan_sha_fails(tm_repo: Path) -> None:
    p = tm_repo / "docs/threat-model.md"
    p.write_text(p.read_text().replace(hashlib.sha256(PLAN_BODY.encode()).hexdigest(), "0" * 64), encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 1
    assert "SHA-256" in proc.stdout


def test_out_of_scope_must_name_t8_t9(tm_repo: Path) -> None:
    p = tm_repo / "docs/threat-model.md"
    text = p.read_text()
    text = text.replace("- **T9 — state-level deanonymization:** out of scope, stated.\n", "")
    p.write_text(text, encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 1
    assert "T9" in proc.stdout


def test_too_few_invariants_fails(tm_repo: Path) -> None:
    p = tm_repo / "docs/threat-model.md"
    text = p.read_text()
    # drop invariant 12 (leaves 11 < 12)
    text = text.replace("12. **AI boundary:** none. [Plan §1.12-12](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)\n", "")
    p.write_text(text, encoding="utf-8")
    proc = run_tool("--repo", ".", cwd=tm_repo)
    assert proc.returncode == 1
    assert "Invariants" in proc.stdout
