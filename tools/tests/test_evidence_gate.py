"""test_evidence_gate.py — T0: strict evidence-gate auto-covers new bundles.

The P6/P7 debt: run_checks.sh pinned `--strict --only P3,P4,P5`, so P6 (and any
later phase) silently fell off the strict gate. T0 makes strict mode
auto-discover every `P<n>` bundle newer than the P2 legacy exemption.

These tests are the canary (L8): they prove the gate FAILS on a deliberately
broken P6/P7 bundle and PASSES when healthy, and that P1/P2 stay exempt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import evidence_check


def _write_bundle(
    root: Path,
    phase: str,
    *,
    healthy: bool = True,
    qualified: bool = False,
) -> Path:
    """Create a minimal evidence bundle under root/<phase>/."""
    d = root / phase
    (d / "logs").mkdir(parents=True, exist_ok=True)
    (d / "human-gates.md").write_text(
        f"# {phase} human gates\n\nNo human gates; all work is mechanical.\n",
        encoding="utf-8",
    )
    if qualified:
        # P1/P2 style: a qualified status + a dangling citation. Deliberately
        # NOT strict-compliant — but P1/P2 are exempt, so this must not be
        # reported under --strict auto scope.
        (d / "evidence.json").write_text(
            json.dumps({
                "phase": phase,
                "generated": "2026-01-01",
                "plan": "docs/plans/plan.md",
                "dod_rows": [{
                    "id": "DOD-1", "dod": "x",
                    "status": "VERIFIED (mock; real sync needs a host)",
                    "evidence": ["nope-missing.txt"],
                }],
            }),
            encoding="utf-8",
        )
        return d

    cite = "logs/x.txt" if healthy else "logs/missing.txt"
    if healthy:
        (d / "logs" / "x.txt").write_text("ok\n", encoding="utf-8")
    (d / "evidence.json").write_text(
        json.dumps({
            "phase": phase,
            "generated": "2026-01-01",
            "plan": "docs/plans/plan.md",
            "verdict_vocabulary": ["VERIFIED", "HUMAN-GATED", "SIMULATED"],
            "dod_rows": [{
                "id": "DOD-1", "dod": "x", "status": "VERIFIED", "evidence": [cite],
            }],
        }),
        encoding="utf-8",
    )
    return d


def _run_main(monkeypatch, repo: Path, *extra: str) -> int:
    monkeypatch.setattr(sys, "argv",
                        ["evidence_check.py", "--repo", str(repo), *extra])
    return evidence_check.main()


def test_strict_default_phases_discovers_newer_than_p2(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    for name in ["P1", "P2", "P3", "P4", "P6", "P7", "P10", "notaphase", "draft"]:
        (root / name).mkdir(parents=True)
    assert evidence_check.strict_default_phases(root) == [
        "P3", "P4", "P6", "P7", "P10",
    ]


def test_broken_p6_bundle_fails_strict_auto(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "evidence"
    _write_bundle(root, "P1", qualified=True)   # exempt: bad but never checked
    _write_bundle(root, "P2", qualified=True)   # exempt
    _write_bundle(root, "P3", healthy=True)
    _write_bundle(root, "P6", healthy=False)    # broken: dangling citation
    _write_bundle(root, "P7", healthy=True)

    # The gate as run_checks.sh invokes it: --strict, no --only.
    assert _run_main(monkeypatch, tmp_path, "--strict", "--dir", str(root)) == 1

    # Exactly P6 fails, on the missing artifact; P3/P7 are clean.
    p6 = evidence_check.check_file(root / "P6" / "evidence.json", tmp_path, strict=True)
    assert p6 and any("missing.txt" in f for f in p6)
    assert evidence_check.check_file(root / "P3" / "evidence.json", tmp_path, strict=True) == []
    assert evidence_check.check_file(root / "P7" / "evidence.json", tmp_path, strict=True) == []


def test_broken_p7_bundle_fails_strict_auto(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "evidence"
    _write_bundle(root, "P1", qualified=True)
    _write_bundle(root, "P3", healthy=True)
    _write_bundle(root, "P7", healthy=False)
    assert _run_main(monkeypatch, tmp_path, "--strict", "--dir", str(root)) == 1


def test_strict_auto_passes_when_healthy(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "evidence"
    _write_bundle(root, "P1", qualified=True)
    _write_bundle(root, "P2", qualified=True)
    _write_bundle(root, "P3", healthy=True)
    _write_bundle(root, "P6", healthy=True)
    _write_bundle(root, "P7", healthy=True)
    assert _run_main(monkeypatch, tmp_path, "--strict", "--dir", str(root)) == 0


def test_explicit_only_still_overrides_auto(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "evidence"
    _write_bundle(root, "P3", healthy=True)
    _write_bundle(root, "P6", healthy=False)
    # --only narrows the set, so a healthy P3 passes even with P6 broken.
    assert _run_main(monkeypatch, tmp_path,
                     "--strict", "--only", "P3", "--dir", str(root)) == 0
