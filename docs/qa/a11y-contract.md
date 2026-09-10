# A11y contract (P9-T7) — what a feature phase must satisfy

This is what P13/P21/P29/P30 inherit — the a11y-complete bar is defined here
once, so no feature phase re-argues it. Plan §11.6: "accessibility and
honesty failures block the release exactly like a crash would."

## The bar (per novel UI surface)

1. **Structural** — `tools/a11y_lint.py` (ARIA APG combobox, live regions,
   `:focus-visible`) and `tools/a11y_tree.py` (AXTree snapshot: every
   interactive node named, combobox/listbox pattern intact). Both run in CI;
   both have canaries.
2. **axe-core** — farm-run against the built bundle (HG-31,
   `build/qa/a11y/axe_run.mjs`); a violation needs a waiver
   (`build/qa/visual/waivers.yaml` pattern — expiries mandatory). The
   decision that axe needs a real DOM (and that jsdom is NOT pulled in as a
   second package) is recorded in `docs/dependencies/axe-core.yaml`.
3. **Copy** — `tools/copy_lint.py`: banned vocabulary over the ONE string
   source + the §11.6 "no numeric-similarity score" check over source and
   the `qyy` artifact.
4. **Pseudo-locale** — `tools/pseudo_locale.py` renders `xr_strings.grdp`
   to `qyy`; the RTL smoke (`rtl_lint`/`a11y_lint` over the rendered output)
   and the fixed-width canary stay green.
5. **Keyboard** — the 12 core tasks in `docs/qa/keyboard-tasks.yaml`
   (data, owned); farm executes them (HG-31), the gate protects the list.
6. **SR/forced-colors** — human passes on security surfaces (HG-32),
   scheduled per release (§11.14).

## Waivers

Any a11y violation a phase wants to ship WITH must land as a waiver with an
**expiry** (the same law as visual): an expired waiver turns the lane red,
forcing the owning phase to re-assert. Blanket waivers are not
representable.

## Farm rows (HG-31 / HG-32)

| row | command |
|---|---|
| axe run | `node build/qa/a11y/axe_run.mjs` in the farm browser after each view renders |
| keyboard tasks | execute `docs/qa/keyboard-tasks.yaml` end-to-end, record per-task pass |
| SR pass | NVDA/VoiceOver/Orca on prompts/dial/panel/vault/split headers (§11.6) |
