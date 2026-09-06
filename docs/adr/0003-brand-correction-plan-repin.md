# ADR-0003: Brand correction (RRRTX Systems → RRRTX Labs) and plan re-pin

- **Status:** Accepted
- **Date:** 2026-09-07
- **Decider:** Principal, RRRTX Labs (agents draft, humans decide — ADR-0002 §4)
- **Supersedes:** nothing (no prior decision concerned company branding)

## Context

The official company/product brand is **RRRTX Labs**. The pinned plan v1 is
internally inconsistent about it:

- line 3: `**Product:** XR Browser by RRRTX Systems` (stale)
- line 8: `**Spec-B** … (RRRTX Labs engineering spec)` (current)

Other repo surfaces carried the stale form: `README.md`
("XR Browser by RRRTX Systems") and `SECURITY.md`
("Security policy — XR Browser (RRRTX Systems)").

At P1 release preparation (2026-09-07), the principal directed that no
"RRRTX Systems" branding remain in XR-owned project content, and that the
plan — the pinned single source of truth — be corrected through the
documented amendment path rather than left inconsistent.

## Decision

1. **v2 of the plan** is created at
   `docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md`: **exactly one
   token changed** vs v1 (line 3, `RRRTX Systems` → `RRRTX Labs`). No line
   is added or removed, so every line-number reference (feature registry
   `plan_line` fields, vocab-allowlist entries, threat-model links) stays
   valid.
2. **Re-pin, in one commit:**
   - `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` = byte copy of v2
   - `docs/master-plan.sha256`:
     - old (v1): `a74b2aa4e8fd6f427c71cadfe932489249afe208a10413bf78c04734fd343e1b` (298,080 B)
     - new (v2): `02743146146fa139cd53b15216aaa26b79f9d9307998b1814019d27406265a7b` (298,077 B)
   - `docs/register/decisions.yaml` `plan_sha256` → v2 digest
   - `docs/registry/*` regenerated via `tools/gen_registry.py --write`
   - `docs/threat-model.md` header SHA → v2 digest
   - recorded digests updated in `evidence/P1/registry-recount.md`,
     `evidence/P1/evidence.json`, and the pin test constants
3. **Repo surfaces** updated to the official brand: `README.md`,
   `SECURITY.md` (title). `SECURITY.md`'s pending GHSA URL is pointed at
   the real organization `github.com/RRRTX-Labs` (status remains
   PENDING-OPS until the repos are pushed and GHSA is enabled — HG-3/HG-4).
   `evidence/P1/human-gates.md` HG-3 records the org name.
4. **Not changed (deliberate):**
   - `/home/user/uploads/` original spec (out of repo, read-only per
     project rule — the in-repo v2 is the authoritative copy).
   - `rrrtx.example` addresses and `@xr/*` handles: RFC 2606 placeholder
     identities for mailboxes/org handles that do not exist yet
     (HG-2/HG-3), not company branding.
   - Git commit author metadata (`platform@rrrtx.example`): history is
     immutable; the identity is a documented placeholder.
   - Owner-placeholder IDs `RRRTX-*` (e.g. `RRRTX-LEGAL-01`): internal
     role prefixes, consistent with the brand.
   - Third-party copyright/license attributions and upstream authorship
     (untouched by this ADR).

## Consequences

- Every governance anchor now binds the v2 digest; the v1 digest is
  recorded here and remains valid only as history.
- The original (pre-correction) spec remains available to the principal in
  `/home/user/uploads/`; the in-repo plan is the project's source of truth
  and carries the v2 digest.
- Future brand changes repeat this path: new versioned plan file +
  re-pin in one reviewed commit (docs/process/plan-amendment.md).

## Reopen condition

A change of the official brand by the principal, or evidence that the v1
spec (with its original text) must be preserved byte-for-byte as the
anchor (e.g. an external audit keyed to the v1 digest). In either case:
new plan version + re-pin + this ADR revised.
