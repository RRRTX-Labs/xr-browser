# Perf budgets (generated — P9-T5)

Generated with `--as-of 2026-09-10`. Do not hand-edit; regenerate with `tools/perf_gate.py --report-md`. Budgets transcribed from the pinned plan by `gen_perf_budgets.py`.

Bench: bench, themes apply (40 tokens x 6-case corpus: accept x4, refuse x2) (rig class **trend**)

| metric | value | budget | delta % | verdict | owner | plan |
|---|---|---|---|---|---|---|
| cache_warm_pinned_read_us | 0.13 | 5.0 | -97.4 | MET | @xr/platform | §4 P6 Perf (Resolve() p99 ≤5 µs cached; bench key cache_warm_pinned_read) |
| resolve_cold_us | 10.049 | 200.0 | -94.975 | MET | @xr/platform | §4 P6 Perf (Resolve() p99 ≤200 µs cold) |
| snapshot_apply_us | 1115.524 | 2000.0 | -44.224 | MET | @xr/platform | §4 P6 Perf (snapshot apply ≤2 ms; bench key snapshot_apply_40, normalized by the comparator) |
| theme_apply_us | 155.2 | 100000.0 | -99.845 | MET | @xr/platform | §4 P8 Perf (theme apply ≤100 ms) |
