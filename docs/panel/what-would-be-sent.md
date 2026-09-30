# The "what would be sent" viewer (P13-T6)

**Core:** `xr-core/ui/panel/sent-tab.ts` ·
**Tests:** `ui/panel/tests/sent-tab.test.mjs` ·
**Lane:** `build/webui/panel-tests.sh` (`XR_PANEL_SENT_BUNDLE`).

## Why it exists

The product's privacy guarantee #1 is "you can see exactly what would leave the
machine before it leaves". Every such viewer in every product fails the same way:
the preview is written a second time. It enumerates the fields it knows about,
drifts from the serializer, and quietly stops showing the field that was added
last. Nobody notices, because the preview still renders.

So this viewer has **one serializer**. `serialize()` flattens a payload into an
ordered list of `{path, value}` fields; `viewerRows()` is a pure function OF THAT
OUTPUT. The viewer never sees the payload's shape, so it cannot enumerate fields
independently — hiding a field would require a second implementation, and there
is nowhere to put one.

## Totality

Every serialized field produces a row. A value the viewer cannot render — a
nested structure, an array of objects — still produces a row, marked
`value-unrenderable`, carrying the field's PATH. `hiddenFields()` returns the
paths that would be hidden and is asserted empty over every shape in the suite.

The proof is by planting: the suite adds a field the viewer has no special case
for (`cookie`) and asserts it becomes a visible row. A viewer that can hide a
field fails that test; a viewer that cannot hide one passes it by construction.

## Related surfaces

* the breakage tab's payload (`ui/panel/breakage-tab.ts`) has a **closed** row
  set, so the viewer's input cannot contain page content in the first place;
* the report path itself (`docs/panel/breakage-report.md`) refuses the smuggle
  classes pre-send and has no transport in this repository.

## What is NOT-RUN

The rendered half: the viewer's real DOM, its focus order and its screen-reader
reading — `NOT-RUN (method: docs/qa/browser-harness.md)`. The suite is a node
test against the bundled core, and it is described as exactly that.
