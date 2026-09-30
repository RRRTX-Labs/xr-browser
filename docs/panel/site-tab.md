# The Site tab (P13-T2)

**Core:** `xr-core/ui/panel/site-tab.ts` ·
**Tests:** `ui/panel/tests/site-tab.test.mjs` ·
**Why table:** `docs/shield/reason-codes.json` (13 codes) ·
**Lane:** `build/webui/panel-tests.sh` (`XR_PANEL_SITE_BUNDLE`, `XR_PANEL_WHY_TABLE`).

## What the user sees

TLS/certificate basics, the trust dial inline, per-site exceptions, the
permissions summary (a pointer forward to P15), the isolation card, and
blocked-by-category with a "why" drill.

## The laws the core owns

1. **One scope object, no second store.** Shields-down is one bit that the
   cosmetic layer and the network layer read TOGETHER. `shieldsDown()` is a pure
   function over the scope array; the dial's `read_by` names both readers
   (`['xr-core/shield', 'xr-core/cosmetic']`) and its `by` is
   `site-toggle:<site>`; `toggleRequest()` and `exceptionRequest()` return
   REQUESTS (8-key scope wire form) — the tab writes nothing itself, and there is
   no local set to drift from the ledger.
2. **An absent certificate is not a green certificate.** `certRows(null)` renders
   `no-certificate-observed`, never an empty list and never "secure".
3. **The why-drill reaches rule / list / source**, consuming the 13-code table;
   an event whose code is absent renders a TYPED FALLBACK
   (`shield.why.unknown.<code>`), not a blank and not an "unknown" that reads
   like "clean". The suite walks every code × the fallback.
4. **Generic hides are not exception-able, and the row says why.**
   `genericHideSetRows({count,rule_ids,reason_key})` yields per-row
   `exceptionable: false`, a `reason_key` and the `set_size` — and **no `remove`
   field at all**. The absence IS the law: there is no control to render, so no
   renderer can render one.
5. **The isolation card is DATA, not prose** (P4's measured table, row for row),
   and a row P4 did not measure renders
   `NOT-RUN (method: docs/qa/browser-harness.md)` — classed `not-run` — rather
   than an empty cell, because an empty cell reads as "fine".
6. **The scriptlet surface is stated, not implied.** `scriptletRows()` renders
   the registry as `present`/`absent` and execution as `INERT (flag:off)` /
   `ACTIVE` / **`unknown`** — an unobserved flag is never reported as "off"
   (fail-safe in the direction that matters).
7. **Permissions:** `permissionsSummary().grants_live_in = 'P15-permissions'`.
   The tab summarises; it does not grant.

## Registered negatives

`tools/negatives/p13_c01.sh` (the unit/isolation negatives), the bypass negative
in `tools/negatives/p13_c5.sh` (a frame that names a tab id), and the node suite
itself, which the `--plant-leak` control must be able to redden.

## What is NOT-RUN

Every rendered half: the dial's paint, the card's keyboard order, the drill's
focus behaviour — `NOT-RUN (method: docs/qa/browser-harness.md)`. HG-31 remains
the browser rig gate.
