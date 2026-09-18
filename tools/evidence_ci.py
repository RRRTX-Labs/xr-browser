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


# T0-U2: the final-CI claim must point at the bundle's OWN head. This is a
# STRUCTURAL rule (offline, deterministic): the bundle records its phase head
# (`phase_head`) and which workflows it claims final-CI green for (`ci_claimed`,
# default `governance` — the push gate runs on every push to main; a phase that
# touched xr-core lanes or C++ cores declares `core-hardening` too). Every
# claimed workflow needs >= 1 `source: ci-run` row whose `head_sha` matches
# `phase_head`; a row citing an OLDER head stays fine for its own claim (rule
# (a) resolves its greenness) but cannot stand as the phase's final-CI claim.
# Online authenticity is rule (a)'s job; this rule is the bundle's own
# consistency, so it must not depend on network reachability.

_HEAD_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_CI_RUN_LABEL = "ci-run"
DEFAULT_CI_WORKFLOWS = ("governance",)


def _head_matches(row_head: str, phase_head: str) -> bool:
    """7..40-hex, case-insensitive, prefix-match either way (the resolver's
    own comparison shape: a short recorded rev meets a full API sha)."""
    a = _HEAD_RE.search(row_head or "")
    b = _HEAD_RE.search(phase_head or "")
    if not (a and b):
        return False
    ra, rb = a.group(0).lower(), b.group(0).lower()
    return ra.startswith(rb) or rb.startswith(ra)


def head_coverage_findings(doc: dict, rows: list[dict], path) -> list[str]:
    """T0-U2 findings, or [] — plus the comparison lines the reader needs to
    SEE that both heads were compared (stderr, both --json and text modes)."""
    fails: list[str] = []
    phase_head = str(doc.get("phase_head") or "").strip()
    if not _HEAD_RE.search(phase_head):
        # not declared: grandfathered bundle (P9-T12 scoping pattern) — the
        # rule binds only bundles that record their head.
        return fails
    claimed = doc.get("ci_claimed")
    if isinstance(claimed, list) and all(
            isinstance(w, str) and w.strip() for w in claimed):
        claimed = [str(w).strip() for w in claimed]
    else:
        fails.append(f"{path}: ci_claimed must be a list of non-empty "
                     f"workflow names (T0-U2), got {claimed!r}")
        claimed = []
    if "governance" not in claimed:
        fails.append(f"{path}: ci_claimed must include 'governance' — it runs "
                     f"on every push to main, so a phase cannot claim final-CI "
                     f"green without it (T0-U2)")

    covered: dict[str, str] = {}
    for row in rows:
        if row.get("source") != _CI_RUN_LABEL:
            continue
        wf = str(row.get("workflow") or "governance").strip()
        row_head = str(row.get("head_sha") or "").strip()
        print(f"head-match: phase_head={phase_head} vs ci-run "
              f"{row.get('id', '<no id>')} head_sha={row_head} "
              f"(workflow={wf})", file=sys.stderr)
        if _head_matches(row_head, phase_head):
            covered.setdefault(wf, str(row.get("id", "<no id>")))
    for wf in claimed:
        if wf not in covered:
            fails.append(
                f"{path}: phase records head {phase_head[:12]}, but no "
                f"ci-run row carries a matching head_sha for workflow "
                f"{wf!r} (T0-U2) — a final-CI claim must point at the "
                f"phase's own head, not an older one")
    good = sorted(f"{w}:{rid}" for w, rid in covered.items())
    print(f"head-match: covered=[{', '.join(good) or 'none'}] "
          f"phase_head={phase_head}", file=sys.stderr)
    return fails


# Tests monkeypatch this to exercise the content-mismatch paths offline.
CI_RESOLVER = _default_ci_resolver
