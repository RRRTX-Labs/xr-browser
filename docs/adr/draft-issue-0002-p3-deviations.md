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
