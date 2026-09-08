# P7 — human gates (the actions this phase cannot do, honestly recorded)

These are the human/farm-only actions P7 ships the *harness for* but cannot
itself perform in-sandbox. None of these are marked met-in-sandbox; the browser-
runtime budgets are **HUMAN-GATED** (HG-31), and the core budget **is** met in-
sandbox with recorded numbers (see `evidence.json` DOD-12 + `logs/bench.json`).

## HG-31 — farm browser E2E (the browser-runtime budgets)

The in-sandbox proof covers the **core** sub-budget (matcher p99 ≤ 5 ms on the
2000-command corpus — **measured at 972 µs**, `logs/bench.json`). The
**end-to-end** budgets and browser-runtime behaviors need a real browser on the
HG-31 farm:

- palette **≤ 50 ms warm / ≤ 150 ms cold** end-to-end (type → ranked → execute).
- **type → execute E2E**: the host protocol driven by a real `commands_host`
  mojom/IPC glue (P16) — the stdio host + the parity fake are proven; the
  browser IPC transport is farm-gated.
- **visual snapshot matrix**: identity-color-bar × themes (the §1.4 identity /
  trust color vocabulary rendering across the chrome themes).
- **cold-start ≤ 10% nightly**: the flake budget over the nightly farm runs.

Runbook: `docs/webui-e2e.md` (the four-views flow, host protocol, budgets,
keyboard table). Commands + harnesses are shipped; execution is the farm's.

## HG-32 — a11y engineer keyboard-only walkthrough

A screen-reader / keyboard-only pass over the palette (the SR-first combobox)
and the Tier-2 surfaces. The structural a11y law is enforced by
`tools/a11y_lint.py` (ARIA APG combobox tokens + `aria-live` empty-state +
`:focus-visible`), and the keyboard model is documented in
`docs/webui-e2e.md`. The *experience* (announcement order, focus management
across the four views) is a human a11y engineering review.

## HG-33 — power-user dogfood, week 1

Real power users driving the palette / menus / shortcut editor / help index for
a week. Not reproducible in-sandbox.

## HG-26 — contract ratification (now two consumers deep)

`command-host-protocol v1` is a new P7 contract registered in the post-freeze
registry (`docs/contracts/registry-post-freeze.md`). Ratification is
human-only (HG-26). It is now **two consumers deep** (the P7 registry + this
evidence bundle + P8/P13 will consume it). Escalate to principals: the frozen
surface is growing a second protocol on top of the P5 descriptor, both
parity-locked.

## HG-34 — branch protection (carried)

Branch protection is still open (PR-flow switch per P6 T0 policy). Pushes here
are direct under the phase token; the PR-flow switch is a separate human action.

## Carried (unchanged from prior phases)

- **HG-9** — (carried)
- **HG-21** — (carried)
- **HG-28** — (carried)
- **HG-29** — mojom / PrefService integration is farm-gated (P7's `commands_host`
  is the stdio host + the parity reference; the on-tree mojom/IPC is P16).
