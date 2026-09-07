# Reserved ADR numbers

| Number | Reserved for | Status | Set by |
|---|---|---|---|
| 0042 | **P4 identity-seam ADR** — "identity seam": primary per-WebContents `StoragePartitionConfig` model vs. `BrowserContext` fallback, papercut census result, patch estimate (Plan §4 Phase P4, tasks T8/T9; Plan §12/§15 inputs; DR-25) | **IN USE** — `docs/adr/0042-identity-seam.md`, status PROPOSED (ratification HUMAN-GATED, HG-23). The reservation is consumed; the number is never reused for another topic. | ADR-0002, 2026-09-07 · used 2026-09-07 (P4) |

**Rules**

1. No ADR may be allocated number 0042 for any other topic while the
   reservation is in force.
2. When P4 executes, its ADR lands as 0042 *if* the numbering sequence has
   reached that vicinity; if earlier ADRs have consumed the sequence past a
   natural 0042 slot, P4's ADR takes the next free number **and this
   reservation row is updated in the same PR** (with `Register-Change`
   discipline not required — this file is not the register — but with an
   ADR reference).
3. If P4 falsifies the seam and ships the fallback (Plan P4-T9), the
   fallback decision is still recorded in ADR-0042; the number is
   never reused for a new topic.
