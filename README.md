# xr-browser (meta repository)

XR Browser by RRRTX Labs — the governance, build/release, and
documentation surface. The product code lives in the sibling `xr-core`
repository (Plan §7.1: two repos + helpers; deliberately not a sprawl).
Full map: `docs/state/repo-map.md`.

**License:** MPL-2.0 (see `LICENSE`; choice recorded in
`docs/adr/0001-repo-topology-and-licensing.md`). Contributions require
the [Developer Certificate of Origin](https://developercertificate.org)
(`git commit --signoff`).

**Status:** Phase P1 complete (governance, legal gates, skeleton).
Phase P2 (hermetic Chromium build) has not started and nothing in this
repo stubs it — the anti-stub rule is plan law (§0.4, L5).

## The Master Plan is pinned

`docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` is the single source of
truth, pinned by SHA-256 in `docs/master-plan.sha256` and verified on
every CI run. The file is immutable in place; amendments follow
`docs/process/plan-amendment.md` (new versioned file + register entry +
re-pin, in one reviewed commit).

## What makes this repo move (the gates)

Everything in `tools/` is machine-checkable project law. CI
(`.github/workflows/governance.yml`) runs all of it from commit 1:

| Gate | Enforces |
|---|---|
| `plan_pin_check.py` | committed plan == SHA-256 pin |
| `registry_lint.py` | feature registry == plan §2 (122 rows; "no feature exists outside it") |
| `dr_parse.py` | Decision Register schema (DR-01..30) + `Register-Change: ADR-<nnnn>` trailers |
| `license_audit.py` | canonical MPL-2.0 + no GPL/AGPL code (header/inventory level) |
| `dco_check.py` | every commit carries a matching signoff |
| `check_threat_model.py` | threat-model v0 structure (T1–T11 honesty column, plan binding) |
| `vocab_lint.py` | banned-claims vocabulary (plan §0.3/§1.12-9/§9.11) |
| `owners_sync.py` | CODEOWNERS/OWNERS in sync with `docs/process/s0-paths.yaml` |

Run everything locally: `tools/run_checks.sh` (gate) and
`tools/run_negatives.sh` (proof the gates fail on bad input — the plan's
P1 "Tests" DoD). Tests: `python3 -m pytest tools/tests/ -q`.
Dependency policy: `tools/DEPS.md` (max PyYAML/jsonschema/pytest,
hash-pinned; stdlib otherwise).

## Where the decisions live

- **`docs/register/decisions.yaml`** — DR-01..DR-30, the decision
  register (plan Appendix B). Changing it requires a
  `Register-Change: ADR-<nnnn>` trailer (CI-enforced).
- **`docs/adr/`** — agents draft, humans decide (ADR-0002).
- **`docs/legal/`** — LG-1/LG-2/LG-3 counsel briefs: facts + sources +
  options + questions, with verdict fields **blank by design** (counsel
  work, never agent work).
- **`docs/dependencies/`** — L9 evaluation pack: one file per §8
  INTEGRATE row, live-verified 2026-09-07, 90-day refresh.
- **`evidence/P1/`** — the P1 evidence bundle: `evidence.json` (12 DoD
  rows), `human-gates.md` (HG-1..HG-8 — what humans/ops must do next),
  executed gate logs.

## Honest status of protections

This repo contains **governance only**. The threat model v0 is
explicitly pre-implementation: every protection it states is target
posture, not shipped functionality. P1 ships the rules, the gates, and
the evidence trail — not a browser.
