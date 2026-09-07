# Human gates — P2

Items that are **human/ops-gated by design** in P2. None is faked in P2
artifacts: they appear here, in `evidence.json` (verdict `HUMAN-GATED`), and
in the affected documents (marked as definitions/templates/scaffolds).
Structure follows `evidence/P1/human-gates.md`.

**Extraction note (P3 T0.6, 2026-09-07):** this file consolidates the gate
rows that P2 recorded scattered across `evidence/P2/evidence.json`,
`PHASE2_RELEASE.md` §5, `BUILDING.md`, `build/farm/caching.md`,
`build/branding/icons/README.md`, and `ci/*.yml`. HG-9, HG-10, HG-11 and
HG-14 were explicitly numbered in those artifacts; the two rows P2 left
unnumbered in its gates table ("P10 real code-signing certs" and the
"DR-14/LG-3 Widevine verdict") are assigned HG-12 and HG-13 here — numbers,
not new gates; the gate content is verbatim from the P2 record.

| # | Gate | Why it cannot be done in P2 (agent scope) | Blocking action to unblock | Owner placeholder | Status (2026-09-07) | Blocks |
|---|---|---|---|---|---|---|
| HG-9 | **Build-farm bring-up + runner registration (Linux/mac bare-metal, Win VMs)** | Real hardware provisioning is ops work; P2 ships the lane definitions + runner provisioning scripts only | Register self-hosted runners with labels `xr-linux`/`xr-mac`/`xr-win` (§13.1); verify first `nightly-rebase-build` run on real hardware | RRRTX-OPS-02 | PENDING | 3-OS nightly builds (P2 DoD); real `sync`/`compile` (this sandbox is under-provisioned by design — preflight refuses it) |
| HG-10 | **Branch protection requires the CI lanes** | GitHub-side settings are org-admin work; lanes are committed definitions until then | Enable branch protection on `main` requiring the governance check + build lane on S0-touching PRs | RRRTX-OPS-02 | PENDING | CI definitions become enforced (not advisory); PR-tier gating (§13.1) |
| HG-11 | **Remote ccache endpoint sign-off** | A remote cache is a build-supply-chain vector (§9.11); endpoint + capacity are ops decisions, and the template ships with no real endpoints | Approve endpoint + capacity (ADR-0005), land the real config, record in the runbook | RRRTX-OPS-02 | PENDING | Remote cache tier (local ccache works without it — a miss is slower, never failed) |
| HG-12 | **Real code-signing certs (P10)** | HSM-backed production keys are a principals' + ops act; P2's `sign_artifact.py` is the TEST-cert scaffold and errors on `release`/`stable` channels by design (ADR-0004) | P10 key ceremony: HSM provisioning, cert profiles, notarization service; flip channel policy in one reviewed change | RRRTX-PLATFORM-LEAD | PENDING | Release/stable channel signing; SBOM publication on dev channel (needs a real signed build) |
| HG-13 | **Widevine CDM counsel verdict (DR-14 / LG-3)** | Legal conclusion (platform distribution terms differ; R13); `enable_widevine=false` is the committed default until the verdict | Outside counsel verdict on LG-3; register change + GN default flip only after it | RRRTX-LEGAL-01 | PENDING | Widevine user-initiated download path (P10 exit at the latest) |
| HG-14 | **Real icons after trademark outcomes** | Final iconography depends on HG-5 (trademark filings); P2 ships a generated interim mark + generator | Commission/land final icon set once HG-5 resolves; regenerate + re-verify branding | RRRTX-PLATFORM-LEAD | PENDING | Final brand surfaces (P6 branding task) |
| HG-15 | **T0.1 push-credential grant + history-restoration approval (P3)** | Pushing to origin and restoring rewritten history are owner acts an agent must never self-authorize; the P2 release zips were the only source of the true 30-commit/`6416bf1` history | RRRTX-OPS provided the release archives (Drive) and a push token, and directed the restoration + pushes in the kickoff follow-up (2026-09-07); executed as `git push --force-with-lease=main:d792824…` (xr-browser) and fast-forward `6fb5411..6416bf1` (xr-core); logs in `evidence/P3/logs/t01-*.txt` | RRRTX-OPS | **EXECUTED 2026-09-07** (grant recorded; token single-purpose, revocation advised post-phase) | Origin-green D1/D2 rows (P3 DoD 1) |

## Standing rule (carried from P1)

Any artifact that would read as "live" for a gated item must carry an
explicit marker (PENDING-OPS / UNREGISTERED / DRAFT — NOT ACTIVE / SIMULATED).
The vocabulary lint and review checklist enforce this (L5/L11). If a gate
stays PENDING past the phase that needs it, that phase's DoD row is
`HUMAN-GATED`, not `PASS` — and the block is reported, not papered over.
