# The network-service cosmetic blob cache (P12-T2)

This file is the design record for the per-page **compiled** cosmetic blob
cache that lives in the network service, per Plan §8 line 749: *"per-page
rule blob cache in network service (avoid re-IPC per frame; identity-aware
keys)"*. It is written as invariants-plus-tests, not prose-as-wish: every
derivable property below either has a committed test today or is marked
`NOT-RUN (method: …)` with the exact harness that will prove it once the
browser process exists.

The renderer never compiles a blob; the network service compiles once
(`xr-core/renderer/cosmetic/core/keyset.h`, law 2) and serves the
compiled-for-this-page subset. The renderer-side cache seam is
`xr-core/mojom/cosmetic.mojom` (ADR-0048); this doc owns the network-service
half of that seam.

## 1. The keys: identity-partitioned, site + trust aware

The cache slot key is `(identity, site, trust)` — the same tuple the policy
cache already settled on in `xr-core/policy/core/cache.h` `PolicyCacheKey`
(lines 28-39) and that the shield exception scope extends in
`xr-core/shield/core/scope.h` `ExceptionScope` `{identity, site, workspace}`.
The cosmetic derivation is `xr-core/renderer/cosmetic/core/scope_key.h`:

- `DeriveScopeKey()` hashes the FRAME'S registrable domain — **never the
  embedder's top-level site** — with the identity, trust class, navigation
  class and document-url class (canonical field order pinned by the golden
  vectors).
- `IdentityPartition()` computes the identity→partition hash an eviction path
  uses to drop one identity's whole partition without re-deriving any key.

Two hard invariants follow, and both are tests, not assurances:

- **Cross-identity leakage is a security failure.** A blob evicted for one
  identity can never be served to another: the partition id rides alongside
  the key (`scope_key.h` `ScopeKey.partition`), and `core/blob.cc`
  `ParseBlob` refuses a `scope` that does not match the caller's own frame
  scope (`BlobError::kScopeMismatch`). Proven today by golden vectors
  (`docs/contracts/vectors/cosmetic-v1.json`) replayed byte-for-byte across
  the C++ host and Python fake (`tools/cosmetic_vectors_check.py`).
- **The embedder can never become an input.** A non-empty `embedder_site`
  refuses key derivation (`ScopeError::kMalformedSite`, `core/scope_key.cc`
  lines ~98-102 — "we noticed you tried to key on the top-level site" is how
  a leak survives a refactor). The planted negative
  `tools/negatives/p12_t2.sh` `embedder_scope_key_refused` keeps it red if
  this ever regresses.

Why the frame site and not the top-level site: a cross-site frame would
otherwise inherit the embedder's cosmetic rules, which is the exact
shields-down extension the P12 brief forbids (T5's OOPIF matrix asserts
"embedder-shields-down must not extend to a cross-site frame").

## 2. Bounds and accounting (oversized ⇒ typed refusal)

The cache charges real bytes, computed once by the compiler so the cache and
the benchmark cannot disagree (keyset.h law 3):

- per key set: `kMaxKeySetRules 4096`, `kMaxKeySetBytes 1 MiB`
  (`xr-core/renderer/cosmetic/core/keyset.h` lines 39-40);
- per rule contribution: `RuleBytes()` — the serialized fields the cache
  actually stores, not `sizeof`.

An oversized key set is **refused as a whole** with `KeySetError::kTooManyRules`
/ `kTooManyBytes` (`core/keyset.cc`), never silently truncated. The blob-level
analogues (`BlobError::kTooManyRules`, `rule-too-large`) are exact refusals
too. Proven today by `core/tests/test_keyset.cc` `TestByteBudgetIsEnforcedDuringTheWalk`
and the fuzz target's byte-accounting invariant
(`renderer/cosmetic/tests/test_cosmetic_fuzz.cc`).

## 3. Staleness and expiry (stale/expired ⇒ no work)

A compiled blob is valid for the bundle whose rules produced it. Invalidation
is owned by the bundle's monotonic apply version, per the P11 law in
`xr-core/shield/core/apply.h` — `bundle_version` is monotonic per `bundle_id`
(a downgrade is refused) and the previous active slot becomes
**last-known-good (LKG)** when a newer bundle applies.

On the network-service side:

- when a bundle with a newer `bundle_version` applies, every cache slot bound
  to that bundle's scope is **invalidated** — never reused, because the rules
  that compiled them are no longer the active bytes;
- a slot hit whose `generated_epoch` (`core/blob.h` `CosmeticBlob.generated_epoch`,
  an integer token the producer signs, not a wall clock) is older than the
  LKG bundle's version is **treated as absent**, which routes through the
  degrade truth table's `kBlobMissing` row → `kGenericSetOnly`, i.e. *no work
  beyond the conservative generic set*.

The whole wiring is "stale ⇒ no work", never "stale ⇒ guess". An eviction
drops the LKG slot LAST (LKG is the recovery slot `shield/core/apply.h`
already keeps for rule application; the cache reuses it rather than keeping
a second one and drifting).

There is deliberately **no timestamp in the key**. Expiry decisions never
read the wall clock — a cache that expires by `now()` is a date-invariance
violation in the gate's terms, and `tools/wall_clock_lint.py` watches the
rewriteable seam if any future module is tempted.

## 4. Eviction and the LKG interaction

Eviction is by `(identity, trust)` partition, independently of site, so a
whole identity can be dropped (profile destroyed, shields reset) without
walking every site key:

- `EvictIdentityPartition(identity, trust)` drops every slot whose partition
  is `IdentityPartition(identity, trust)` — this is the method
  `cosmetic.mojom` exposes, and it must never serve a survivor back to a
  different identity (invariant 1).
- The LKG bundle slot is exempt from partition eviction (it is the recovery
  slot), which is the one time a cosmetic entry may outlive its identity
  *entry* but never its identity *boundary*: an LKG blob still carries its
  own scope and is re-validated against the requesting frame on every hit
  (`kScopeMismatch` otherwise).

The three-way degrade proof (`docs/renderer/cosmetic.md`, P12-T5) asserts the
same property at the renderer edge; this file is the network-service half of
that proof.

## 5. Farm row: the measurement that is NOT made here

This sandbox has no network service and no browser process. The hit-rate and
occupancy numbers the Observatory shows are:

- **NOT-RUN (method: `docs/qa/browser-harness.md#document-start-p95`)**
  for the p95 document-start add; the cosmetic host already reports
  `blob_cache_occupancy` as the string `"NOT-RUN (network-service side)"`
  (`xr-core/renderer/cosmetic/host_protocol.md`, `page-states`) rather than
  inventing a byte count it does not own.

The farm row that measures hit-rate vs bytes is HG-31 (browser harness) with
the 50-hard-apps spot check over the fixture corpus; the surrogate bench
(`tools/cosmetic_bench.py`, P12-T7) is labeled `surrogate`/`model` in every
report line and never presented as the browser measurement.
