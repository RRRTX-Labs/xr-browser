# The upstream bot (P3 treadmill operations)

Status: ACTIVE (P3) · Owner: @xr/platform · Code: `build/upstream/` · Workflow: `.github/workflows/nightly-rebase-build.yml`

The upstream treadmill keeps XR within days of Chromium main (and on the shipping series) while the patch budget stays enforced. This page documents what the bot does, what it is FORBIDDEN to do, and where humans act.

## Laws the bot obeys

| law | text |
|---|---|
| L24 | the bot NEVER pushes, merges, or opens authenticated issues; it prepares artifacts and LOCAL branches — humans press the buttons |
| §12.3 | conflicts are resolved in patch SEMANTICS; "disable & TODO" is forbidden |
| §12.4 | SLA from TAG PUBLICATION; missed windows freeze feature work (§15-R1) |
| §12.5 | every retired patch is ledgered; `xr-patch retire` is the only sanctioned removal path |
| §12.7 | the never-list (§12.7) is absolute — no telemetry, no phoning home, no exceptions |
| chokepoint | ALL network flows through `build/upstream/fetch.py` (allowlist: chromium.googlesource.com, commondatastorage.googleapis.com, chromiumdash.appspot.com, api.github.com); zero new vendored deps |

## The nightly loop (definitions committed; activation human-gated, HG-19)

1. **Canary rebase** — `./scripts/build rebase rebase --to <latest main>` (gitiles TEXT, zero clone). Verdict GREEN/DRIFT/BROKEN; DRIFT/BROKEN produce owner-routed issue bundles (`docs/contracts/patch-ledger-v1.md`). Drift is EXPECTED output, not a job failure.
2. **Assumption suite** — `./scripts/build assumptions run --use-deps` (§12.4 rows; FAIL = P0 artifact + promotion block).
3. **Fast lane** — `fastlane watch` (new Stable/Extended tags → plans with SLA deadlines) + `fastlane drill` (synthetic rehearsals, `source:"fixture"`).
4. **Promotion discovery** — `./scripts/build promotion discover` (even-milestone Extended series, cadence-as-data from `build/upstream/promotion-config.yaml`).
5. **Retirement lint** — `./scripts/build retire lint` (ledger linkage + removal-without-ledger detection).
6. **Fork health** — `./scripts/build fork-health` regenerates `docs/state/fork-health.md` (SKIP-visible headline chart).

Evidence uploads as workflow artifacts (30-day retention). **No push step exists in the workflow — by design.**

## Promotion (P3-T4; the weekly human loop)

`./scripts/build promotion run` prepares the PR bundle: series discovery (live chromiumdash), candidate rev resolution (gitiles tag), **compat-smoke v0** (argsets validate; xr-patch apply/verify/revert round-trip at the candidate rev over a scratch tree; brand fixtures + endpoint scan; SBOM fixture + gate; the blocking assumption suite), `promotion-report.json`, a prepared `DEPS.promotion-bump`, and `pr-body.md`.

**HG-18**: execution/approval is the on-call human's act (target ≤2 person-hours, 2 consecutive clean promotions before automating further). The verdict is `promo-ready` or `issues` — the job never merges.

## Retirement (P3-T7)

`./scripts/build patch retire --id X --mechanism upstreamed|obsoleted|dropped-with-review --note "..." --evidence "..."`:
appends the ledger row (meta repo) AND surgically removes the patch block + dir (xr-core), with rollback if either half fails. Both repos commit together; `retire lint` fails any removal that lacks a ledger row (including historical ones, when xr-core history is present). The reward metric — **seams retired** — is headline row #2 of the fork-health chart.

## Where humans act

| event | human act |
|---|---|
| canary DRIFT/BROKEN | owner re-anchors per issue bundle (semantics, never disable-and-TODO); re-run canary |
| assumption FAIL | P0 artifact → owner BEFORE any promotion (blocking) |
| promo-ready bundle | on-call executes the DEPS bump PR, approves, merges (HG-18) |
| SLA breach (post-GA) | feature freeze per §15-R1; security release becomes the only work |
| budget OVER | retire a seam or ship a scope decision; the gate stays red until then |
