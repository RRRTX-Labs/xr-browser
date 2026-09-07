# P3 — human gates (retrofitted 2026-09-07, P4-T0.3 · debt D-C)

P3 shipped `evidence/P3/logs/` only. It never recorded which outcomes require a
human, so the phase could be reported as green while nine hosted runs were red.
This file is the missing half: everything below is an action that **no agent may
perform**, with the exact command a human runs and what "done" looks like.

| gate | what the human must do | exact command / place | done when |
|---|---|---|---|
| **HG-16** | Authorise the issue bot (`api.github.com` is on the fetch allowlist, but the bot prepares bundles and never files them — L24). | `./scripts/build rebase rebase --to <sha> --dry-run --explain` then file owner bundles by hand, or grant a **fine-grained, single-repo, issues:write** token. | An owner-routed issue exists for a real drift event. |
| **HG-17** | Name the fast-lane on-call roster (who acts on an SLA breach). | `docs/runbooks/fastlane-runbook.md` — fill the roster table. | At least one named primary + backup. |
| **HG-18** | Execute the promotion drills against the **real** extended-stable series (P3's were fixtures). | `./scripts/build promotion discover` then follow `docs/upstream-bot.md`. | A real series row is recorded in `docs/state/`. |
| **HG-19** | Activate the nightly cron and confirm the **first scheduled** run is green (not a dispatch run). | Actions → `nightly-rebase-build` → Enable; or `gh workflow run nightly-rebase-build.yml -f reason="activation"`. | A run whose `event == schedule` has `conclusion == success` (check: `gh api repos/RRRTX-Labs/xr-browser/actions/runs --jq '.workflow_runs[] \| select(.event=="schedule") \| {id,conclusion}'`). |
| **HG-20** | **Revoke the over-scoped PAT now.** | GitHub → Settings → Developer settings → Personal access tokens → `ahmadrrrtx` (scope: repo + workflow) → **Delete**. | Token shows as revoked; nothing in either repo references it (verified clean: no `ghp_`/`gho_`/`github_pat_` strings in the trees). Issue a fine-grained replacement limited to the two repos and the scopes a push needs. **No agent ever sees or handles a token.** |
| **HG-21** | Run the P4 identity-seam **runtime** probes on farm hardware. | Requires HG-9 (a compiled browser). Then: `./scripts/build spike --farm` (see `evidence/P4/human-gates.md` for the exact invocation). | `evidence/P4/evidence.json` runtime rows flip from `PENDING-FARM` to measured. |
| **HG-P4-PUSH** | Push the P4 branch so the hosted-CI rows can be **re-measured** rather than asserted. | `git -C xr-core push origin main && git -C xr-browser push origin main` (in that order — see `docs/process/cross-repo-pin.md`), then `gh api repos/RRRTX-Labs/xr-browser/actions/runs --jq '.workflow_runs[0:5] \| .[] \| {id,name,event,conclusion,head_sha}'`. | Every run at the pushed HEAD has `conclusion == success`. |

## What P3 could not have claimed

* **"104 tests pass"** — true only in a pre-seeded environment. On a fresh clone
  the measured result is 103 passed / 1 **FAILED** (`test_fastlane_drills`:
  `FileNotFoundError: 'minisign'`). Fixed in P4-T0.1; re-measured both ways.
* **"this also triggers the live governance CI, whose result I'll verify"** —
  never verified. The result was red: 9/9 runs failed, for two independent
  reasons (a 404 clone URL and the missing external tool). Both are fixed in
  P4-T0.1 and the re-measurement is HG-P4-PUSH.
* **"xr-core BUILD.gn is a successor-commit item"** — it never arrived. It is
  xr-core commit `56b4ebb` in P4-T0.2, pending push.

## Standing rule

A gate is not closed by an agent writing that it is closed. It is closed when
the command above has been run by a human and its output is cited in a later
evidence bundle.
