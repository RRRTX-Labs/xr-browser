"""The P13-P0-C phase-finality law, end to end through the CLI.

The brief's four negatives live in tools/negatives/p13_p0c.sh (shell, as the
gate runs them); these tests pin the same law where the rest of the suite
lives, plus the wiring that makes it non-vacuous: `evidence_check --strict`
must call it, and `--require-phase-final` must be able to force the in-flight
phase to declare itself final.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
HEAD_A = "a" * 40
HEAD_B = "b" * 40


def _bundle(root: Path, name: str, doc: dict, *, report: bool = True) -> Path:
    d = root / "evidence" / name
    (d / "logs").mkdir(parents=True, exist_ok=True)
    (d / "logs" / "local.txt").write_text("transcript\n", encoding="utf-8")
    doc = {"generated": "2026-09-29", "plan": "docs/plans/x.md", **doc}
    (d / "evidence.json").write_text(json.dumps(doc), encoding="utf-8")
    (d / "human-gates.md").write_text("x " * 40, encoding="utf-8")
    if report:
        (d / "report.md").write_text(
            "\n".join(f"## {i}. section" for i in range(1, 13)), encoding="utf-8")
    return d / "evidence.json"


def _row(status: str, rid: str = "X-1") -> dict:
    return {"id": rid, "dod": "planted", "status": status,
            "source": "local-run", "evidence": ["logs/local.txt"]}


def _tree(tmp_path: Path, phase: str = "P13") -> Path:
    (tmp_path / "docs" / "state").mkdir(parents=True)
    (tmp_path / "docs" / "state" / "phase-base.json").write_text(
        json.dumps({"phase": phase}), encoding="utf-8")
    return tmp_path


def _run(tool: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          capture_output=True, text=True)


def test_state_absent_means_final_and_silence_reddens(tmp_path: Path) -> None:
    """The measured vacuity: P12's bundle had no state and PASSED. It must not."""
    root = _tree(tmp_path)
    _bundle(root, "P12", {"phase": "P12", "dod_rows": [_row("BLOCKED-PENDING-T5")]})
    proc = _run("evidence_finality.py", "--repo", str(root))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PENDING is interim" in proc.stdout


def test_final_requires_report_head_and_claimed_workflows(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _bundle(root, "P12", {"phase": "P12", "state": "final",
                          "dod_rows": [_row("VERIFIED")]}, report=False)
    proc = _run("evidence_finality.py", "--repo", str(root))
    out = proc.stdout
    assert "report.md" in out and "phase_head" in out and "ci_claimed" in out, out


def test_interim_needs_the_tree_to_declare_the_phase_in_flight(tmp_path: Path) -> None:
    root = _tree(tmp_path, phase="P13")
    _bundle(root, "P13", {"phase": "P13", "state": "interim",
                          "dod_rows": [_row("BLOCKED-PENDING-T7")]})
    assert _run("evidence_finality.py", "--repo", str(root)).returncode == 0
    # the same bundle for a phase that is NOT in flight is illegal
    (root / "evidence" / "P12").mkdir()
    _bundle(root, "P12", {"phase": "P12", "state": "interim",
                          "dod_rows": [_row("BLOCKED-PENDING-T7")]})
    proc = _run("evidence_finality.py", "--repo", str(root))
    assert proc.returncode == 1 and "not the in-flight phase" in proc.stdout


def test_invented_state_is_rejected(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _bundle(root, "P12", {"phase": "P12", "state": "final-ish",
                          "dod_rows": [_row("VERIFIED")]})
    proc = _run("evidence_finality.py", "--repo", str(root))
    assert proc.returncode == 1 and "not 'interim' or 'final'" in proc.stdout


def test_append_only_correction_clears_a_pending_row(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    original = _row("BLOCKED-PENDING-T5", rid="DOD-7")
    fix = {**_row("VERIFIED", rid="DOD-7-corr"), "corrects": "DOD-7"}
    _bundle(root, "P12", {"phase": "P12", "state": "final", "phase_head": HEAD_A,
                          "ci_claimed": ["governance"],
                          "dod_rows": [original, fix]})
    proc = _run("evidence_finality.py", "--repo", str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "superseded by appended corrections" in proc.stderr


def test_require_phase_final_refuses_an_interim_closing_bundle(tmp_path: Path) -> None:
    """evidence_check --strict --require-phase-final on the in-flight phase."""
    root = _tree(tmp_path, phase="P13")
    _bundle(root, "P13", {"phase": "P13", "state": "interim",
                          "dod_rows": [_row("VERIFIED")],
                          "not_done_by_design": ["still shipping"]})
    base = ["--repo", str(root), "--strict", "--only", "P13", "--no-presence"]
    assert _run("evidence_check.py", *base).returncode == 0
    proc = _run("evidence_check.py", *base, "--require-phase-final")
    assert proc.returncode == 1 and "--require-phase-final is set" in proc.stdout


def test_evidence_check_strict_calls_the_finality_law(tmp_path: Path) -> None:
    """The law is wired in, not merely available (the brief's requirement)."""
    root = _tree(tmp_path, phase="P13")
    _bundle(root, "P12", {"phase": "P12", "dod_rows": [_row("BLOCKED-PENDING-T9")]})
    proc = _run("evidence_check.py", "--repo", str(root), "--strict",
                "--only", "P12", "--no-presence")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "final bundle carries *-PENDING-* sentinels" in proc.stdout


def test_prelaw_bundles_are_untouched(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _bundle(root, "P9", {"phase": "P9", "dod_rows": [_row("BLOCKED-PENDING-X")]},
            report=False)
    proc = _run("evidence_finality.py", "--repo", str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
