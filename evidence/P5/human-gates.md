# P5 — human gates

P5's mechanical work is complete and green; the following require humans/infra
and were NOT simulated (L24). New gates opened by P5 are HG-26 and HG-27.

## New in P5

- **HG-26 — Contract ratification (S0 dual-review).** The 14 review packets
  (`docs/contracts/review/01..14-*-v1.md`) carry the required checklist rows
  (narrow surface / typed errors / no generic exec / fuzz-target-before-
  integration) with **human sign-off fields pending**. `FROZEN.yaml` rows are
  `ratified: PENDING`; no agent may write RATIFIED (freeze_check enforces).
  Includes the **Design-track** review row (§10 command/settings/theme) and
  the S0 Security review. P6 may start against the fakes+vectors now
  (orchestrator sequencing) — this gate does not block P6.
- **HG-27 — mojom bindings compile at farm.** The C++/JS mojom bindings for
  `//xr/mojom` must compile on the farm (pinned checkout + toolchain). Feeds
  P6's first CI. Includes verifying the per-file `kContractVersion` const does
  not trigger a module-scope redefinition (mechanical fix pre-documented in
  `docs/contracts/INDEX.md` if it does).

## Carried (not closed by P5)

- **HG-1** counsel — Isolation-Card strings legal review (`legal: PENDING-HG-1`).
- **HG-6** funding.
- **HG-9 / HG-21** farm build + runtime probes (all measured-table rows remain
  PENDING-FARM).
- **HG-23** ADR-0042 ratification (P5 recorded the orchestrator disposition;
  ratification is still a human act).
- Hosted-CI success at the final xr-browser HEAD is reported once the P5 PR
  lands on `main` and `governance.yml` runs (DOD-11, HUMAN-GATED).

## Push / consent note

The user explicitly authorized pushing with a supplied token and stated they
will revoke it afterward. xr-core P5 was pushed to `main` (the cross-repo pin
process requires the pinned rev to be an ancestor of origin `main`). The
xr-browser P5 branch push is recorded in the evidence; merging it to `main` is
a human action (PR review), consistent with the S0 dual-review model.
**The supplied token should be revoked now.**
