# ADR-0002: Machine-checkable Decision Register and ADR numbering

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Deciders (humans):** XR Platform team (agent draft; human ratification tracked)
- **Plan anchor:** Plan §0 header ("Changes to any … Decision Register (DR-xx) entry require new external evidence and a recorded reversal"), §7.3, §14 L14/L24, Appendix B, P5-T10 (contract-amendment RFC procedure binds the same flow for contracts)

## Context

Appendix B of the Plan carries 30 decisions (DR-01..DR-30) that are the
**only** mechanism for reopening settled engineering fights (Plan §0.1
rulings R1–R15; "reopen only with written new evidence"). The Plan's own
P1 task list (XR-P1-T9) requires a *machine-checkable* register, and P1-T7
requires S0 enforcement by CI. Without machine checks, register drift is
silent — the exact failure mode the Plan calls its #1 risk class.

At the same time, the ADR directory needs a numbering scheme now, because
ADR-0042 is **reserved** for the P4 identity-seam ADR (Plan §4 P4: "T8 write
ADR: chosen seam …"; "Artifacts: … ADR-0042 'identity seam'").

## Decision

1. **Register location & shape:** `docs/register/decisions.yaml` is the
   single machine-readable source for DR-01..DR-30, transcribed from Plan
   Appendix B (no rewording of rationales). Fields per entry: `id`,
   `title`, `status`, `rationale`, `linked_lg`, `reopen_condition`,
   `phase_anchor`. Status enum: `RATIFIED | OPEN | GATE-PENDING | MONITORED`.
   P1 status assignments: DR-01 = `GATE-PENDING` (funding, §15-R17);
   DR-14 = `OPEN` (pending LG-3 verdict); DR-15 = `OPEN` (pending LG-2
   verdict); DR-13 = `MONITORED` (CWS fragility watch, §15-R5); all others
   `RATIFIED`.
2. **Register-change protection:** any commit touching
   `docs/register/decisions.yaml` must carry the git trailer
   `Register-Change: ADR-<nnnn>` naming the ADR that authorizes the change.
   The initial seeding commit cites ADR-0002 (this ADR).
   `tools/dr_parse.py --check-trailers` enforces this in CI; schema and
   completeness (all 30 ids present exactly once) are validated by
   `tools/dr_parse.py`.
3. **ADR numbering:** `docs/adr/NNNN-<slug>.md`, 4-digit zero-padded,
   sequential, never reused. **0042 is RESERVED for the P4 identity-seam
   ADR** ("identity seam": primary `StoragePartitionConfig` model vs.
   `BrowserContext` fallback, Plan §4 P4-T8/T9). 0042 must not be allocated
   to any other topic before P4 executes; if P4 produces the ADR with a
   different number, the reservation lapses and 0042 becomes free (recorded
   in `docs/adr/RESERVED.md`).
4. **Agents draft, humans decide (L24, explicit):** coding agents may
   *author drafts* of ADRs and register changes, but the **decision** —
   flipping an ADR to ACCEPTED or changing a DR status — is made only by
   named human deciders. Agent-drafted ADRs carry the decider line
   "recorded by agent draft; human ratification pending" until a human
   signs off. This ADR set (0001, 0002) is such a draft awaiting human
   ratification; the *mechanics* (numbering, trailer rule, reserved 0042)
   are in force for tooling purposes regardless, because they only
   constrain process, not product.
5. **Reopening a DR:** new written evidence → new ADR referencing the DR →
   register status changed in the same PR with `Register-Change` trailer →
   CI validates. Reopenings are *loud*: the ADR title names the DR, and the
   register keeps the old `rationale` verbatim (new rationale is appended
   via `superseded_by` note, not rewritten).

## Consequences

- Positive: register drift is impossible without a trailer; ADR-0042 cannot
  be accidentally consumed; agent/human authority boundary is explicit.
- Negative / cost: one extra trailer on register commits (trivial); the
  initial register is an agent transcription — a human re-read against
  Appendix B is a listed human gate (`evidence/P1/human-gates.md`).
- Follow-ups: P5-T10 (same trailer discipline extended to `//xr/mojom`
  contract amendments), P9 (gate tool reads the register for §17 DoD
  computation).

## Reversal

Changing the numbering scheme or the trailer rule requires a superseding
ADR (this would be the first case of the rule applying to itself).
Changing any DR status is governed by §5 above, not by this ADR's reversal
clause.
