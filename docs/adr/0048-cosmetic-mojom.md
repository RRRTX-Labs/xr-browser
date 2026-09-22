# ADR-0048: the cosmetic.mojom request surface, and the renderer-cache boundary it crosses

- **Status:** PROPOSED (drafted by the P12-CLOSE coding agent; ratification
  rides HG-26's queue — agents draft, humans decide, L24)
- **Date:** 2026-09-19
- **Deciders (humans):** Platform lead + Security lead (identity partitioning
  and mojom surface are S0-adjacent, L13 dual review)
- **Plan anchor:** Plan §8 line 749 (P12-T2): "request compiled cosmetic
  key-set for (site, identity-trust) via mojom" + "per-page rule blob cache in
  network service (avoid re-IPC per frame; identity-aware keys)"; the
  `docs/rfcs/RFC-0001.md` companion covers the freeze/surface procedure.

## Context

P12-T1 shipped the cosmetic **core** (selector / keyset / blob / scope-key /
degrade / style) behind `renderer/cosmetic/host_protocol.md` — a stdio test
protocol, not a browser boundary. P12-T2 connects that core to the browser
across two surfaces the plan names precisely: the renderer asks the network
service for a **compiled key-set**, and the network service keeps a
**per-page blob cache** whose keys are `(site, identity-trust)`.

Two decisions are load-bearing and must be recorded, not assumed:

1. **The mojom surface is a new interface (cosmetic.mojom), not an extension
   of shield.mojom.** Rationale, in order of weight:
   - *Contract discipline.* shield.mojom is frozen (`FROZEN.yaml`, §1.11).
     Adding cosmetic request/response shapes there would be a frozen-contract
     amendment touching §1.5-listed consumers; filing the new surface as its
     own freeze unit keeps the amendment blast radius zero.
   - *Ownership.* The network-layer Shield decides *blocking*; the
     renderer-side cosmetic feature decides *hiding*. Their consume points
     (network service vs document-start Blink hook) and fail laws differ —
     Shield blocks fail-CLOSED (`docs/contracts/shield-v1.md`), cosmetic
     fails OPEN toward "render the page unstyled" (`core/degrade.h`, recorded
     in `docs/contracts/cosmetic-blob-v1.md`). Merging them invites a reader
     to inherit the wrong fail law.
   - *Budget.* `core/keyset.h` pins `kMaxKeySetRules 4096` / `kMaxKeySetBytes
     1 MiB` and `core/scope_key.h` pins `kMaxSiteLen 256` /
     `kMaxIdentityLen 128`; the `.mojom` carries these as `// budget:` notes so
     contract and budget cannot drift, which is exactly the house style of the
     other ten files.

2. **The cache is identity-partitioned, bounded, and never shared.** The
   network-service blob cache takes the same `(identity, site, trust)` key the
   policy cache already settled on (`policy/core/cache.h` PolicyCacheKey,
   lines 28-39) and that `shield/core/scope.h` ExceptionScope extends
   (`{identity, site, workspace}`); the identity→partition hash matches
   `renderer/cosmetic/core/scope_key.h` `IdentityPartition()`. That is the
   P4/P6 partition seam this feature must not reopen.

## Decision

1. **`xr-core/mojom/cosmetic.mojom` declares `interface Cosmetic`** with the
   request/response surface the stdio protocol already exercises: compile a
   per-frame key-set (`GetCompiledRuleSet`), cache/evict compiled blobs and
   identity partitions (`CacheCompiledBlob` / `EvictCompiledBlob` /
   `EvictIdentityPartition` / `CacheOccupancyBytes`). Every size is a `//
   budget:` comment sourced from the live core headers, not a new number.
   Banned-surface laws (R1-R8) pass under `tools/mojom_lint.py`.
2. **The request frame is `CosmeticScope`** — frame site, frame identity,
   trust class, navigation class, document-url class, and an `embedder_site`
   field that is **REFUSED when non-empty** (`ScopeError::kMalformedSite`).
   The key is derived from the FRAME's site only; the negative fixture in
   `tools/negatives/p12_t2.sh` keeps "key on the top-level site" structurally
   impossible (it is also written down in `core/scope_key.cc` lines ~98-102).
3. **`docs/renderer/blob-cache.md` records the network-service cache
   invariants as tests, not prose** — everything derivable (oversized ⇒ typed
   refusal, stale/expired ⇒ no work, eviction-for-one-identity-never-serves-
   another) is asserted; the monotonic bundle-`apply` version from
   `shield/core/apply.h` (bundle downgrade refused, LKG slot) is the
   invalidation trigger, cited `path:line`.
4. **The mojom surface is a freeze-touching change, so it travels under the
   amendment procedure** of `docs/contracts/contract-amendment-rfc.md`: the
   new file is committed with the RFC-DRAFT present (`docs/rfcs/RFC-0001.md`)
   and the commit carries `Contract-Amendment: RFC-0001`; approval of that
   RFC is a HUMAN act, which is why this ADR is PROPOSED and the RFC's status
   stays DRAFT in this tree — the coding agent records the fact, never
   self-approves. On the xr-core side the file lands as its own commit, and
   the xr-browser gate `tools/amend_guard.py` sees only warn-only drafting
   (it is human-stamped after a human sets `status: APPROVED`).

## Consequences

- Positive: the renderer can request a compiled key-set without recompiling
  blobs itself (compilation stays in the network service, exactly once —
  `core/keyset.h` law 2); the blob cache gains the identity-aware eviction
  the P4/P6 partition seam already demands; the fuzz coverage test,
  `tools/tests/test_mojom_coverage.py`, makes any FUTURE interface invisible
  to `tools/mojom_fuzz_gen.py` a build failure, not a code review note.
- Negative / cost: one more frozen `.mojom` and one more fleet target
  (cosmetic-core) to keep fresh under the mutation/timebox laws; the binding
  compile remains farm-gated (HG-9/HG-27) exactly like the other ten files.
- Follow-ups: P13 consumes the cosmetic reason codes (`docs/shield/
  reason-codes.*`); P16 takes the mojom-bind fuzz row.

## Reversal

Reopen if: (a) the renderer is shown to need a surface shield.mojom already
covers such that a separate interface duplicates IPC; or (b) the cache key
must include a field this ADR's `CosmeticScope` omits — either case starts a
new ADR and a registry change, never a silent edit, per the Decision Register
discipline (ADR-0002).
