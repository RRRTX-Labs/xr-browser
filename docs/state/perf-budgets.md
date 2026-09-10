# Perf budgets (generated — P9-T5)

Generated with `--as-of 2026-09-10`. Do not hand-edit; regenerate with `tools/perf_gate.py --report-md`. Budgets transcribed from the pinned plan by `gen_perf_budgets.py`.

Bench: canary (rig class **trend**)

| metric | value | budget | delta % | verdict | owner | plan |
|---|---|---|---|---|---|---|
| resolve_cold_us | 999999.0 | 200.0 | 499899.5 | MISSED | @xr/platform | §4 P6 Perf (Resolve() p99 ≤200 µs cold) |
