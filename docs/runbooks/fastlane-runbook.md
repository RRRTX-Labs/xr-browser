# Runbook: the security fast lane (P3-T5)

Audience: the on-call security owner (@xr/security). Tool: `build/upstream/fastlane.py` via `./scripts/build fastlane|sla`. Contract: `docs/contracts/sla-metrics-v1.md`.

## Steady state (automated, nightly)

The nightly workflow runs `fastlane watch`: every new Chromium Stable/Extended tag becomes a candidate with a cherry-pick plan; deadlines are computed from TAG PUBLICATION (72h critical/IIT, 14d high). Nothing fires while no XR stable exists (first stable = P10). Drills run nightly to keep the lane honest (`source:"fixture"`, simulated elapsed labeled).

## When a security tag drops

1. `./scripts/build fastlane watch --json` — confirm the new tag is a candidate (release-driven; commit-message matching is advisory only, R4).
2. `./scripts/build fastlane plan --version <tag>` — the plan: range commits between previous_version and version, risk classes, `needs_build`, deadlines.
3. Triage candidates: explicit advisory marker > security wording > unknown (unknown is treated as security until proven otherwise — worst-case-first).
4. The apply/sign/verify path for REAL activations is exercised per the drill choreography (cherry-pick onto the release branch, verify content, sign via P2 `sign_artifact.py` dev channel with TEST keys until P10's release-key parity, build, ship). **The bot prepares; the on-call executes (L24).**
5. Post-GA, a real activation records real elapsed-from-publication; pre-GA, only drills exist and every artifact says so.

## SLA clock

`./scripts/build sla --since <version> [--severity critical|high] [--at <ISO>]` — deadlines, remaining hours, breach state; on breach it writes `work/upstream-cache/feature-freeze.json` (§15-R1; advisory in CI now, HARD in the P9 dashboard; pre-GA markers are ADVISORY-ONLY and say so).

Two misses in a quarter = feature freeze (the kill-switch arms at P10's first stable promotion).

## Drills (what PASS means)

`./scripts/build fastlane drill` → 2/2 must PASS:
- **in-window** (30h simulated): apply+verify+sign ok, unsigned-stable refused, no breach, no marker.
- **breach** (80h simulated): same walk, breach detected, marker written.

The negative is part of PASS: signing with `--channel stable` must be structurally refused by the P2 tool. Elapsed fields separate `elapsed_real_seconds` (≈0.1s) from `simulated_elapsed_hours` — never conflate them in reporting.

## Incident quick-checks

| symptom | check |
|---|---|
| chromiumdash unreachable | `fetch.py` allowlist / retry; watch fails LOUD, never silently passes |
| plan range empty | previous_version missing on chromiumdash → fall back to previous KNOWN tag, record in the plan's `detection` note |
| cherry-pick conflicts | treat as semantic conflict: resolve in patch semantics (§12.3), never disable-and-TODO |
| signing refuses | correct for anything but dev/nightly-test (P2 law); drill keys are TEST-ONLY (`XR_PROD_SIGN` unset) |
