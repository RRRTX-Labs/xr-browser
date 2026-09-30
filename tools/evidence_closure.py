"""tools/evidence_closure.py — WHEN the phase-finality law binds (P13-C-P0.3).

Extracted from tools/evidence_finality.py so no touched file crosses the
repo's 380-line ceiling (the P11 tools/checks/*.sh split is the precedent).

The law it serves is in docs/contracts/evidence-bundle-v1.md. The one sentence:

    a verdict is a CLAIM, and the gate binds on the claim, not on a phase's
    position in a list.

`--require-phase-final` used to trigger on *being the newest phase in
docs/state/phase-base.json*, which made it UNSATISFIABLE for an in-flight
phase — the presence law (tools/evidence_presence_check.py) requires a phase's
bundle from that phase's FIRST commit, and a bundle that must exist from commit
one cannot be final from commit one. So `governance` was red for the whole of
every future phase, in the same words every time: a real law turned into
background noise. Closure is an ACT, so it is stated as one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Same trailer discipline tools/dr_parse.py --check-trailers applies to
# `Register-Change:` (ADR-0002 §2): a trailer, on its own line, with the
# phase's own name — nothing inferred from position or from prose.
CLOSE_RE = re.compile(r"^Phase-Close:\s*P(\d{1,3})\s*$", re.MULTILINE)


def closure_claims(repo: Path, rng: str | None = None) -> set[str]:
    """Phases a `Phase-Close: P<n>` trailer CLAIMS to close, in the gated
    commits. Empty when git cannot answer (a fixture tree, a tarball): "no
    claim" is the fail-OPEN direction here *deliberately* — the fail-closed
    direction is the bundle's own `state`, and
    tools/negatives/p13_c03.sh pins both.
    """
    revs = [rng] if rng else ["HEAD"]
    try:
        # --no-merges: a merge commit re-states its children's messages, and a
        # phase closed on a topic branch must not be re-closed by its merge.
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--no-merges", "--format=%B", *revs],
            capture_output=True, text=True, timeout=60)
    except (OSError, ValueError):
        return set()
    if out.returncode != 0:
        return set()
    return {f"P{m.group(1)}" for m in CLOSE_RE.finditer(out.stdout)}


def closure_note(phase: str) -> str:
    """The line an unclaimed closing gate prints. A pass that is not a verdict:
    "not a verdict" is printed rather than nothing, because a silent pass is
    indistinguishable from a judged pass."""
    return (f"finality: {phase} interim (phase open; no closure claimed) "
            f"— not a verdict")


ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def interim_verdict(doc: dict, phase: str, in_flight: str | None) -> tuple[bool, str]:
    """Is `state: interim` legal for this bundle? (legal, message) — P13-C-P0.4.

    Legal in exactly two cases:

    1. it IS the in-flight phase (docs/state/phase-base.json) — PENDING
       sentinels are legal there and the final rules do not apply;
    2. it DECLARES interim outside that window **in writing**: at least one
       `not_done_by_design` row opening with an ISO date.

    Why (2) exists. P12 landed its substance while its same-head CI claim cannot
    exist — no green `governance` run exists at its recorded head, and a run four
    commits back cannot be created retroactively. The brief's two permitted
    answers were "declare interim with a dated reason" or "cite a green run at
    the phase's own head"; the second is unavailable, and the forbidden third is
    to point at someone else's green run. Declaring interim is therefore the
    honest act, and this rule is what keeps it from being a free pass: an
    undated interim has no author and no date on it, and the closing form
    (apply_phase_final) makes interim illegal the moment a `Phase-Close: <phase>`
    trailer exists. So the hole the P13-P0-C law closed — interim as a place to
    hide a finished-but-unproven phase — stays closed from both directions.
    """
    if in_flight is not None and phase == in_flight.strip():
        return True, (f"finality: {phase}: interim — in flight per "
                      f"docs/state/phase-base.json (phase={in_flight}); "
                      f"PENDING sentinels are legal here and the final rules do "
                      f"not apply")
    dated = [r for r in (doc.get("not_done_by_design") or [])
             if ISO_DATE_RE.match(str(r).strip())]
    if dated:
        return True, (f"finality: {phase}: interim — DECLARED, not the "
                      f"in-flight phase (phase={in_flight}); legal only because "
                      f"{len(dated)} dated not_done_by_design row(s) say what "
                      f"remains, and the final rules do not apply until closure "
                      f"is claimed (P13-C-P0.4)")
    return False, (f"state 'interim' but this is not the in-flight phase "
                   f"(docs/state/phase-base.json says {in_flight!r}) and no "
                   f"dated not_done_by_design row says why — a phase may only "
                   f"stay open in WRITING, dated, and never as the state of a "
                   f"closed/superseded phase (P13-P0-C)")


def apply_phase_final(results: dict, repo: Path, *, claims: set[str],
                      in_flight: str | None) -> None:
    """Enforce the claim: every phase that claims closure must be `final`.

    `results` maps bundle path -> failures, and is MUTATED (that is the point:
    the caller's own reporting, --json included, sees the finding). A phase
    whose bundle is missing from the run is not silently skipped — the presence
    law owns "no bundle at all", and this law owns "bundle says interim".
    """
    if not claims:
        print(closure_note(in_flight or "P<n>"), file=sys.stderr)
        return
    for phase in sorted(claims):
        rel = f"evidence/{phase}/evidence.json"
        if rel not in results or results[rel]:
            continue
        doc = json.loads((repo / rel).read_text(encoding="utf-8"))
        if str(doc.get("state", "final")).strip().lower() == "final":
            print(f"finality: --require-phase-final: {phase} claims closure "
                  f"(Phase-Close trailer) and declares final — judged",
                  file=sys.stderr)
        else:
            results[rel] = [
                f"{rel}: a `Phase-Close: {phase}` trailer claims this phase is "
                f"closing at this commit, but the bundle still says 'interim' — "
                f"flip it to 'final' with its report.md and its same-head "
                f"ci-run rows, or drop the trailer and leave the phase open "
                f"(P13-C-P0.3)"]
