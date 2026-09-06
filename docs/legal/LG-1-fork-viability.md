# LG-1 — Fork viability, licensing posture, trademark & codec budget — **DRAFT-FOR-COUNSEL**

- **Status:** DRAFT-FOR-COUNSEL (facts, sources, questions, options — no legal conclusions; the verdict is counsel's work, HG-1)
- **Date:** 2026-09-07 · **Prepared by:** XR Platform agent (P1, XR-P1-T5)
- **Linked register rows:** DR-01 (funding gate — GATE-PENDING), DR-02 (Chromium + overlay + cadence), DR-05 (MPL-2.0), DR-04 (no GPL linked), DR-26 (cadence decoupling)
- **Linked assumptions:** A2 (Widevine availability — see LG-3), §15-R17 (funding-shock fallback)

## 1. Questions for counsel

- **Q1 (overlay legality):** Is the overlay-repo model — `xr-core` as an independent MPL-2.0 repository mounted at `chromium/src/xr` inside a pinned Chromium checkout, with upstream modifications carried as a budgeted patch set (≤150 files) tracked in a patch ledger — legally sound with respect to Chromium's BSD-3-Clause redistribution conditions, specifically the attribution requirements for *modified* upstream files? Is the Plan's patch-ledger mechanism (owner, category, upstream-bug reference, rebase notes per modified file) an adequate attribution/provenance record, or do additional per-file notices/conditions apply?
- **Q2 (trademarks):** What trademark stripping is required for a Chromium fork: names (Chrome/Chromium/Google), logos, UI assets, the "Chromium" designation in release notes/about pages? What does the BSD-3 non-endorsement clause ("Neither the name of Google LLC nor the names of its contributors may be used to endorse or promote products derived from this software…") practically require for our marketing surface, `xr://help` copy, and the docs site (P39)?
- **Q3 (funding-gate point-of-no-return):** The Plan carries DR-01 (≥10 engineers or §15-R17 fallback: hardened-Chromium distribution + companion processes) as a *Stage-0 exit condition* and assumes the funded-team premise (§0.2-7). If the gate regresses after P1 artifacts exist: (a) are the MPL-2.0 license grants already made on the P1 governance repositories (this repo + xr-core) a problem for pivoting to the fallback distribution? (b) Is there any point after which the fallback posture is no longer available (e.g. after the first public build, after enterprise commitments in P39-T4)?
- **Q4 (codec budget):** For the shipping build's codec matrix (H.264, HEVC, AAC, VP8/9, AV1 — Plan §11.12), what are the known patent-pool / licensing considerations a fork should be aware of *as a client* (no content provision), and which of them (if any) should be a budget line in the funding gate rather than a legal blocker? (Widevine/DRM-specific questions are in LG-3.)
- **Q5 (MPL-2.0 for tooling + overlay):** Confirm the choice recorded in ADR-0001 (uniform MPL-2.0 file-level copyleft including Python governance tooling) is appropriate, and identify any interaction between MPL-2.0 `//xr` files and BSD-3 upstream files when both are *built* into one binary (as opposed to linked as libraries) — in particular whether any build-combination could be characterized as a "Larger Work" scenario that changes notice obligations.

## 2. Facts (sourced; all accessed 2026-09-07)

| # | Fact | Source (URL) | One-line quote | Anchors |
|---|---|---|---|---|
| F1 | Chromium's codebase license is BSD-3-Clause with a Google non-endorsement clause | https://chromium.googlesource.com/chromium/src/+/main/LICENSE | "Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met … Neither the name of Google LLC nor the names of its contributors may be used to endorse or promote products derived from this software…" | Q1, Q2 |
| F2 | The overlay-repo model (separate repo of "changes, APIs, and scripts" over a pinned Chromium, with maintained patches) is in production use by Brave — live evidence the model survives trains | https://github.com/brave/brave-core (README) | "Brave Core is a set of changes, APIs, and scripts used for customizing Chromium … Maintains patches for 3rd party Chromium code." (repo active: pushed 2026-09-06; license MPL-2.0) | Q1 (pattern evidence) |
| F3 | The *rejected* alternative build model (ungoogled-chromium) is domain-substitution patching built for purity, not product cadence — the Plan takes its *inventory*, not its build model (Plan §1.2 de-Googling posture) | https://github.com/ungoogled-software/ungoogled-chromium (README) | "These features are implemented as configuration flags, patches, and custom scripts … replacing many Google web domains in the source code with non-existent alternatives ending in `qjz9zk` (known as domain substitution)" | Context for Q1 (what we are NOT doing) |
| F4 | Chromium's release cadence changed to two-week Stable/Beta starting Chrome 153 (2026-09-08) — the economic premise of the funding gate (rebase economics "nearly double", Plan §0.2-1) | https://developer.chrome.com/blog/chrome-two-week-release | "The new release cycle means that a new beta and stable version of Chrome will ship every two weeks, starting from the stable release of Chrome 153 on September 8th. This applies to all platforms—Desktop, Android, and iOS." | Q3 (cadence risk), DR-26 |
| F5 | An independent embedder's public adaptation confirms the even-milestone (4-week-equivalent) shipping strategy is workable — precedent for DR-26 | https://github.com/chromiumembedded/cef/issues/4114 (closed; created 2026-03-04) | "Adjustments for Chromium's two week release cycle (starting September 2026) … Update CEF for even numbered Chromium milestones only. This keeps us on the existing 4 week update strategy and aligns with existing extended/LTC/LTS channels" | Q3, DR-26 |
| F6 | Cautionary dataset: Thorium (patch-queue hobby model) is LTS-paced, the inverse of the overlay+canary-daily model the Plan adopts | https://github.com/Alex313031/thorium (README; repo moved from Everdevs.io; pushed 2026-08-23) | "Always built with the latest LTS version of Chromium." | Q3 (fallback context) |
| F7 | The identity seam the product depends on is an *upstream-supported* mechanism (process-suitability rule), reducing fork-legal surface to the patch budget | https://chromium.googlesource.com/chromium/src/+/main/docs/process_model_and_site_isolation.md | "StoragePartition (which may differ between tabs and Chrome Apps) … two documents from different profiles or StoragePartitions can never share the same renderer process." | Q1 (seam = supported override, not a legal-ambiguous fork hack) |
| F8 | DCO trailer convention used by both P1 repositories (`Signed-off-by: Name <email>`) | https://developercertificate.org/ | "By making a contribution to this project, I certify that: (a) The contribution was created in whole or in part by me and I have the right to submit it under the open source license indicated in the file; …" (Developer's Certificate of Origin 1.1) | Q3 (contribution-record obligations) |

## 3. Our model, as it exists (for counsel's framing)

- Two MPL-2.0 repositories exist today (governance files only; no engine code): `xr-browser` (meta) and `xr-core` (product). First build: P2 (hermetic Chromium build, DEPS-pinned).
- Distribution model: **free open-source browser for consumers + a paid enterprise edition** (Plan §16 P39-T4: enterprise policy pack; MPL-2.0 chosen partly to keep this legal — ADR-0001).
- Patch budget ≤150 upstream files, CI-counted, published per release (Plan §1.2) — the attribution surface for Q1.
- No XR-operated services (DR-10); update/list channels are XR-operated signed endpoints (T10 threat model).

## 4. Options with consequences (no recommendation — counsel's call)

| Option | Content | Consequences (as we understand them — counsel to correct) |
|---|---|---|
| **A** | Proceed on the funded-team premise (Plan §0.2-7); DR-01 stays GATE-PENDING until principals record staffing (HG-6); overlay + MPL-2.0 + DCO as designed | Full product path; P2 build-farm capacity sized for the two-week upstream pace (F4); if the gate regresses later, §15-R17 fallback must still be *available* (see Q3) |
| **B** | Adopt the §15-R17 fallback posture now (hardened-Chromium distribution + companion processes; no fork commitment) | Avoids fork obligations before funding is confirmed; cost: the identity/moat architecture (Plan §1.4) is not the fallback's shape — re-planning cost if funding later *lands*; P1 governance artifacts remain reusable |
| **C** | Hybrid: proceed with P2 (build system only) and re-open the gate at SF-0 (end of P5) | Limits sunk cost to build infra; Plan's concurrency plan assumes the funded premise from EB-1 — a mid-EB slip triggers the §15-R9 scope discipline |

## 5. Decision — **left blank by design**

- **VERDICT:** ______________ (counsel; attach written memo)
- **CONDITIONS:** ______________ (e.g. required trademark strip list, patch-ledger amendments, codec budget lines)
- **REVIEW-BY:** ______________ · **DATE:** ______________ (must precede P10 exit per A2/§15-R7 and inform the DR-01 gate)

## 6. Register actions on verdict

- Verdict → attached to DR-01 context (funding + codec budget) and DR-02 (overlay model confirmation);
- any condition that changes the patch-ledger shape → ADR (ADR-0002 flow, `Register-Change` trailer);
- any trademark constraint on `//xr` copy → copy-gate update (L5/L21 vocabulary lint inputs).
