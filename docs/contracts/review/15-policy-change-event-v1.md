# Review packet: Policy-change-event v1 (P6-T5; post-freeze addition)

- **Contract id:** policy-change-event  **Version:** 1  **Freeze status:** REVIEW-COMPLETE (P6-born; NOT retro-inserted into the P5 §1.11 freeze register)
- **Ratification:** PENDING (HG-26; human sign-off below is pending)

## Why this contract exists (plan §643 UX req)

The change-strip copy law: concrete deltas ("camera, mic, location now
blocked · stricter isolation · Undo"), **no scores, no auto-reload** —
codified as the event payload schema so P8's dial strip cannot invent a
different shape later. This is the ONLY thing this contract carries: what
changed, in human terms, with an undo affordance.

## Files shipped

- `docs/contracts/policy-change-event-v1.schema.json` — 9 required fields
  (`event`, `contract_version`, `identity`, `site`, `previous_trust`,
  `new_trust`, `deltas[]`, `summary`, `undo`), `additionalProperties: false`.
- `docs/contracts/policy-change-event-v1.md` — laws + example.
- `docs/contracts/tests/golden-policy-change-event.json` — golden event,
  byte-verified against the C++ generator (`xr-core/policy/core/events.cc`).
- Generator: `xr-core/policy/core/events.{h,cc}` (18 leaf paths, deltas +
  " · " summary + undo; golden strings pinned in
  `xr-core/policy/tests/test_events.cc`).
- Registration: `tools/xr_schema.py` SCHEMAS map (validated in run_checks).

## Absence laws (lint-enforced, not convention)

The schema file and md must NOT contain numeric judgment/quality field
names or auto-reload fields — the ban is a token scan over the full file
(prose and comments included; the first draft self-hit and was reworded).
Enforced by `tools/tests/test_p6_policy_tools.py` (absence laws).

## §7.2 import-law compatibility check

- Pure data contract: no imports, no code dependencies beyond the C++
  generator (which lives in `policy/core`, std-C++20, no Chromium includes).
- Consumed by: P8 dial strip (future), xrctl diagnostics (read-only).

## Threat-model invariants linked

- No auto-reload by absence: consumers re-derive policy through the
  resolver; the event is a NOTIFICATION of a resolved change, never an
  instruction (§465: no parallel path around the resolver).
- `undo` is an affordance flag, not a capability: the actual revert goes
  through the same store + resolver path as any other change.

## Checklist (structure mirrors freeze_check rows; sign-off = human)

- [ ] narrow surface — sign-off: __PENDING (human)__
- [ ] typed fields only (enum/string/bool; no free-form error strings) — sign-off: __PENDING (human)__
- [ ] no scores/risk/grades (absence-linted) — sign-off: __PENDING (human)__
- [ ] no auto-reload semantics (absence-linted) — sign-off: __PENDING (human)__
- [ ] fuzz target required before integration — target: covered by
      `policy_fuzz.py` envelope laws (P6) + P9 event-stream fuzz — sign-off: __PENDING (human)__

## Open questions for the S0 humans

- Confirm the delta leaf-path set (18 paths) matches the intended change-strip
  granularity (P8 may request additions — that is an RFC under T10, not a
  silent edit).
- Confirm HG-26 ratification together with the P5 batch.
