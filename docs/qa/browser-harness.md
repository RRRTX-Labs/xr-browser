# XR browser-test harness (P9-T1) — runner-ready, farm-executed

Status: **runner-ready-fake-only** (source + lint real; compile/run = farm).
Owner tool: `tools/browser_test_lint.py`. Closing phase for the compile/run
half: P10 (browser build exists) → HG-31 (farm browser E2E).

## What this is

`xr-core/test/browser/` ships the C++ fixtures future phases attach their
`browser_tests` to, so no phase invents fixtures mid-flight (the brief's
"each track stops inventing fixtures mid-flight"). The fixtures are:

| Fixture | Purpose | Upstream attach point (at pin `d04cdb24…`) |
|---|---|---|
| `fixtures/xr_browser_test_base.{h,cc}` | one base for every XR browser test | `content/public/test/browser_test_base.h:64` (`BrowserTestBase`), `:83` (`SetUpOnMainThread`), `:90` (`SetUpCommandLine`), `:133` (`SetUpInProcessBrowserTestFixture`) |
| `fixtures/multi_identity_window.{h,cc}` | second window bound to a distinct identity | `content/public/test/browser_test_utils.h` |
| `fixtures/ephemeral_partition.{h,cc}` | disposable identity, zero-residue close | `content/public/browser/storage_partition.h` |
| `fixtures/network_stub.{h,cc}` | stubbed resolver + pinned network state | `net/dns/mock_host_resolver.h:69,185` (`AddRule`); `net/base/mock_network_change_notifier.h:19` |
| `fixtures/frozen_clock.{h,cc}` | fixed `TickClock` (frozen-clock law, browser side) | `base/time/default_tick_clock.h:19` |

## Why the compile half is farm

This sandbox has no Chromium checkout and no gn/ninja. `BUILD.gn` targets
(`xr_browser_test_fixtures`, `xr_browser_tests`) are wired for the farm's
`gn gen && ninja -C out/… xr_browser_tests`; the P9 gate's `--syntax` pass
attempts `g++ -fsyntax-only` and **SKIPs visibly** with the missing-headers
reason. Nothing here claims a compile result it did not produce.

## The lint laws (enforced for real, in `run_checks`)

1. Every `XR_*_TEST` uses a fixture from `test/browser/fixtures/`.
2. Every test file has an owner in `test/browser/OWNERS.yaml`.
3. No `GTEST_SKIP()` on a test path — a security assertion that cannot run
   fails loudly on the farm (plan §11.2: corrupt-prefs/corrupt-store
   fixtures are mandatory; a skip would silently pass them).
4. Empty-run law: a browser-test tree with zero `XR_*_TEST` files is a
   FAILURE, not a pass.

Negative fixtures (in `tools/tests/test_p9_browser_lint.py`) prove each law
bites, and the whole tool is registered as a canary in the negative gate.

## Farm runbook (HG-31)

```bash
# On a machine with the Chromium checkout at the pinned rev:
gn gen out/xr --args='…xr branding…' && ninja -C out/xr xr_browser_tests
out/xr/xr_browser_tests --gtest_filter='Xr*'
```

## P11-T7: shield perf — the reference-rig lane (NOT-RUN, rides HG-31)

Three lanes measure the shield budgets; only the farm lane can certify
the REFERENCE-class rows (perf_gate's rig-class law forbids a trend rig
from ever emitting MET for them):

| lane | rig class | engine | rows it may rule on |
|---|---|---|---|
| sandbox (`build/qa/perf/shield_bench.py`, committed trend file) | trend | fake (TableEngine, linear scan) | `list_apply_ms` (≤1500ms) MET; `fakecore_decision_p99_ms`, `rss_structures_mb`, `fake_decision_p99_ms` (sampled n=2000) RECORD-ONLY |
| hosted (core-hardening `shield-vendor`) | trend (GitHub runner) | real (vendored adblock-rust shim) | `filter_decision_p99_ms` (≤1ms trend row), `list_apply_ms`; ≥50k decisions — the plan floor the fake lane cannot honor for the product path |
| farm (this section) | reference (calibrated rig) | real | `memory-default` (≤80MB REFERENCE row), reference certification of `filter_decision_p99_ms`, D-6 capture set |

The sandbox fake-engine decision row is record-only BY LAW: a 20k-rule
linear scan on a shared sandbox cannot honestly assert the ≤1ms product
budget — the product path is the indexed real engine on a calibrated
rig. Farm runbook (when the browser + rig exist):

```bash
# Reference rig, pinned hardware class, real engine product bundle:
python3 build/qa/perf/shield_bench.py --repo . --engine real \
  --shim-dir <cdylib dir> --rig reference --iters 50000 --rules 20000 \
  --merge-trend   # writes the reference trend file the gate consumes
python3 tools/perf_gate.py --repo . --bench docs/state/bench-trend.json \
  --check --as-of <frozen date>
```
