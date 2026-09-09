# Human gates touched by P8 (Stage 1) — XR Browser Phase P8

Nothing here is met-in-sandbox. Browser-runtime, screen-reader, visual, and
reference-hardware claims are HUMAN-GATED and stay HUMAN-GATED until the named
humans run them on the farm; every row carries the exact command/runbook.

## Carried gates this phase touches (statuses unchanged from earlier phases)

- **HG-26 — contract ratification (now THREE consumers deep).** PENDING
  (human act). P8 surfaces depending on frozen-but-unratified contracts:
  1. settings-schema-v1 (§1.11 #14) — consumed by `xr-core/settings/core/`
     (schema validation, section registry, search corpus) and the
     `settings-host-protocol` post-freeze contract;
  2. theme-tokens-v1 (§1.11 #14) — consumed by `xr-core/ui/themes/tokens.json`,
     `tools/tokens_gen.py`, and `xr-core/themes/core/` (strict token set,
     contrast audit, loader refusal);
  3. command-descriptor-v1 (P5 freeze) — consumed through the P7 registry by
     the settings-jump commands (`settings.network`, `settings.privacy`,
     `settings.identity`) that the §10 coverage ratchet binds to P8's sections.
  Ratification stays PENDING; P8 adds no RATIFIED claim anywhere.
- **HG-20 — user action, STILL UNCONFIRMED: PAT revocation.** The PAT used to
  push this phase's commits (ghp_… supplied by the user in the phase brief)
  remains un-revoked/un-confirmed by the user. Re-flagged, not resolved.
- **HG-28 — 24 h fuzz + reference-hardware bench.** P8's in-sandbox seeded
  campaigns (600 s each) and budget benches are local evidence only; the 24 h
  fleet run and reference-hardware numbers remain open.
- **HG-31 — farm browser E2E.** P8 adds the settings flow (search → jump →
  toggle → deep link → back), theme switching, and the both-flags matrix to
  `docs/webui-e2e.md`; execution needs the farm browser.
- **HG-32 — a11y engineer walkthrough.** EXTENDED (P8): the keyboard-only +
  screen-reader walk now also covers the settings shell (search → results →
  section → control, focus return after jump, aria-live counts) and the
  High-Contrast theme + settings under forced-colors.
- **HG-33 — power-user dogfood, week 1.**
- **HG-34 — branch protection / PR flow.** Direct push to main remains
  sanctioned until HG-3/HG-10 land (recorded P6-T0 push-mode ruling).

## New gate from this phase

- **HG-35 — browser-side settings/theme budgets + no-reload theme switch +
  visual ×theme snapshots on the farm.** Exact runbook in `docs/webui-e2e.md`:
  theme apply ≤100 ms is CORE-side (met in-sandbox, `themes/tests/bench`); the
  *browser-side* rows — first paint ≤300 ms after `xr://settings` open, theme
  switch mid-window with NO reload and a published token-map event, and visual
  snapshots of all 4+2 themes across the four views + settings — are farm
  rows (HG-31 hardware), never inferred PASS from this sandbox.
