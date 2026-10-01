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

## P11-T8: shield live-capture FP set (D-6 method, NOT-RUN, HG-31)

The vendored corpus (≥1,500 synthetic cases) carries the FP ≤0.5% band
today. The plan's 1,000-site live-traffic measurement needs a browser
and is recorded as NOT-RUN — no live-traffic FP claim exists anywhere.
Farm method, verbatim:

1. Load the top-1,000-site list (frozen copy committed with the run) in
   the farm browser with the product shield bundle active.
2. Capture every network-service request URL through the seam's redacted
   match surface (`scheme://host/path`, lowercased, port/query/fragment
   stripped) plus initiator rd — the capture file is the corpus.
3. Replay each captured request through BOTH engines (TableEngine and
   the real shim) offline via `tools/shield_parity.py --corpus
   <capture>`; agreement ≥98%, FP ≤0.5% of expected-allow.
4. Every divergence lands in `docs/shield/parity-divergences.md` as a
   pinned class BEFORE any band re-run; an unpinnable divergence is a
   stop-and-report (brief law), never a band adjustment.

## P12-T7: cosmetic perf — the surrogate lane and the NOT-RUN farm halves

The sandbox surrogate (`tools/cosmetic_bench.py`) drives `cosmetic_host`'s
`key-set` path (the compiled core the renderer uses) and commits two rows
into `docs/state/bench-trend.json`: `cosmetic_keyset_build_ms` (measured
~2 ms against the 50 ms generic-set sustain budget) and
`cosmetic_generic_set_rules` (the shipped 33). Both are labelled
`surrogate:true` and `rig_class:trend`; `tools/perf_gate.py` refuses a
cosmetic row without the label and pins every surrogate NEUTRAL — a
synthetic number may never read as a browser measurement (this phase's
disqualifier), and `tools/negatives/p12_t7.sh` keeps both red.

The real halves are NOT-RUN (method pointers below). No page-level or
compiled result is claimed anywhere in this tree.

### document-start p95 method (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#document-start-p95)` —
reference rig only, `cosmetic_document_start_add_ms` (≤4 ms p95):

1. Farm browser at the pinned Chromium rev, `xr_shield_cosmetic_v1` on.
2. Load the committed fixture-corpus pages (ad-layout set from P12-T1) and
   measure mojom-request → first inline-style applied at `Document` start.
3. p95 over ≥500 navigations, cold and warm; commit the bench JSON through
   `tools/perf_gate.py` on a `reference` rig only.

### blank-page detection over the fixture corpus (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#blank-page-detection)` —
the down-the-page safety proof, never merged with the other two ways:

1. Render fixture pages with the seam active; assert a non-empty layout
   (blankness oracle) for every page, incl. the kill-switch suit where the
   hook is forced to die.
2. A page that rasterizes blank is a red; the degrade table's "render the
   page unstyled" guarantee is proven here, not inferred from the host.

### 50-hard-apps spot check (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#50-hard-apps)` — manual-
design spot check over the P12 hard-app corpus: no layout corruption with
the seam active, dark-mode + high-contrast × cosmetic interaction per the
phase Manual row.

### breakage-diff baseline ≤ +0.5 % (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#breakage-diff)` — compat
corpus deltas: diff day-to-day breakage counts with the seam on vs off
against the same-milestone Chrome; the baseline is ≤ +0.5 %, tracked per
promotion (P12 DoD "corpus deltas within budget").

### DOM-poll measurement vs the cited reference (NOT-RUN, UNVERIFIED)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#dom-poll)` —
`cosmetic_dom_poll_cost_us`: measure the abpc DOM-poll cost on the
reference rig and compare to the uBO reference measurement cited in
`docs/state/research-log-P12.md`; **that citation is UNVERIFIED at
close-out** — the budget row's source says so rather than inventing a
number (`build/qa/perf/gen_perf_budgets.py`, `cosmetic-dom-poll-cost`).

## P13-T7: panel perf — the surrogate lane and the NOT-RUN farm halves

What this sandbox measures is the frame's PURE CORE, and it says so: the two
`panel_open_core_ms` / `panel_open_subtree_scans` rows come from
`tools/panel_bench.py` (the bundled `ui/panel/focus-trap.ts` under node, over a
4096-focusable synthetic document), the benches declare `surrogate: true`, and
the comparator's rig-class law means a `trend` rig may never read `MET`
(negative: `tools/negatives/p13_t7.sh`). The budget rows themselves are emitted
only by `build/qa/perf/gen_perf_budgets.py`, transcribed from the pinned plan:
`panel-open` and `panel-ring-scroll` from §11.7 / §4 P13 Perf, plus the
surrogate ceiling.

Both browser-side budgets stay NOT-RUN here, with their methods:

### panel open ≤ 150 ms (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#panel-open-150ms)` — on the
reference rig (HG-31): open `xr://settings` with a 20-tab profile and a
populated ring, then toggle the panel with the keyboard; measure the time from
the key event to the frame's first painted frame (`performance.mark` around the
host's toggle + `requestAnimationFrame` to first paint), median of 20 opens and
p90 with a cold tab strip. The budget is the plan's §11.7 `panel-open` row
(150 ms); the panel's lazy-tab law is asserted structurally in the same run: the
number of REGISTERED tabs must not affect the open time (open with 1 tab vs 20,
delta inside the comparator's ±2 % noise band).

### ring render ≤ 16 fps worst-case scroll (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#panel-ring-scroll)` — on the
reference rig: fill the Observatory's ring to its 2k cap, then scroll the panel
body continuously for 10 s while recording `requestAnimationFrame` timestamps;
report the worst 1-s window's frames-per-second and the p99 frame interval. The
budget is the plan's §4 P13 Perf row verbatim (`ring render ≤16 fps worst-case
scroll`, transcribed as `panel-ring-scroll`); the run records the rig class and
the window definition next to the number, because a frame-rate number without
its window means nothing.

Both methods need a real Blink rig, a real build and a real 2k-row ring; none of
the three exists in this sandbox. The surrogate above is not a substitute — it
is labelled a subset everywhere it appears.

## P13-T4/T6: the breakage report and the what-would-be-sent viewer (NOT-RUN)

Two surfaces whose *rendered* halves stay unmeasured here, for the same reason as
everything above: no browser (HG-31). The honest statement of each method:

### breakage-report confirmation: one click, no modal (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#breakage-report-confirmation)` —
on the reference rig: open the breakage tab with a blocked event selected, click
the confirmation control once, and assert (a) the report is composed into the
preview with the same field set the serializer would write, (b) no modal, dialog,
badge, toast or banner appears anywhere in the frame, and (c) keyboard focus
never moves to a notification surface. The structural half is asserted in
`xr-core/ui/panel/tests/breakage-tab.test.mjs` (`assertConfirmable()` throws on
that vocabulary); what the rig adds is that a real renderer cannot route around
it.

### what-would-be-sent: the preview equals the payload (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#what-would-be-sent-parity)` — on
the reference rig: with a payload open in the viewer, copy the preview's rows out
of the DOM and compare them, path for path and in order, with the bytes the
serializer produces for the same payload; then plant an extra payload field and
assert it appears in the rendered rows. The structural half is
`ui/panel/tests/sent-tab.test.mjs` (planted `cookie` field must render,
`hiddenFields()` must be empty); the rig's half is the DOM.

### observatory export cost on a full 2k ring (NOT-RUN)

`↦ NOT-RUN (method: docs/qa/browser-harness.md#observatory-export-cost)` — on the
reference rig: fill the ring to its 2000-row cap, export JSON and CSV, and record
the wall-clock cost and the produced size per format, with `rig_class` printed.
No export cost or size number is claimed in this phase: the surrogate lane
measures the frame's pure core, not the export.

## Identity switch / wake budgets (P14-T1) — METHOD, not a result

The plan's `switch ≤ 200 ms` and `wake ≤ 200 ms to first paint` are rig
budgets. Method (a real rig, never this sandbox): build the pinned
Chromium + `xr/identity` wiring at the seam decision's primary seam, drive
N=30 switches/wakes between two provisioned identities via the CDP harness
(`build/spike/cdp.py` shape), record time-to-first-paint from
`Page.frameStartedLoading` to the first `PaintTime` marker, report p50/p95
against the budget rows in `docs/state/perf-budgets.json` (identity rows:
`rig_class: trend`). The state-machine halves (cap, eviction order,
no-resurrect) are pure core and ARE tested here
(`xr-core/identity/tests/test_hibernate.cc`).

## Mixed-identity walkthrough ×3 themes (P14-T4) — METHOD

Three themes (light / dark / high-contrast) × the mixed-identity
walkthrough (create Work + Disposable, open a tab in each, move a tab
across, destroy the disposable) on the visual-rig; snapshot the color-bar +
pill + amber-dashed-border states per layout × theme into the visual CI
corpus (`--check`; regeneration is a deliberate act with its own command —
never rewrite in-tree).

## Move-confirm usability session (P14-T3) — METHOD

6 non-engineer participants; task = move a tab across identities with the
confirm dialog; pass = the participant can say what the move will lose
BEFORE confirming (unaided). Recorded as a human gate (the phase report's
HG section); no surrogate exists and none may be invented.

## SR announcement audit (P14-T4) — METHOD

With a screen reader active, focus a tab in each identity kind; the
identity name + glyph must be announced. Axe-core `--check` covers the
static assertions; the live SR pass is the audit method (human gate).
