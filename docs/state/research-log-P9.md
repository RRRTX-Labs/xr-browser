# Research log — Phase P9 (Stage 1): Test & Benchmarking Infrastructure v1

Each item: cite (`path:line@pin`, a URL + date, or `UNVERIFIED (deferred to
P<n>)`). Nothing relied on is left to memory where a fetch settles it.
Upstream facts were checked at the pin
`d04cdb24d67b081f6cf80200ffc5233f44b61109` (152.0.7977.82) via
`build/upstream/fetch.py` where a checkout exists; where a fact needs a
Chromium checkout this sandbox does not have, it is marked `UNVERIFIED`.

## R1 — Chromium browser-test fixtures (T1)

The five XR fixtures' upstream attach points are recorded in
`docs/qa/browser-harness.md` with `path:line@pin d04cdb24…`:
`content/public/test/browser_test_base.h:64,83,90,133`
(`BrowserTestBase`, `SetUpOnMainThread`, `SetUpCommandLine`,
`SetUpInProcessBrowserTestFixture`), `net/dns/mock_host_resolver.h:69,185`
(`AddRule`), `net/base/mock_network_change_notifier.h:19`,
`base/time/default_tick_clock.h:19`. Anything not found at the pin is not in
the code — the `--syntax` gate SKIPs visibly rather than claiming a compile.

## R2 — Chromium Gold + snapshot pipeline (T6)

`docs/qa/gold-triage.md` records the split: the PNG codec + comparator are
real here; the Gold bridge is the farm `goldctl imgtest` invocation
(HG-37). The in-tree `//skia/gold` / `//ui/gl` state at the pin is
**UNVERIFIED (deferred to the farm, P36 visual-review)** — verifying what
exists in-tree needs a checkout this sandbox does not have.

## R3 — WPT infra (T4)

Current `wptrunner`/`run_ptr_*` status **UNVERIFIED (deferred to P14,
browser farm)** — needs a checkout. What is real here is the delta-bot
contract: `tools/wpt_delta.py` compares two result sets as data and enforces
the §11.12 law (≤0.5% within-tolerance) with committed synthetic fixtures
(`docs/qa/wpt-fixtures/`, 5/1020 vs 6/1020 boundary).

## R4 — axe-core (T7)

Full evaluation in `docs/dependencies/axe-core.yaml` + the live probe
(`registry.npmjs.org`, 2026-09-09/10): version **4.13.0**, license **MPL-2.0**
(file-level, no viral clause), **zero runtime dependencies** (`deps: {}`), 0
advisories, actively maintained (Deque Systems). Decision: axe-core needs a
real DOM; `jsdom` would be a second package (not authorized), so the
in-sandbox lane runs the **AXTree snapshot transform** (documented in
`docs/qa/a11y-contract.md`) and the browser-side `axe_run.mjs` is farm row
HG-31.

## R5 — ClusterFuzzLite (T8) — decision: not adopted

Evaluated and **not adopted**. `build/fuzz/libfuzzer/` ships clang/libFuzzer
entry points for the four cores (CI-side, HG-28); the in-house seeded fuzzers
are the gate (g++ only, run everywhere). CLite was declined because: (a) it
would add a hosted action + a container-registry pull (network) while this
phase's law is zero new hosts; (b) its build_fuzzers/run_fuzzers contract
assumes a gn/ninja Chromium build for browser targets — our cores build via
their own Makefiles, which the fleet already drives. Recorded in
`docs/qa/fuzz.md` (farm rows HG-28/HG-29).

## R6 — pcap/capture options for the leak harness (T3)

`docs/qa/leaktest.md` records the privilege model: `tcpdump`/`libpcap` +
`CAP_NET_RAW` (or root) is required for the capture lane — absent here. The
loopback lane (binds 127.0.0.1 only, no privilege) is the real local test;
`--mode capture` SKIPs visibly (exit 77). Cite: `tools/leaktest.py` (the
loopback guard refuses non-loopback targets).

## R7 — Semgrep + clang-tidy custom checks (T9)

`docs/dependencies/sast-tooling.yaml` records the verdict: **config-only for
clang-tidy** — the two plan rules (no mode-logic outside `//xr/policy`; no
direct pref reads) are already enforced by `tools/mode_lint.py` +
`tools/sast_check.py`, so a custom clang-tidy check is decoration and is not
shipped. Semgrep rules are real files (`build/sast/rules/semgrep/`) with
must-match/must-not-match fixtures; CLI execution is CI-side (HG-30, no
semgrep host here).

## R8 — Python-only PNG codec + perceptual diff (T6)

Real, stdlib-only: `build/qa/visual/pngcodec.py` (8-bit RGB/RGBA/gray/
palette, filters 0–4) + `build/qa/visual/engine.py` (fixed-point sRGB delta,
threshold, AA-ignore regions). Discrimination measured on synthetic images
(identical / 1 px / theme-swapped / RTL-mirrored / above+below threshold).
The capture half is farm (no real screenshots here) — see R2.

## R9 — GitHub API for evidence links (T12) — verified this phase

Verified 2026-09-10 against `RRRTX-Labs/xr-browser`:
`GET /repos/RRRTX-Labs/xr-browser/actions/runs?per_page=N` ✓ (public),
`GET /repos/RRRTX-Labs/xr-browser/actions/runs/<id>/jobs` ✓ (per-step
conclusions, unauthenticated), `…/actions/runs/<id>/logs` → **403**
(admin-only), `…/check_suites` → **404**. Confirmed unchanged from the
orchestrator's finding. `tools/evidence_check.py --strict` now resolves
`ci_run`/`ci_job` ids through `build/upstream/fetch.py` (api.github.com
already allowlisted), SKIP-visible when offline.

## Decision rows (the ones the brief asked to record)

| decision | verdict | where recorded |
|---|---|---|
| axe-core vs DOM shim | AXTree snapshot transform (no jsdom) | `docs/qa/a11y-contract.md`, R4 |
| Gold bridge scope | codec+comparator real; captures farm | `docs/qa/gold-triage.md`, R2 |
| CLite placement | not adopted; libFuzzer entry points CI-side | `docs/qa/fuzz.md`, R5 |
| leaktest privilege model | loopback real; capture farm (CAP_NET_RAW) | `docs/qa/leaktest.md`, R6 |
| clang-tidy config-only vs checks | config-only (mode_lint covers) | `docs/dependencies/sast-tooling.yaml`, R7 |
| DOM/AXTree snapshot transform | Lit AST → `docs/qa/axtree-snapshot.json` | `docs/qa/a11y-contract.md` |
| deliberately not-yet | Rust fuzz targets + Mojo bind fuzz = P11/P16 (owners in `docs/qa/surfaces.yaml`) | `docs/qa/surfaces.yaml` |

## Product-code-paths-unchanged assertion (security req 5)

No `#if defined(XR_TEST)` weakening, no flag that turns a refusal into an
accept, no disabled assertion was added. Grep used:
`grep -rn "XR_TEST\|XR_TESTING\|#ifdef.*TEST" xr-core/{policy,commands,settings,themes}`
— zero product-path hits; every fixture lives in `xr-core/test/` or
`fakes/fixtures/` (separate trees). The theme loader, dispatch source-tag
allowlist, and policy deny-on-unknown remain absolute.
