# Perf budgets (generated — P9-T5)

Generated with `--as-of 2026-09-10`. Do not hand-edit; regenerate with `tools/perf_gate.py --report-md`. Budgets transcribed from the pinned plan by `gen_perf_budgets.py`.

Bench: trend-rig benches (policy resolve + themes apply + shield decision/apply) (rig class **trend**)

| metric | value | budget | delta % | verdict | owner | plan |
|---|---|---|---|---|---|---|
| cache_warm_pinned_read_us | 0.121 | 5.0 | -97.58 | MET | @xr/platform | §4 P6 Perf (Resolve() p99 ≤5 µs cached; bench key cache_warm_pinned_read) |
| resolve_cold_us | 10.503 | 200.0 | -94.749 | MET | @xr/platform | §4 P6 Perf (Resolve() p99 ≤200 µs cold) |
| snapshot_apply_us | 1383.273 | 2000.0 | -30.836 | MET | @xr/platform | §4 P6 Perf (snapshot apply ≤2 ms; bench key snapshot_apply_40, normalized by the comparator) |
| theme_apply_us | 157.6 | 100000.0 | -99.842 | MET | @xr/platform | §4 P8 Perf (theme apply ≤100 ms) |
| fakecore_decision_p99_ms | 3.50664 | — | — | RECORD-ONLY |  | RECORD-ONLY |
| list_apply_ms | 230.109 | 1500.0 | -84.659 | MET | @xr/platform | §4 P11 Perf (list apply ≤1.5 s background) |
| rss_structures_mb | 60.223 | — | — | RECORD-ONLY |  | RECORD-ONLY |
| fake_decision_p99_ms | 43.87867700006609 | — | — | RECORD-ONLY |  | RECORD-ONLY |
