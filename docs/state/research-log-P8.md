# Research log — Phase P8 (Stage 1): WebUI platform, Settings v0, Theme tokens v1

Each item: cite (`path:line@pin`, a URL + date, or `UNVERIFIED (deferred to
P<n>)`). Nothing relied on is left to memory where a fetch settles it. Upstream
facts were checked at the pin `d04cdb24d67b081f6cf80200ffc5233f44b61109`
(152.0.7977.82) via `build/upstream/fetch.py`.

## T0 — added-file upstream debt (root cause, P8 blocking debt)

Manifest entries may ADD files that exist at no upstream rev (P7's
`0100-ui-skeleton` payload `chrome/browser/ui/xr/*`). `rebase_bot.py:151`
(`pin_files[f] = source.file_text(from_rev, f)`) had no 404 tolerance while the
target-side fetch one line below was already wrapped (`try/except FetchError`),
so the daily canary died before producing a report:

```
$ XR_LIVE_NET=1 ./scripts/build rebase rebase --to <latest-main-sha> --dry-run --explain
error: HTTP 404 fetching https://chromium.googlesource.com/chromium/src/+/d04cdb24…/chrome/browser/ui/xr/BUILD.gn?format=TEXT   (exit 1)
```

The same latent defect sat in `promotion.py` (compat smoke `_patch_roundtrip_at`,
previously `promotion.py:144`): a FetchError there became
`return False, "target file … not fetchable"`, so any promotion would be
permanently refused while an added file is in the manifest — an added file is
absent at the candidate rev *by definition* and must not be an error.

Fix semantics (implemented in the pure engine `classify.py`, not the fetch
layer):
- a manifest file missing at the pin is an **addition**: absent at the pin AND
  absent at the target ⇒ `clean` (apply creates it);
- addition + PRESENT at the target ⇒ `path-collision` (BROKEN verdict, human
  work item — never silently renamed);
- moved-detection (`_moved_targets`) is never attempted for additions (the
  pin bytes do not exist by definition, so there is nothing to hash).
- Only a genuine `HTTP 404` counts as "missing": any other FetchError still
  fails closed (an absence is never guessed).
- `promotion.py`: 404-at-candidate ⇒ materialize the file as ABSENT and let
  `apply_patch` decide. Added file ⇒ created (clean); an upstream-DELETED hook
  file ⇒ apply failure (refusal, real re-anchor work item). Offline-deterministic.

Coverage so this cannot hide until a 02:00 UTC nightly again:
- fixture tests in `build/upstream/tests/test_upstream_suite.py`
  (added-file clean / path-collision BROKEN / mixed entry / engine-misuse
  rejections / run_rebase rows / promotion smoke accepted-added +
  refused-deleted);
- the fixture corpus gained `F-0006-added` (a patch whose file exists at NO
  rev) with per-range oracle rows;
- a NEW on-push live smoke lane in `tools/run_checks.sh`: real fetch.py
  classification from the pin to the pin (`--to <chromium_rev>`, gitiles TEXT,
  no new allowlist entries); measured 8.0 s locally (warm cache) — cold CI cost
  est. 15–30 s, comfortably inside the ~60 s note.
- one negative-gate case (added-file path-collision) ships with the P8
  negatives restructure (T8).

No gate semantics, thresholds, seeds, timeboxes or allowlist entries changed
for T0; `fetch.py` itself was NOT touched.

## Open research items (P8's eight; filled as they settle)

1. NativeTheme observation surface for the payload (views-side light/dark +
   high-contrast observer API) — to cite at the pin.
2. Upstream settings-page registration surface (`chrome/browser/resources/settings`)
   — extend-not-fork evidence.
3. Grit/GRD facts (`browser_strings*.grdp` conventions, `.xtb` byte format) and
   whether `.xtb` can be produced without Chromium's grit.
4. Chromium pseudo-locale (`qyy`) behavior (expansion/accenting/mirroring).
5. WCAG 2.1 relative-luminance/contrast math (W3C definition + worked examples).
6. Chromium forced-colors/`forced-colors-adjust` CSS conventions.
7. npm dev-dep status re-check at work date (lit/esbuild/typescript) + stdlib
   GRD-parse confirmation.
8. Isolation-card ↔ grdp interplay decision (fold vs. keep-both + gate).

## Locked decisions (P8) — recorded with rationale

(To be completed as each task lands: curated +2 themes and rationale, matcher
share-vs-copy, header type, bundled-font list empty, isolation-card/grdp
relationship, host-protocol conventions.)
