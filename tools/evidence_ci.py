#!/usr/bin/env python3
"""tools/evidence_ci.py — hosted-CI run resolution for evidence bundles (P10-T0-d).

Split out of tools/evidence_check.py by responsibility: the BUNDLE validator
stays in evidence_check.py; the ci-run VERIFIER (loading the fetch
chokepoint, resolving a run/job id against the public API, deciding
green/not-green/offline) lives here. Pure refactor — no behavior change;
P10's bundle is the second consumer and the 400-LOC law is absorbed by the
split, not by compressing comments.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

def _load_upstream_fetch() -> Any:
    """Lazy, collision-safe load of build/upstream/fetch.py (the chokepoint).

    fetch.py does a bare `from _common import ToolError, main_with_guard`; in
    a shared process (./scripts/build test) whichever `_common` landed in
    sys.modules first wins, and it may be tools/_common.py, which lacks
    main_with_guard (see ef6771f). Preload build/_common.py under that name
    for the duration of fetch.py's exec, then restore. The gate itself runs
    evidence_check as a subprocess (fresh interpreter), where this is a no-op.
    """
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    saved = sys.modules.get("_common")
    cspec = importlib.util.spec_from_file_location(
        "_common", root / "build" / "_common.py")
    cmod = importlib.util.module_from_spec(cspec)
    sys.modules["_common"] = cmod
    try:
        cspec.loader.exec_module(cmod)
        fspec = importlib.util.spec_from_file_location(
            "upstream_fetch", root / "build" / "upstream" / "fetch.py")
        fmod = importlib.util.module_from_spec(fspec)
        sys.modules["upstream_fetch"] = fmod
        fspec.loader.exec_module(fmod)
        return fmod
    finally:
        if saved is None:
            sys.modules.pop("_common", None)
        else:
            sys.modules["_common"] = saved


def _default_ci_resolver(run_id: int, job_id: int,
                         bundle_commits: set[str]) -> bool | str:
    """Resolve a hosted-CI run via the chokepoint (fetch.py).

    True = verified green; False = verified not-green (must FAIL the bundle);
    a str = SKIP reason (offline / chokepoint unavailable). Never fabricates
    an id: the ids come from the row, the verdict from the public API.
    """
    try:
        fetch = _load_upstream_fetch()
    except Exception as exc:  # import/layout trouble == cannot verify
        return f"offline (cannot load the fetch chokepoint): {exc}"
    try:
        res = fetch.resolve_ci_run(int(run_id), int(job_id))
    except fetch.CiRunNotFound as exc:
        return False  # a cited run that does not exist is a red, not a skip
    except Exception as exc:  # network/transient — fetch.py retried already
        return f"offline (api.github.com unreachable): {exc}"
    if res.get("conclusion") != "success":
        return False
    head = str(res.get("head_sha") or "")
    if head and bundle_commits and not any(
            head.startswith(c) or c.startswith(head) for c in bundle_commits):
        return False
    return True


# P11-T0-d rule (d): a VERIFIED row whose own text claims hosted execution
# must carry a machine-resolvable ci-run citation — either itself (source
# ci-run) or via an APPENDED correction row with "corrects": <row-id>.
# Append-only law: corrections add rows; they never edit history. This is
# the rule that makes a hand-flipped "hosted = green" claim impossible:
# P10-DOD-2 shipped BLOCKED ("no cargo in sandbox"), was flipped in place
# once the hosted runs went green, and until this rule nothing in the
# validator could resolve the hosted half of the claim.
HOSTED_CLAIM_RE = re.compile(
    r"\bhosted\b|\bGitHub Actions\b|\bon the runner\b", re.I)


def hosted_claim_findings(rows: list[dict], path) -> list[str]:
    corrected = {r.get("corrects") for r in rows
                 if r.get("source") == "ci-run" and r.get("corrects")}
    fails: list[str] = []
    for row in rows:
        if not str(row.get("status", "")).startswith("VERIFIED"):
            continue
        text = " ".join(
            str(x) for x in [row.get("dod", ""), row.get("notes", "")]
            + [str(e) for e in (row.get("evidence") or [])])
        m = HOSTED_CLAIM_RE.search(text)
        if not m:
            continue
        if row.get("source") == "ci-run" or row.get("id") in corrected:
            continue
        fails.append(
            f"{path}: row {row.get('id', '<no id>')} claims hosted "
            f"execution ({m.group(0)!r}) with source {row.get('source')!r} "
            "— a hosted claim needs a ci-run citation: source ci-run with "
            "ci_run/ci_job ids on the row itself, or an appended correction "
            f"row carrying them with a 'corrects' field naming "
            f"{row.get('id')!r} (P11-T0-d rule d)")
    return fails


# Tests monkeypatch this to exercise the content-mismatch paths offline.
CI_RESOLVER = _default_ci_resolver
