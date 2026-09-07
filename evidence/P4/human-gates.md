# P4 — human gates

Nothing below can be done by an agent. Each gate states the exact command and
what "done" looks like; a gate is closed when a human has run it and its output
is cited in a later evidence bundle.

| gate | what | exact command | done when |
|---|---|---|---|
| **HG-20** | Revoke **both** over-scoped PATs **now** | GitHub → Settings → Developer settings → Personal access tokens → `ahmadrrrtx` (repo + workflow) → **Delete** | Token revoked. Both repos verified free of `ghp_`/`gho_`/`github_pat_` strings (see `logs/no-token-scan.txt`). Issue a fine-grained replacement limited to the two repos. **No agent ever sees or handles a token.** |
| **HG-21** | Farm executes the runtime identity-seam probes | `./scripts/build sync --checkout ./chromium` → apply `spike/patches/0042-seam-hook/0042-seam-hook.patch` → build `//xr/spike:probes` → `./scripts/build spike probe --farm --binary <browsertest> --checkout ./chromium` | `docs/spike-identity/probe-matrix.md` rows flip from PENDING-FARM to measured, and `evidence/P4` gains a farm bundle. Requires HG-9 (compiled browser). |
| **HG-22** | Org settings, **only if** hosted-green is blocked by admin-level permissions | Settings → Actions → General | Only if a run fails for an org-permission reason rather than a repo/YAML reason. Not currently indicated. |
| **HG-23** | Platform + Security lead ratification of ADR-0042 | Review `docs/adr/0042-identity-seam.md`; sign off in the PR | ADR status flips PROPOSED → ACCEPTED (or SUPERSEDED with a new ADR if F1/F2/F3 fired). |
| **HG-24** | P5 identity-adjacent contract freeze | Orchestrator sequencing **after** HG-21 | Freeze happens only with runtime results in hand. Drafting (`IdentityProvisioning` notes in ADR-0042) is allowed now. |

## Why the push is gated rather than done

The agent has no credentials and must not acquire any. The two root causes that
made all nine hosted runs red are fixed in the tree (404 clone URL → the org
repo; missing `minisign` → installed in CI, and SKIP-visible when absent), but
"the fix works on GitHub" is a claim that only a run can make. It is recorded
as `BLOCKED-PENDING-PUSH`, not as VERIFIED.

## HG-P4-PUSH — CLOSED 2026-09-07

Pushed in the required order (`docs/process/cross-repo-pin.md`):

| repo | range | contents |
|---|---|---|
| `xr-core` | `c34cd66..1ee5f4c` | `//xr:xr_all` mount (D-B); identity-seam spike kit + 0042 candidate patch |
| `xr-browser` | `e35f332..c0af9d2` | P4-T0.1..T0.4 debt closure, the P4 spike, the paired DEPS bump, and the workflow-expression fix |

Both repos are in sync with `origin/main` (verified by comparing `git rev-parse HEAD`
against `GET /repos/{owner}/{repo}/commits/main`).

**Re-measured after the push: run `34145834427` — `governance`, event `push`,
head `c0af9d2`, `conclusion: success`, 1 job, 12/12 steps.** The `nightly-rebase-build`
workflow is green on dispatch (`34145296332`, success) and still produces a spurious
0-job run on push events, which is `actions/runner#4001`, not a defect here.
