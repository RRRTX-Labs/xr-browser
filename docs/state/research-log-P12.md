# docs/state/research-log-P12.md — XR cosmetic filtering + scriptlet seam

Law (inherited): each item cites `path:line@pin` or reads
`UNVERIFIED (deferred to <where>)`. Never assert from memory where an
artifact settles it. Sandbox facts are recorded per item where they matter.

## T2 — cosmetic.mojom + blob-cache + fuzz

- **D1 — mojom interface choice.** Cosmetic lands as a NEW ninth frozen
  `xr-core/mojom/cosmetic.mojom`, not an extension of `shield.mojom`.
  Reasons (ADR-0048, PROPOSED — ratification is a human act, RFC-0001
  stays DRAFT): shield.mojom is frozen (§1.11) and its fail law
  (fail-CLOSED, network) is the deliberate opposite of cosmetic's
  (fail-OPEN, "render the page unstyled"); `CosmeticScope.embedder_site`
  is REFUSED when non-empty so "key on the top-level site" is
  structurally impossible. `tools/owners_sync.py --check` stays green
  (the mojom dir is already S0 + RFC-gated).
- **D2 — generator coverage proved not hoped.** `tools/tests/
  test_mojom_coverage.py` discovers every `xr-core/mojom/*.mojom`
  interface and FAILs if any is absent from `tools/mojom_fuzz_gen.py`'s
  inputs (12 hosts: activity-log, commands, downloads, guard, identity,
  policy, renderer/cosmetic, route-manager, settings, shield, themes,
  vault). A new interface unmapped to the fuzzer is now a build failure,
  not a review note.
- **D3 — fuzz never-accept law.** `xr-core/renderer/cosmetic/tests/
  test_cosmetic_fuzz.cc` (≥600 s, seeded, ≥min-iters or FAIL) wired as a
  FIFTH `tools/fuzz_fleet.py` target (`cosmetic-core`); the corpus seeds
  (51) ride `tools/seed_corpus.py --check` (127 seeds total). Empty-run
  is a negative (`tools/negatives/p12_t2.sh`).
- **D4 — blob-cache contract.** `docs/renderer/blob-cache.md` records the
  network-service invariants (identity-partitioned keys, bounded entries
  + bytes, never shared across identities, invalidated by the monotonic
  `apply` version — cited to P11 `shield/core/apply` and the P4/P6
  partition seam). The derivable half (key derivation, size accounting,
  oversized ⇒ typed refusal, stale/expired ⇒ no work) are tests, not
  prose.

## T5 — exception interplay (one scope object, atomic)

- **D5 — parity divergence found and fixed.** The matrix case
  `matrix-blob-embedder-key-ignored` diverged at generation: the C++
  host's blob-check compares exactly `site` + `identity_class` from
  `frame_scope` ("the embedder is not an input to this comparison
  anywhere", `core/scope_key.h`), the Python fake compared the whole
  frame dict. The host's law wins; `fakes/cosmetic.py` fixed and
  byte-parity re-verified.
- **D6 — the four laws pinned as vectors.** 249 committed cases; the
  ≥40-property matrix lives in `tools/cosmetic_vectors_matrix.py` and is
  checked by `tools/cosmetic_scope_single_check.py`: embedder-shields-down
  must not extend to a cross-site frame (embedder REFUSED); a frame's
  exception must not reach the embedder (frame-site key separation,
  constant per-identity partition); same-site/different-identity ⇒
  different key-set (hex AND partition distinct); eviction for one
  identity never serves another (identity-exclusive partition).
- **D7 — two planted negatives.** `tools/negatives/p12_t5.sh`:
  split-brain (private exception store ⇒ red via the single-scope-object
  grep) and the naive optimization (key on the embedder ⇒ DRIFT via the
  parity harness). Both re-proven red; N 132 → 134.
- **D8 — cosmetic ledger.** `## cosmetic exception ledger rows` (empty at
  ship) in `docs/limitations.md`; checked by
  `tools/exception_ledger_check.py` — same scope grammar as shield,
  monotonic expiry vs `--as-of` (never `date.today()`), and a cosmetic
  row must have a matching shield row (the one-object law).

## T7 — perf budgets + the bench

- **D9 — uBO DOM-poll reference: UNVERIFIED.** `cosmetic_dom_poll_cost_us`
  is a browser-side `reference` row whose source cite must name the uBO
  measurement used. No such measurement exists in this repo's ledger, so
  the row's `plan_cite`/`note` say UNVERIFIED rather than inventing a
  number — the trend rig may never assert it, and the farm must supply
  the citation before the reference row can ever emit MET.
- **D10 — surrogate law in perf_gate.** A `cosmetic_*` row without
  `surrogate:true` is REFUSED, and every surrogate is pinned NEUTRAL
  (never MET) — `tools/negatives/p12_t7.sh` keeps both red. The
  committed rows (`cosmetic_keyset_build_ms` ~2 ms vs 50 ms sustain;
  `cosmetic_generic_set_rules` 33) are surrogate/model, trend-rig only.

## mojom RFC status

- RFC-0001 "frozen-mojom amendment (ninth interface, cosmetic.mojom)" is
  DRAFT; ADR-0048 is PROPOSED. Approval is a human act (HG-26 class) —
  the S0/CODEOWNERS machinery stays green either way, but the interface
  must not be treated as ratified copy until a human sets APPROVED.
