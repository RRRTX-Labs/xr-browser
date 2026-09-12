"""tools/tests/test_p11_t0d_evidence.py — the P11-T0-d strict tightening.

Rule (d): a VERIFIED hosted claim needs a ci-run citation (on the row or on
an appended "corrects" row). Rule (e): a BLOCKED row whose blocker tool is
proven present (ledger or sandbox) is stale. Ledger law: present claims cite
real runs; UNOBSERVED says why; comment-claims are refused. All offline.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import evidence_ci  # noqa: E402
import runner_caps  # noqa: E402

P = "evidence/PXX/evidence.json"


def row(rid, dod, status="VERIFIED", source="local-run", **kw):
    return {"id": rid, "dod": dod, "status": status, "source": source,
            "evidence": ["logs/x.txt"], **kw}


# ---- rule (d): hosted claims need ci-run citations -------------------------

def test_hosted_claim_uncited_fires():
    hits = evidence_ci.hosted_claim_findings(
        [row("F-1", "compiles byte-exact on the hosted runner")], P)
    assert len(hits) == 1 and "rule d" in hits[0]


def test_hosted_claim_satisfied_by_own_ci_run_source():
    r = row("F-1", "hosted green", source="ci-run", ci_run=1, ci_job=2)
    assert evidence_ci.hosted_claim_findings([r], P) == []


def test_hosted_claim_satisfied_by_appended_correction_row():
    rows = [row("F-1", "hosted green"),
            row("F-1-C1", "correction", source="ci-run", ci_run=1, ci_job=2,
                corrects="F-1")]
    assert evidence_ci.hosted_claim_findings(rows, P) == []


def test_hosted_claim_correction_from_a_non_ci_run_row_does_not_satisfy():
    rows = [row("F-1", "hosted green"),
            row("F-1-C1", "correction", source="local-run", corrects="F-1")]
    assert len(evidence_ci.hosted_claim_findings(rows, P)) == 1


def test_hosted_claim_ignores_open_rows():
    # a BLOCKED/HUMAN-GATED row may name the hosted farm freely — it is not
    # claiming the hosted thing was DONE
    assert evidence_ci.hosted_claim_findings(
        [row("F-1", "needs the hosted runner", status="BLOCKED-NET")],
        P) == []


def test_hosted_claim_regex_is_narrow():
    # 'farm runner' / 'isolation-matrix runner' are TOOL names, not hosted-CI
    # claims (P9 DOD-1/DOD-9 must not fire); 'on the runner' IS a claim
    for dod in ("isolation-matrix runner lands", "farm runner + gate"):
        assert evidence_ci.hosted_claim_findings([row("F", dod)], P) == []
    assert evidence_ci.hosted_claim_findings(
        [row("F", "542 passed on the runner")], P)
    assert evidence_ci.hosted_claim_findings(
        [row("F", "GitHub Actions run green")], P)


# ---- rule (e): stale BLOCKED rows ------------------------------------------

CAPS = {"capabilities": {
    "cargo": {"present": True, "version": "1.98.1",
              "proven_by": [{"ci_run": 1, "ci_job": 2, "date": "2026-09-11"}]},
    "go": {"present": "UNOBSERVED", "note": "never printed"},
}}


def _pin_no_local_tools(monkeypatch):
    """Hermeticity pin for rule (e)'s LOCAL arm (P11-T5).

    Hosted CI runners have cargo/go/make installed; the dev sandbox does
    not. Without this pin the fixture tests below measure whichever
    environment they happen to run in — the leak reddened the hosted
    governance lane at 9df51d1: 'no cargo in the sandbox' double-fired
    (ledger arm + `which cargo` local arm => 2 hits, assert wanted 1) and
    the UNOBSERVED-go test fired via `which go`. The local arm keeps its
    own explicit positive test below (test_stale_blocked_local_arm).
    """
    monkeypatch.setattr(runner_caps.shutil, "which", lambda _tool: None)


def test_stale_blocked_ledger_arm(monkeypatch):
    _pin_no_local_tools(monkeypatch)
    hits = runner_caps.stale_blocked_findings(
        [row("B-1", "Rust replay — no cargo in the sandbox",
             status="BLOCKED-NET")], CAPS, P)
    assert len(hits) == 1 and "STALE BLOCKED" in hits[0]


def test_stale_blocked_unobserved_tool_never_fires(monkeypatch):
    _pin_no_local_tools(monkeypatch)
    assert runner_caps.stale_blocked_findings(
        [row("B-2", "telemetry — no go in the sandbox",
             status="BLOCKED-NET")], CAPS, P) == []


def test_stale_blocked_ignores_verified_rows_and_other_reasons(monkeypatch):
    _pin_no_local_tools(monkeypatch)  # uniform hermeticity (defensive)
    assert runner_caps.stale_blocked_findings(
        [row("V-1", "hosted replay, no cargo needed anymore")], CAPS, P) == []
    assert runner_caps.stale_blocked_findings(
        [row("B-3", "needs the browser+VM farm", status="BLOCKED-NET")],
        CAPS, P) == []


def test_stale_blocked_local_arm():
    if not shutil.which("make"):
        import pytest
        pytest.skip("SKIP (tool absent: make) — local arm of rule (e)")
    hits = runner_caps.stale_blocked_findings(
        [row("B-4", "suite build — make missing on this host",
             status="BLOCKED-NET")], {"capabilities": {}}, P)
    assert any("local arm" in h for h in hits)


# ---- the ledger citation law -----------------------------------------------

def test_caps_laws():
    assert runner_caps.check_caps(CAPS, "t") == []
    assert runner_caps.check_caps({"capabilities": {}}, "t")  # zero-case
    uncited = {"capabilities": {"rustc": {"present": True,
                                          "version": "1.98.1"}}}
    assert any("proven_by" in f for f in runner_caps.check_caps(uncited, "t"))
    noteless = {"capabilities": {"go": {"present": "UNOBSERVED"}}}
    assert any("note" in f for f in runner_caps.check_caps(noteless, "t"))
    versioned = {"capabilities": {"go": {"present": "UNOBSERVED",
                                         "note": "x", "version": "1.2"}}}
    assert any("version" in f for f in runner_caps.check_caps(versioned, "t"))
    proof_no_ids = {"capabilities": {"c": {"present": True, "proven_by": [
        {"date": "2026-09-11"}]}}}
    assert any("neither" in f for f in runner_caps.check_caps(proof_no_ids,
                                                              "t"))
    log_proof = {"capabilities": {"pyyaml": {"present": False, "proven_by": [
        {"log": "evidence/x.txt", "date": "2026-09-11"}]}}}
    assert runner_caps.check_caps(log_proof, "t") == []


def test_the_shipped_ledger_passes_its_own_law():
    doc = runner_caps.load_caps(REPO)
    assert doc is not None, "docs/state/runner-capabilities.json must exist"
    assert runner_caps.check_caps(doc, "shipped") == []
    caps = doc["capabilities"]
    # the two headline laws of the ledger content itself
    assert caps["cargo"]["present"] is True and caps["cargo"]["proven_by"]
    assert caps["go"]["present"] == "UNOBSERVED"  # a comment is not a run
