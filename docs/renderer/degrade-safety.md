# Degrade safety, asserted three ways (P12-T5)

Cosmetic filtering must degrade safe: refusing to hide an ad must never refuse
to render a page. That requirement is easy to state and easy to violate at five
different call sites (the blob loader, the key-set builder, the DOM mutation
callback, the exception check, the flag check), which is why the single truth
table in `xr-core/renderer/cosmetic/core/degrade.cc` exists and why this page
records the assertion strategy. The security requirement is **never merged into
one claim** — the property is proven three independent ways, and a regression
in any one of them is a distinct failure.

## The table (one place decides)

`DegradeCondition × DegradeOutcome` is DATA in `core/degrade.cc`, exercised
through `cosmetic_host`'s `degrade-apply` method and pinned by the golden
vectors (every condition named once; an unknown condition is refused
`unknown-degrade-condition` rather than defaulted). The default is the page:
the table resolves toward "render the page unstyled", the deliberate opposite
of the network layer's fail-CLOSED rule
(`docs/contracts/cosmetic-blob-v1.md` records the divergence so a future
reader does not "fix" it).

The two laws every degrade row feeds:

- **no rules, no work** (`ShouldInstallObserver`): zero rules ⇒ zero emitted
  style and no mutation observer — the property that keeps the default-off
  state byte-identical to today's product;
- **generic set always-on but still flag-gated** (`GenericSetApplies`): a
  shields-down must not leave the page half-styled, so the generic set applies
  independent of the per-site exception bit, but the feature flag still gates
  the whole call site (off ⇒ nothing active).

## The three ways

1. **Static — `tools/blink_guard_lint.py`.** Every injected call site in the
   `blink_seams/0300-cosmetic-document-start` patch must be behind an
   `#if defined(XR_…)` guard. A hook compiled into a build where the feature
   is off means the flag gates the CALL but not the CODE; the lint reports
   `hooks: 1, guarded: 1, unguarded: 0` and reddens on an unguarded hook with
   a planted-negative proof.
2. **Core-level — "no blob / no rules ⇒ zero emitted bytes + bounded cost".**
   `core/keyset.cc` `RuleBytes()` charges the real serialized bytes and the
   1 MiB / 4096-rule budget is refused as a whole (`kTooManyBytes` /
   `kTooManyRules`), never truncated. `core/degrade.cc`'s `kEmptyRuleSet ⇒
   kNoWork` is asserted in `renderer/cosmetic/tests` and pinned by the vectors
   (the degrade table and the byte accounting are tests, not prose).
3. **Farm runbook — the page-level blank-page property.** Named in
   `docs/qa/browser-harness.md` (blank-page detection over the fixture corpus,
   the 50-hard-apps spot check, the breakage-diff baseline ≤ +0.5 %). This is
   `NOT-RUN (method: docs/qa/browser-harness.md#…)` in this sandbox: no Blink
   build exists here (`gn`/`ninja` absent), and relabeling a model measurement
   as a browser observation is this phase's disqualifier.

## The two planted negatives (kept red)

- `tools/negatives/p12_t5.sh` `cosmetic_split_brain_private_store`: a private
  exception store in the cosmetic surface reddens the single-scope-object
  check — cosmetic must consult the SAME P11 scopes object shield writes;
- `cosmetic_naive_embedder_key`: keying on the top-level (embedder) site
  reddens the byte-parity check (a `DRIFT` a single-implementation test could
  not see) — the naive optimization the P12 brief calls out by name.

Both are re-proven red by `bash tools/run_negatives.sh` (N grown from 132).

## Limits (honesty)

The table and the vectors prove the DECIDER: what the host refuses and what a
well-formed blob/key-set carries. They do not prove what Blink renders.
Page-level, compiled and browser-harness observations are `NOT-RUN` with their
method named, everywhere. The `xr://shield` dev page reports
`blob_cache_occupancy` as the string `"NOT-RUN (network-service side)"` for the
same reason: a number this host does not own would be an invented one.
