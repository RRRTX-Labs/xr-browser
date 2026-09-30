# The Tracker Observatory tab (P13-T3)

**Core:** `xr-core/ui/panel/observatory-tab.ts` ·
**Tests:** `ui/panel/tests/observatory-tab.test.mjs` ·
**Export:** `tools/observatory_export.py` (`--check` is the gate) ·
**Data:** `block-event-v1` rows (P11/P12), byte-parity with the golden row.

## What the user sees

The activity ledger as a **virtualized list**: a ring capped at 2000 rows,
filters by type and origin, and an export that can be JSON or CSV. The header is
honest by construction — `ringSummary()` returns `shown_of_total` (`"<n> of
<total>"`), `dropped_by_cap` and `filtered_out` — because a ring that quietly
shows a window of the newest rows looks exactly like a ring that has everything.

## The four laws the core owns

1. **The cap is 2000 and the drop count is returned, never hidden.**
   `mergeIntoRing()` returns `{rows, dropped}`; past the cap the OLDEST rows go,
   and the UI can say "2000 of 3141".
2. **The window clamps at both ends.** `windowFor()` turns
   (scrollTop, rowHeight, viewportHeight, overscan) into `[first, last)` over the
   FILTERED length, so the last screenful is never short (the classic off-by-one
   that makes the final rows unreachable) and a scroll position that belonged to
   the unfiltered list cannot produce an empty screen.
3. **Filters run before the window.** `applyFilters()` treats an absent filter as
   "no filter", never as "match nothing".
4. **The a11y tree is told the truth.** `a11yRowMeta()` hands every RENDERED row
   its `aria-rowindex` / `aria-rowcount` / `aria-posinset`, with `rowcount` = the
   whole FILTERED length, not the window: a screen reader is told the list is
   longer than the DOM. The renderer does not invent the attributes, so "a row
   present in the DOM but absent from the a11y tree" cannot be produced by
   accident.

## Export: redaction is the contract

`tools/observatory_export.py` is the only exporter. Its laws arrive as tests:

* **no query params, no fragments** by default (`--full` opts the query back in,
  the fragment never);
* **`user:pass@` is REFUSED, never stripped** — a stripped row still looks
  exported, which is worse than a refusal the caller must handle;
* a field *named* like a leak (`cookie`, `user_agent`, `selector`) is refused by
  NAME, whatever its value, because a renamed leak is still the leak;
* a value that looks like a leak is refused even under an innocent key;
* **the refused bytes never reach the writer**: `--check` runs a seven-case
  smuggle corpus and asserts the offending substring is absent from every byte
  the tool produced (JSON and CSV);
* the product's own data is not eaten: `###tracker-ad` is a filter RULE, and the
  rule that drops fragments is a function of the parsed target, not a text scan;
* **one field list drives both formats** (`FIELDS`), so a column cannot exist in
  JSON and be missing from CSV; the committed golden block-event row is exported
  three times and compared byte-for-byte.

`tools/shield_state_check.py` asserts the enum surface: the export's `FIELDS`
must carry every enum-bearing `block-event-v1` property (`action`, `why_code`,
`request_class`, `page_modifying`) and may not name a property the schema does
not define. `request_class` is exported under the ledger's own name; the
observatory's filter name for it (`type`) is declared as an alias in the tool, so
the rename is data rather than a call-site translation. Registered negative:
a fixture with `page_modifying` dropped from `FIELDS` reddens
(`tools/negatives/p13_c2.sh` case 5).

## What is NOT-RUN

Rendered/browser halves: the virtualized list's paint cost, the ≤16 fps
worst-case scroll on a populated 2k ring, and the export's cost on a full ring —
`NOT-RUN (method: docs/qa/browser-harness.md#panel-ring-scroll)`. No screenshot,
no frame timing and no memory figure is claimed anywhere in this phase (HG-31).
