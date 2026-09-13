# Shield engine parity — documented divergence classes (P11-T8)

The T8 parity gate (`tools/shield_parity.py`, corpus
`xr-core/shield/tests/corpus/parity-corpus-v1.json`, ≥1,500 cases) holds
the vendored adblock-rust shim (`xr-core/shield/engine/lib.rs`) and the
v1 reference matcher (`shield/core/fake_engine.h` TableEngine + its
Python mirror) to the plan's bands: **agreement ≥98% (±2%), false
positives ≤0.5%** of expected-allow cases, provenance ≥98%.

Where the two engines could diverge by DESIGN, the divergence is either
eliminated in the shim (enforcement) or recorded here as a class with its
direction, blast radius, and corpus pin. Nothing in this file weakens a
band; classes tagged *enforced* are pins the parity run verifies, and
classes tagged *reported* are honest gaps with a named owner lane.

| class | what | status | direction / consequence |
|---|---|---|---|
| D-1 | v1 `redirect`/`replace` rules carry a resource NAME, no body. adblock-rust's `$redirect=` needs loaded resources. | **enforced (mapping)** | The shim compiles redirect/replace rules as their bare filter and maps a hit back to action 2/3 + the resource name through its side table — the same observable as TableEngine's `kRedirect`/`kReplace` (a labeled block at the network layer). Actual body substitution stays a documented v1 limit (bundle format carries no bodies). Corpus classes `redirect`, `replace`. |
| D-2 | ABP `$domain=` matches SUBDOMAINS of the option value; the v1 law (`fake_engine.h`) is EXACT set membership against the request's registrable_domain or host. | **enforced (shim-side)** | The shim deliberately does NOT emit `$domain=`; it keeps `domains`/`exclude_domains` in a side table and re-checks exact membership against the FFI-passed rd/host after every engine hit. A rule whose options fail does not apply. Corpus classes `domains-rd`, `domains-out`, `exclude-rd`, `exclude-host`, and the `option-law-pin` class (an ABP-semantics match that v1 must NOT produce, plus the exact-host case it must). |
| D-3 | First/third-party dimension: ABP keys `$third-party` off the initiator; the v1 FFI carries no initiator. | **moot in v1** | The v1 grammar has no third-party option (`$` in filter text is a bundle-compile refusal), so the shim's first-party source assumption (`Request::new(url, url, …)`) is exact for every rule the format can carry. Revisit when the FFI grows an initiator (network-service seam). |
| D-4 | Rule recovery of optimizer-FUSED filters is not guaranteed (adblock-rust may fuse filters and drop `raw_line`); duplicate filter text across rules recovers last-wins. | **reported** | An unidentified hit still blocks (action correct) but carries the `u32::MAX` sentinel indices; the C++ adapter bounds-checks and leaves `rule_id` empty rather than guessing — a BlockEvent without rule identity, never a wrong identity. Parity corpus cases are single-rule bundles where fusion cannot occur; product bundles measure the unidentified-hit rate in the hosted bench (0 on the 20k-rule bench corpus by construction: distinct filter texts). Owner: farm-lane product bundle run. |
| D-5 | Allow-only rules (exception with no paired block filter): TableEngine reports an allow HIT (`rule-allowed`, engine_decision true); adblock-rust checks exceptions only after a block match, so the shim reports no-opinion. | **reported (action-neutral)** | Final verdict ACTION is `allow` in both lanes — only provenance differs (`rule-allowed` vs `no-match`). Corpus class `allow-only` carries the `provenance-divergence-D5` tag: the real lane compares action, skips provenance. Consequence: no BlockEvent/ledger difference (allow verdicts emit no block event); the `xr://shield` recent-events view shows `no-match` instead of `rule-allowed` for such URLs under the real engine. Upstream-first (§12.7): no adblock-rust change requested — this is ABP-conformant behavior; the v1 TableEngine's eager-allow reporting is the outlier and stays (frozen golden vectors pin it). |
| D-6 | 1,000-site live capture set (plan L739: FP ≤0.5% also measured on a real-traffic corpus). | **NOT-RUN (HG-31)** | Needs the farm browser + capture rig (no browser exists in any lane yet). Method committed in `docs/qa/browser-harness.md` §Shield capture set so the farm lane executes it verbatim; until then the FP band rides the vendored corpus only, and NO claim of live-traffic FP is made anywhere. |

## Lane map

* **local (every run_checks):** generator `--check` (corpus is its
  deterministic output) + fake/TableEngine lane with all bands enforced.
* **hosted (core-hardening `shield-vendor`):** shim's first compilation,
  real-engine bench (≥50k decisions — the product-path floor the sandbox
  fake lane cannot honor for `filter_decision_p99_ms`), and the real
  lane of this corpus with the same bands enforced.
* **farm (NOT-RUN, HG-31):** reference-rig certification of the ≤1ms /
  ≤80MB reference rows and the D-6 capture set.

## Rule of this file

A new divergence discovered at runtime is added here WITH its corpus pin
before the parity band is re-run; a divergence that cannot be pinned or
enforced is a stop-and-report condition (brief law), not a band
adjustment.
