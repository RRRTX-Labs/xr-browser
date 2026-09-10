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
