# ADR-0042: the XR identity seam — partition-domain per tab, contingent on runtime confirmation

- **Status:** PROPOSED (drafted by the P4 coding agent; **ratification is
  HUMAN-GATED — HG-23**, Platform + Security lead sign-off)
- **Date:** 2026-09-07
- **Deciders (humans):** Platform lead + Security lead (HG-23). Coding agents
  draft; they never decide (L24).
- **Plan anchor:** Plan §1.4, §4 Phase P4 (T1–T9), §12.7 never-list, DR-06
  (identity model — **locked**, not reopened here), DR-25
- **Evidence:** `docs/spike-identity/measured-shared-state.md` (23 rows, all
  citation-audited), `docs/state/research-log-P4.md`,
  `evidence/P4/logs/citation-audit.txt`, `evidence/P4/logs/genpatch-roundtrip.txt`

## Context

Plan §1.4 proposes XR identities as per-`WebContents` `StoragePartitionConfig`
domains inside **one** profile, with non-shared renderers and per-partition
`NetworkContext`s. P4 exists to validate or falsify that at the pinned
Chromium rev, because the whole identity architecture (P5 onward and the
isolation matrix §11.4) rests on it.

The orchestrator ruled that P4 proceeds in split form: full **static**
measurement now (executable, and the majority of the epistemic risk), plus a
committed spike kit so the farm executes rather than designs. **No runtime
result is claimed anywhere in this ADR.**

### What the static measurement found

1. **§1.4's named API does not exist at the pin.** There is no
   `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance`. The
   embedder hook is
   `ContentBrowserClient::GetStoragePartitionConfigForSite(BrowserContext*,
   const GURL&)` (`content/public/browser/content_browser_client.h:1208`),
   consulted from `content/browser/site_info.cc:819`.
2. **…and it could not carry identity even if the name were right.** It is
   keyed on `(profile, site)`; two identities visiting the same site in one
   profile are indistinguishable at that call.
3. **The architecture still holds, via a different and better-placed seam:**
   `SiteInstance::CreateForFixedStoragePartition(profile, url, config)`
   (`content/public/browser/site_instance.h:255`) is public embedder API that
   creates a BrowsingInstance whose StoragePartition "is preserved across
   navigations", pinned by `CHECK_EQ`
   (`content/browser/browsing_instance.cc:183`) and inherited by later
   SiteInstances (`:263`). Renderer reuse requires `InSameStoragePartition()`
   (`content/browser/renderer_host/render_process_host_impl.cc:4952`).
4. **The `WebContentsUserData` timing race that §1.4 calls its #1 risk
   dissolves.** The partition must be fixed *before* `WebContents::Create()`;
   taken there, no race exists. `XRIdentityTabData` is therefore a record for
   later lookups, not the mechanism.
5. **DNS is QUALIFIED, not confirmed.** The per-context host resolver is
   partition-local, but the `HostResolverManager` is one per NetworkService
   (`services/network/network_service.cc:492`) and the OS resolver cache is
   outside the browser. DNS is a cross-identity correlation surface.
6. **Nothing in the seam requires touching `content/**`.** The hook lives in
   `chrome/browser/**`, so §12.7 is satisfied.

**Verdict at source level: QUALIFIED — the property is confirmed, the named
mechanism is falsified, and the working mechanism is a different public API.**
This is a finding, not a failure: DR-06 (the identity *model*) is untouched.

### Not decided here

DR-06 (the identity model) is locked. The `.onion`/HCMS/network layers, the
Vault, and identity *persistence* are out of scope. The P5 contract freeze is
P5's job and is gated on the farm results (HG-21) by the orchestrator.

## Decision (contingent)

**Adopt identity = one `StoragePartitionConfig` domain per tab
(`xr:<uuid>`), established at tab creation by
`SiteInstance::CreateForFixedStoragePartition()`, inside a single Profile —
contingent on the runtime rows below confirming the static findings.**

Decision points:

1. The seam is `SiteInstance::CreateForFixedStoragePartition()`, taken in
   `CreateTargetContents()`
   (`chrome/browser/ui/navigator/browser_navigator.cc:479`), before
   `WebContents::Create()`. Candidate patch:
   `xr-core/spike/patches/0042-seam-hook/` (`manifest-entry: NOT-YET`).
2. `GetStoragePartitionConfigForSite()` is **not** the identity seam. It stays
   available for scheme-scoped routing only
   (`xr-core/spike/identity_seam/xr_seam_override.cc`).
3. Identity partitions are validated to be non-default and UUIDv4-shaped; a
   malformed domain is rejected, never silently defaulted
   (S-04, S-22 — an empty domain *means* the default partition).
4. Until HG-21 confirms the runtime rows, this ADR is **PROPOSED** and no
   identity code may be promoted into `patches/manifest.yaml`.

## Falsification triggers

If the farm (HG-21) returns any row below as FAIL, the corresponding trigger
fires. **F1/F2/F3 make the fallback the recommended path** and the P5
identity-adjacent contract freeze must not proceed (HG-24).

| id | trigger (runtime observation) | probe | action if it fires |
|----|-------------------------------|-------|--------------------|
| **F1** | Two identities on the same site end up in the **same** BrowsingInstance or share a renderer process | `probes/process_sharing_browsertest.cc` | Execute T9 fallback (identity = BrowserContext). P5 freeze blocked. |
| **F2** | A cross-site navigation **escapes** the identity partition (config not inherited) | `probes/process_sharing_browsertest.cc` | Fallback; the partition model cannot hold a tab together. |
| **F3** | A second identity's StoragePartition resolves to the **default** partition (or `in_memory` silently collapses) | `probes/isolation_matrix_browsertest.cc`, `probes/ephemeral_zero_write_browsertest.cc` | Fallback; isolation is not expressible. |
| **F4** | Two identity partitions share one **NetworkContext** (so proxy/HSTS/cache collapse) | `probes/network_context_browsertest.cc` | Not a model change: network binding becomes a separate P5/P14 workstream with its own ADR; identity stays. |
| **F5** | An ephemeral identity writes **>0 bytes** to disk (FS-diff) | `probes/ephemeral_zero_write_browsertest.cc` + `build/spike/fsdiff.py` | Not a model change: the ephemeral claim is retracted and limitations.md is corrected before any user-facing copy ships. |
| **F6** | Fortress (OTR Profile) **rejects** custom partition domains (the `CHECK` in `browser_context.cc:148` fires) | `probes/fortress_profile_coexist_browsertest.cc` | Fortress is re-cut as its own BrowserContext; identity per tab stays for the non-OTR case. |
| **F7** | The patch no longer applies cleanly at a newer upstream rev | `./scripts/build spike genpatch` (promotion canary) | Patch is re-cut before promotion; budget/S0 review re-run. Not a model change. |

## Patch estimate (a contract for P5)

Counts are **files touched × §1.2 budget category**, from the candidate patch
plus the census rows that must land before identities are user-visible.

| workstream | files × category | against cap | phase |
|---|---|---|---|
| Seam hook itself (candidate, navigator + BUILD.gn + 4 new files) | 6 × `hook_points` | 6 / 45 | P5 |
| Per-identity network binding (`ConfigureNetworkContextParams`) | 5 × `network_seams` (+2 × `hook_points`) | 5 / 20 | P5 |
| Identity lifecycle UI + tab affordance | 12 × `ui` | 12 / 35 | P5 |
| Profile-shared surface re-keying (census C-01, C-04, C-10, C-11) | 23 × `ui` + 7 × `hook_points` | 35 / 35 (ui **at cap**) + 13 / 45 | P14 |
| DevTools + extension chokepoint (C-03, C-15) | 8 × `extension_chokepoint` **(over the cap of 2)** + 4 × `hook_points` | **8 / 2 — needs a plan amendment or a different mechanism** | P14 |
| Favicon + SW notification scoping (C-08, C-12) | 6 × `hook_points` + 2 × `network_seams` + 3 × `ui` | 17 / 45 | P14 |
| **Total (P5 only)** | | **~25 / 150** | |
| **Total (P5 + P14)** | | **~90 / 150**, **except `extension_chokepoint` which is 4× over cap** | |

The `extension_chokepoint` overage is reported, not hidden. It is a real
conflict with §1.2 and must be resolved by a plan amendment, by reclassifying
the work, or by forbidding extensions in identity tabs — **not** by quietly
spending the budget.

## What an attacker could observe cross-identity

Even with the seam working, these are **not** partitioned. They feed §9 and
the Isolation Card copy; each is a threat-model row.

| id | observable | how | severity |
|----|-----------|-----|----------|
| TM-P4-1 | that an identity downloaded a file (name, time) | Downloads DB is Profile-level (C-01) | S1 |
| TM-P4-2 | other identities' tab titles and URLs | DevTools target registry is browser-wide (C-03) | S1 |
| TM-P4-3 | whether another identity has visited a site | shared favicon cache hit timing (C-12) | S1 |
| TM-P4-4 | full browsing history of other identities | omnibox History provider (C-04) | S1 |
| TM-P4-5 | saved credentials/addresses from other identities | Profile-level autofill store (C-10) | S1 |
| TM-P4-6 | a complete cross-identity activity map | global tab index (C-11) | S1 |
| TM-P4-7 | correlation through extension messaging | one extension registry per Profile (C-15) | S1 |
| TM-P4-8 | DNS resolution as a side channel | shared `HostResolverManager` + OS resolver cache (S-16/S-17) | S2 |
| TM-P4-9 | GPU-process and clipboard are shared | process-global GPU, system clipboard (P-8/P-9) | S2 |

**Nothing here is "airtight".** Identity partitions isolate *storage and
renderer processes*, not the Profile's shared services. Marketing copy must
say so; `tools/vocab_lint.py` enforces the wording.

## Consequences

- **Positive:** the seam is public embedder API, needs no `content/**` patch,
  and is CHECK-enforced upstream — the isolation invariant we rely on is
  upstream's own invariant, not something we re-implement.
- **Positive:** the timing risk §1.4 worried about does not exist at this
  hook point.
- **Negative:** 15 papercuts, 9 of them S1, all in Profile-level surfaces the
  partition does not reach (census). Identity is a storage/process boundary,
  **not** a full-profile boundary.
- **Negative:** the extension chokepoint budget is exceeded by the DevTools +
  extension work; that is a plan conflict to resolve, not a rounding error.
- **Follow-ups:** HG-21 (farm runtime), HG-23 (ratification), HG-24 (P5
  freeze gating), P14 (census fixes + §11.4 isolation matrix).

## Contracts out (for P5, drafting only)

`IdentityProvisioning` must specify: (a) identity creation returns an
`xr:<uuid>` domain, validated UUIDv4; (b) provisioning is a **pre-navigation**
request — the partition is fixed at tab creation, so an identity cannot be
attached to an existing tab without a destructive reload; (c) bind failure is
**fail-closed** (§8.3), which the spike patch currently is not; (d) ephemeral
identities are `in_memory=true`. These are notes for P5's drafting surface;
the freeze is P5's and is gated on HG-21.

## Reversal

New written evidence (a failing runtime row from HG-21, or a later upstream
change that removes `CreateForFixedStoragePartition`) plus a new ADR. The
decision register row is never silently edited. If F1/F2/F3 fire, the
recommended path is the T9 fallback design
(`docs/spike-identity/fallback-design.md`), recorded in a new ADR — **the
number 0042 is never reused**.

## Disposition (2026-09-08, orchestrator)

Recorded by P5-T0. P4 *reported* two conflicts rather than resolving them
(extension-chokepoint cap; `is_in_memory` GN-vs-CHECK divergence). The
orchestrator has now RULED. This section records the rulings verbatim; it does
not relitigate them. A third ruling (HG-25 pre-v1 evidence exemption) is
recorded here for a single audit home.

1. **Extension-chokepoint cap conflict** (P4 census est. 8 files vs §1.2 cap 2):
   **cap stands** — `guard.mojom` is designed so the GuardLedger/Guard consult
   funnels through the ONE upstream dispatch chokepoint (per §1.12/§12.5
   "extension dispatch funnel" and the assumption-suite row); all guard logic
   lives in `//xr`; the 8-file census estimate becomes a binding *redesign
   constraint* on P21 (and §12.5's upstream-PR-or-delete is the escalation path,
   not a cap bump).

2. **`is_in_memory` GN-vs-CHECK divergence** (P4 finding): **runtime reality
   governs contracts** — Vault/Ephemeral semantics in fakes+vectors assert
   "zero persistent *data* writes" (directory skeleton tolerated), §11.4 probe
   definition per P4 probe-matrix.

3. **HG-25 pre-v1 evidence exemption**: **accepted** — `evidence_check --strict`
   stays scoped P3+; agents never re-author P1/P2 claims.
