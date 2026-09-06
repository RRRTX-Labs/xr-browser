# ci/ — pipelines-as-code (S0)

At P2 this directory holds **pipeline definitions** — `build-lane.yml`
(PR compile lane) and `nightly-rebase-build.yml` (3-OS build matrix).
No pipeline is *running* yet: the build farm and self-hosted runners
land via human gate HG-9. The one executable pipeline of the project is
the **governance gate**, defined in `.github/workflows/governance.yml`
and run locally via `tools/run_checks.sh` + `tools/run_negatives.sh`
(plus the P2 build-system gates — `./build test`, provenance verify,
brand-check scan, argset validate).

## Conventions (binding from commit 1)

1. **Pinned actions, full SHA only.** No `@vN` tags in workflows. The
   current pins (verified 2026-09-07) are documented in the workflow
   header; bumping a pin is a PR with the new tag→SHA mapping recorded
   in the commit message.
2. **Hash-pinned Python deps.** Only `tools/requirements-dev.txt`
   (max PyYAML/jsonschema/pytest, sha256-pinned). No other package
   installs in CI (plan: no unnecessary dependency).
3. **Fail-closed tooling.** Every governance tool exits non-zero on any
   doubt (missing file, parse error, missing pin). CI must never treat
   a tool warning as a pass.
4. **Negatives ship with the gate.** When a new check is added, its
   negative case goes into `tools/run_negatives.sh` in the same commit
   (the plan's P1 "Tests" DoD pattern: the scanner must fail on a
   planted sample).
5. **Range-scoped history checks.** DCO and Register-Change trailer
   checks run over the PR/push range in CI and over full history
   locally (`tools/run_checks.sh [git-range]`).

## What lands here when (plan anchors)

| Phase | Pipeline |
|---|---|
| P2 | hermetic build matrix (3 OS) — **defined** in `nightly-rebase-build.yml` + `build-lane.yml`; runs once HG-9 lands the farm |
| P3 | rebase bot + patch-budget meter, promotion jobs, security fast-lane |
| P9 | fuzz fleet scheduling, SAST, isolation/leak suites (T11's full dep-graph license/advisory scan — the one thing P1's `license_audit.py` explicitly is NOT) |
| P10 | signing, transparency log, update-channel pipeline |

Until those phases, do not add stub pipelines here (anti-stub rule,
plan L5).
