## What changes and why

<!-- 1–3 sentences. Link the Decision Register row (DR-xx) or ADR that
     authorizes this change, if any. -->

## Plan traceability

- Plan section(s) affected: <!-- e.g. §2.4, §14, P5-T10 — or "none" -->
- Plan amendment required? <!-- no | yes (see docs/process/plan-amendment.md) -->

## Change discipline checklist (CI enforces most of these)

- [ ] I am NOT editing the pinned plan in place
- [ ] If I touched `docs/register/decisions.yaml`: the commit carries
      `Register-Change: ADR-<nnnn>`
- [ ] If I touched `docs/registry/*`: it was regenerated with
      `tools/gen_registry.py --write` after an approved amendment
- [ ] If I touched user-facing copy: no banned-claims vocabulary
      (plan §0.3/§9.11); new allowlist entries have written justifications
- [ ] If I added/updated a dev dependency: `tools/requirements-dev.txt`
      is hash-pinned and the consumer is in this same commit
- [ ] No premature stubs for later phases (plan L5)

## Verification

<!-- Show the local loop output (or the relevant part): -->

```
$ tools/run_checks.sh
…
$ tools/run_negatives.sh
…
```

## Human review needed (S0/S1)

- [ ] This touches an S0 path (`tools/`, `docs/register/`, `docs/registry/`,
      `docs/adr/`, `.github/workflows/`, `ci/`) — dual senior review incl. Security required
- [ ] This touches an S1 path (`docs/legal/`, `docs/dependencies/`) — legal/owner review required
