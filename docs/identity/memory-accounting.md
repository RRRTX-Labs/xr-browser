# Per-identity memory accounting (P14-T10)

Status: the attribution MODEL is shipped + tested
(`xr-core/identity/core/attribution.{h,cc}`, `tests/test_attribution.cc`).
NO real MB/percent numbers exist anywhere in this repo for identity
memory — the real-rig halves are NOT-RUN (below) and no surrogate is
labelled as a measurement (the grep audit lives in the phase report).

## The model

* Exclusive processes attribute fully to their identity.
* **Shared processes split EVENLY** across the identities served — a
  documented approximation. The alternative (full RSS to every identity)
  is the double-count lie: Σ attributed would exceed the measured total,
  and the sum-identity law (`SumWithinTotal`) exists to redden exactly
  that (the planted double-count is `test_attribution.cc` §4).
* The `(unattributed)` row — browser chrome, GPU, network service, and
  memory no sample explains — closes the table EXACTLY against the task
  manager's measured total: what the user sees sums to what they measured.
* **Fail-closed**: samples that contradict the total (Σ samples > total)
  yield NO table — `attribute` answers `kRejected` and the manager page
  shows "attribution unavailable", never a plausible-looking wrong table.

Invocation: `identity_host attribute '{"samples":[{"pid":1,"rss_kb":1000,
"serves":["xr:…"]}, …],"total_kb":3000}'`.

## The budgets (generator-owned, never MET here)

The plan's `idle-identity overhead ≤ 40 MB` and `window open +6 %` budgets
are perf-budget ROWS owned by the generator (`rig_class: trend`); the
real-rig measurements are P34's rig lane —
`docs/qa/browser-harness.md` records the method. The comparator's refusal
to report rig numbers from this sandbox stays armed by its own negative.

## Feeds

P34 perf + the `xr://identities` manager page's per-identity stats (T7).
