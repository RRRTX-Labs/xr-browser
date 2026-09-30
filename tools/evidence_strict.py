#!/usr/bin/env python3
"""tools/evidence_strict.py — the phase-head strict laws, split out of
evidence_check.py (P13-P0-C).

evidence_check.py sat AT the 380-line touched-file law, so P0-C's finality
work could not add a line to it (the law's own rule: split first, never
compress). This module receives the T12 block VERBATIM — no behavior change —
so evidence_check.py keeps the bundle validator and the row-level checks, and
the phase-head laws (T0-U2 head coverage, the PENDING explainer, the ci-run /
local-run citation rules, the hosted-claim rule, the stale-BLOCKED rule) live
here where the next phase's additions have room.

The ci-run resolver is passed IN (not imported) on purpose: tools/tests/
test_evidence_gate.py monkeypatches `evidence_check.CI_RESOLVER`, and a call
site that reads that module global at call time keeps the monkeypatch working
exactly as before the split.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

# noqa: E402 — sibling tool modules, same convention as evidence_check.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_caps  # noqa: E402
from evidence_ci import head_coverage_findings, hosted_claim_findings  # noqa: E402

T12_MIN_PHASE = 9
CI_RUN_LABEL = "ci-run"
_COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_OPEN_STATUS_PREFIXES = ("PARTIAL", "BLOCKED", "HUMAN-GATED")
PATHISH_RE = re.compile(r"^(?:\.\./)?(?:docs|tools|build|evidence|scripts|release|"
                        r"xr-core|ui)/\S+$|^\S+\.(?:md|json|sh|py|txt|ya?ml)$")


def is_open_status(status: str) -> bool:
    """PARTIAL / BLOCKED* / HUMAN-GATED — work shipped but not as done."""
    return status.strip().upper().startswith(_OPEN_STATUS_PREFIXES)


def bundle_commits(doc: dict[str, Any]) -> set[str]:
    """Commit shas the bundle records (pin + repos block), for ci-run head
    matching. A ci-run row is green only if its head_sha is one of these."""
    commits: set[str] = set()
    for key in ("pin",):
        if isinstance(doc.get(key), str):
            commits.update(_COMMIT_RE.findall(doc[key]))
    repos = doc.get("repos")
    if isinstance(repos, dict):
        for value in repos.values():
            texts = value if isinstance(value, list) else [value]
            for t in texts:
                if isinstance(t, str):
                    commits.update(_COMMIT_RE.findall(t))
    return commits


def strict_phase_findings(doc: dict[str, Any], rows: list[dict[str, Any]],
                          path: Path, repo: Path, *, phase_num: int | None,
                          resolver: Callable[[int, int, set[str]], Any],
                          warn: Callable[[str], None] | None = None
                          ) -> list[str]:
    """The T12 strict laws for one bundle; [] == pass.

    `resolver` is evidence_check.CI_RESOLVER at call time (see module docstring
    — the test suite monkeypatches it there). `warn` receives the SKIP notes
    that used to go straight to stderr.
    """
    warn = warn or (lambda msg: print(msg, file=sys.stderr))
    fails: list[str] = []
    if phase_num is None or phase_num < T12_MIN_PHASE:
        return fails

    # T0-U2: phase_head bundles cite a same-head ci-run row per workflow —
    # for FINAL bundles. A bundle that declares `interim` has made no final-CI
    # claim to match, so the rule does not bind it: `phase_head`/`ci_claimed`
    # are then the phase's INTENT, recorded in advance so the closing commit has
    # something to satisfy (P13-C-P0.4). Binding it here would make the brief's
    # "declare interim with a reasoned date" answer impossible to take.
    if str(doc.get("state", "final")).strip().lower() != "interim":
        fails.extend(head_coverage_findings(doc, rows, path))
    # (b) a PARTIAL/BLOCKED/HUMAN-GATED row must be explained: the bundle
    # carries a non-empty not_done_by_design (P8 shipped [] with partial
    # work — that hole closes here).
    if any(is_open_status(str(r.get("status", ""))) for r in rows):
        ndbd = doc.get("not_done_by_design")
        if not isinstance(ndbd, list) or not ndbd:
            fails.append(f"{path}: a PARTIAL/BLOCKED/HUMAN-GATED row "
                         f"requires a non-empty not_done_by_design list "
                         f"(P9-T12)")
    # (a) ci-run rows: ids required; --strict resolves them machine-side.
    bundle_commits_ = bundle_commits(doc)
    for row in rows:
        if row.get("source") != CI_RUN_LABEL:
            continue
        rid = row.get("id", "<no id>")
        run_id, job_id = row.get("ci_run"), row.get("ci_job")
        if not run_id or not job_id:
            fails.append(f"{path}: ci-run row {rid} must carry ci_run "
                         f"and ci_job ids (P9-T12)")
            continue
        verdict = resolver(int(run_id), int(job_id), bundle_commits_)
        if verdict is True:
            continue
        if verdict is False:
            fails.append(f"{path}: ci-run row {rid} run {run_id}/"
                         f"{job_id} is not certifiably green (P9-T12)")
        else:
            warn(f"SKIP: ci-run verification for {rid}: {verdict}")
    # (c) a local-run row must name its logs/* transcript.
    for row in rows:
        if row.get("source") != "local-run":
            continue
        rid = row.get("id", "<no id>")
        cites = [str(e).strip() for e in (row.get("evidence") or [])
                 if isinstance(e, str) and PATHISH_RE.match(str(e).strip())]
        if not any(c.startswith("logs/") for c in cites):
            fails.append(f"{path}: local-run row {rid} must cite a "
                         f"logs/* transcript (P9-T12)")
    # (d) P11-T0-d: a VERIFIED hosted claim needs a ci-run citation —
    # on the row itself or on an appended correction row ("corrects").
    fails.extend(hosted_claim_findings(rows, path))
    # (e) P11-T0-d: a BLOCKED-* row whose blocker tool the capabilities
    # ledger (hosted, run-cited) or this sandbox proves PRESENT is stale.
    caps = runner_caps.load_caps(repo)
    if caps is None:
        warn(f"SKIP: runner-capabilities ledger absent at "
             f"{repo / runner_caps.CAPS_RELPATH} — rule (e) "
             f"(stale-BLOCKED) inert for this run; visible, never silent")
    else:
        fails.extend(runner_caps.stale_blocked_findings(rows, caps, path))
    return fails
