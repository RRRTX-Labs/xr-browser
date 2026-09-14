# XR Shield v1 — perf: what was measured, on which rig class, and what the farm must measure (P11-T7)

Bench: `build/qa/perf/shield_bench.py` driving `build/qa/perf/shield_bench.cc`
(C++ binding: `DecideMatch` over the shield core — TableEngine by default,
the vendored adblock-rust through the FFI shim with `--engine real` on the
hosted lane) plus the PYTHON fake binding (`xr-core/fakes/shield.py
decide_match`) over the SAME deterministic synthetic corpus (≥50k requests;
no RNG, no wall clock in the data). Verdicts are `tools/perf_gate.py`'s
job; rows merge into the committed trend artifact via `--merge-trend`.

## 1. The rig-class law (P9, unchanged)

This sandbox is a **trend** rig; the GH runner is trend-class too. A
`reference`-class budget (browser-side, calibrated rig) is NEVER asserted
on a trend rig — no unauthorized `MET` on reference rows, no fabricated
history, no compressed 14-day series. `rss_structures_mb` carries no
budget row at all ⇒ RECORD-ONLY.

## 2. The three plan budgets (wired into the GENERATOR)

`tools/gen_perf_budgets.py` derives `build/qa/perf/perf-budgets.json` from
the plan text (`docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md`
§11.7 + §4 P11) — the budgets are generated, not hand-edited:

| metric | budget | assert class | surface |
|---|---|---|---|
| `filter_decision_p99_ms` | ≤ 1 ms/request | trend | core-side |
| `list_apply_ms` | ≤ 1500 ms (background apply) | trend | core-side |
| `memory_default_mb` | ≤ 80 MB (default list sets) | **reference** | browser-side |

## 3. Measured numbers (real runs only — transcripts cited)

Sandbox (trend rig, 2026-09-13; `evidence/P11/logs/t7-shield-bench-sandbox.txt`,
`evidence/P11/logs/t7-perf-gate-merged.txt`, `docs/state/perf-budgets.md`):

* fake-binding decision p50 2.419913 / p99 3.506640 / p99.9 4.636091 ms —
  RECORD-ONLY row (`fakecore_decision_p99_ms`; a Python-mirror number on a
  shared sandbox rig proves nothing against the 1 ms core-side budget and
  is never asserted);
* `list_apply_ms` median 222.317 / worst 230.109 vs 1500 ⇒ MET
  (−84.659 %);
* `rss_structures_mb` 60.223 — RECORD-ONLY;
* `perf_gate`: 8 rows, 0 MISSED, 0 NEUTRAL (MET ×5 incl. the shield rows,
  RECORD-ONLY ×3).

Trend artifact: `docs/state/bench-trend.json` carries the FIRST REAL
entries (sandbox + runner rows, rig-class labeled). The 14-day trend lane
is defined (daily `perf_gate --report-md` merges); its certification series
is farm work — human gate HG-39, `evidence/P11/human-gates.md`. No entry
predates its measurement.

The `shield-vendor` lane (core-hardening workflow) re-measures on the
runner with the REAL engine (50k/20k corpus; rig class trend, labeled):
its numbers are cited machine-resolvably via `ci-run` rows in
`evidence/P11/evidence.json` — not transcribed here as prose.

## 4. What the farm must measure (reference class — HG-31 / HG-39)

1. `memory_default_mb` ≤ 80 MB with the DEFAULT list sets loaded, on the
   calibrated rig (the only place this budget may turn MET);
2. end-to-end per-request filter p99 through the real network-service seam
   (the sandbox measures the core call, not the browser path);
3. the 14-day certification series (`--rig reference`, daily cadence) that
   retires HG-39;
4. live-traffic FP capture feeding the parity bands (HG-31, method:
   `docs/qa/browser-harness.md` §Shield capture set).

Runbook: `docs/qa/browser-harness.md` §Farm runbook — execute verbatim; no
new decisions are needed at the rig.
