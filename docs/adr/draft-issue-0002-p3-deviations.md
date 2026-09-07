# Draft issue 0002 — P3 execution deviations (recorded, none blocking)

Status: DRAFT for human decision · Raised: P3 (2026-09-07) · Owner: @xr/platform

P3 shipped with three conscious deviations from the letter of the plan/prompt.
All are honest-surface decisions; each needs a human call to accept or amend.

1. **§12.4 symbol evolution — `GetStoragePartitionConfigForSiteInstance`.**
   The plan pins this verbatim symbol as an assumption row. At the DEPS pin
   (d04cdb24…) the API has evolved: the surface is now
   `SiteInfo::GetStoragePartitionConfigForUrl(this, url)` (browser_context.cc
   L159) plus `GetSecurityPrincipal().GetStoragePartitionConfig()` (L138);
   the verbatim plan symbol does not exist. Assumption A2 encodes the
   EVOLVED surface (verified by gitiles TEXT before encoding, R10), so drift
   from today's reality FAILs the suite — the safety property the plan
   wanted. DECISION NEEDED: accept the evolved-surface encoding (recommended;
   the alternative pins a dead symbol and fails forever) or re-point A2 at a
   different anchor when P4/P12 land the Site Isolation work.

2. **`xr-patch retire` requires `--evidence` beyond the prompt's
   `--id/--mechanism/--note`.** The ledger row's `evidence` field (upstream
   CL / bug / obsolescence reference) is required by the same honesty law
   that forbids hollow retirement records (L5). DECISION NEEDED: accept the
   extra required flag (recommended) — retiring a seam without a reference
   is exactly the record a later audit cannot trust.

3. **Pre-GA SLA breaches are ADVISORY-ONLY.** §12.4/§15-R1's kill-switch
   (missed window ⇒ feature freeze) presupposes a shipped product. XR has
   no stable release until P10; the real tag 152.0.7977.83's 72h window
   lapsed pre-GA (R12). The sla tool computes honestly and writes the
   marker, but every artifact states the marker is advisory until the first
   stable promotion arms it. DECISION NEEDED: confirm the arming point
   (P10 first stable) is the intended semantics, vs. arming at first
   nightly (P9) instead.

---

## Disposition (2026-09-08, orchestrator)

Recorded by P4-T0.4 (debt D-D). The orchestrator has RULED on all three
deviations; this section records the ruling, it does not relitigate it.
All three are **ACCEPTED**.

1. **§12.4 symbol evolution — ACCEPTED.**
   A2 pins the *evolved* partition-config symbols; that is precisely what an
   upstream-assumption suite is for — it must assert the surface that exists at
   the pin, so that drift from today's reality fails the suite. Pinning the
   verbatim plan symbol would encode a dead symbol and fail forever.
   *P4 measurement note (2026-09-07, at pin d04cdb24…):* the embedder override
   in `content/public/browser/content_browser_client.h:1208` is
   `GetStoragePartitionConfigForSite(BrowserContext*, const GURL&)`; no
   `…ForSiteInstance` exists anywhere at this rev. See
   `docs/spike-identity/measured-shared-state.md` row S-01 and
   `docs/adr/0042-identity-seam.md`.

2. **`xr-patch retire --evidence` — ACCEPTED.**
   The extra required flag strengthens the ledger and is kept. Retiring a seam
   without an upstream CL / bug / obsolescence reference produces exactly the
   record a later audit cannot trust (L5).

3. **Pre-GA advisory SLA markers — ACCEPTED, with mandatory hardening at P9.**
   Advisory-until-first-stable is the correct semantics while XR has no
   release. **The arming point is P9 (first nightly), not P10**, and the
   hardening is mandatory work in P9, not optional follow-up: the
   fast-lane docs and `docs/runbooks/fastlane-runbook.md` must carry that P9
   hardening obligation explicitly so the advisory marker becomes a real
   kill-switch before any user-facing build exists.

### Also recorded: draft-issue-0001 (SECURITY_NOTES falsification)

The proposed falsification is **accepted**. The fast-lane's primary signal is
the release/tag channel via chromiumdash — already implemented in
`build/upstream/fastlane.py` — and that remains the primary signal. The
source-fixture note is kept: it documents why the source path was rejected as
primary, so the decision is auditable rather than forgotten.
