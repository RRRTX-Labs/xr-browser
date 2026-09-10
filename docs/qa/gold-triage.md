# Gold triage (P9-T6) — what's real here, what's farm

Owner tools: `tools/visual_diff.py`, `build/qa/visual/{pngcodec,engine}.py`.

## The split (honest, per research #8)

| Piece | Where | Status |
|---|---|---|
| PNG codec (read/write, stdlib) | `build/qa/visual/pngcodec.py` | **real here** (8-bit RGB/RGBA/gray/palette, filters 0–4) |
| comparison engine (fixed-point sRGB delta, threshold, AA-ignore regions) | `build/qa/visual/engine.py` | **real here** |
| waiver registry with expiries | `build/qa/visual/waivers.yaml` + `tools/visual_diff.py` | **real here** (expired waiver ⇒ red) |
| reference captures (real screenshots) | — | **farm** (Gold captures; HG-31) |
| Chromium Gold bridge (`--gold` invocation) | — | **farm** (recorded, not faked) |

The engine's discrimination is measured on synthetic images (identical /
1 px / theme-swapped / RTL-mirrored / above+below threshold) in the
self-test and the pytest suite — a pair that must be flagged is flagged.

## Snapshot format

`{name, view, theme, locale, direction, identity_mark, hash, size,
provenance}` — carried as a metadata envelope (see `SnapshotMeta`). The
engine compares pixels; the manifest decides which pixels belong together
(theme × layout × identity mark).

## Gold bridge (farm invocation, exact)

```bash
# On the farm, after a promotion build:
goldctl imgtest init --instance xr-snapshots --url https://gold.skia.org
goldctl imgtest add --test-name <view>-<theme>-<dir> --png-file shot.png \
    --keys view:<view>,theme:<theme>,dir:<dir>,identity:<mark>
goldctl imgtest finalize
```

This repo never opens a connection to Gold (zero new egress); the bridge is
a documented farm step, and the comparator here is what a future in-repo
triage can reuse.

## Waiver law

A waiver covers exactly one `(snapshot name, reference hash)` pair. A
differing candidate with an unexpired waiver ⇒ `WAIVED` (pass, recorded);
with an **expired** waiver ⇒ `DIFFERENT` (red — the snapshot must re-assert).
Blanket waivers are not representable.
