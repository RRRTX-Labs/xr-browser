# Research log — P3 (Upstream tracking machinery)

- **Phase:** P3 (Plan §4; tasks XR-P3-T1..T7)
- **Executed:** 2026-09-07 (UTC), live from the phase sandbox (network egress available)
- **Method:** every claim below was executed against the live endpoint from this
  sandbox on 2026-09-07 and the raw observation recorded. Items that could not
  be verified live are marked **UNVERIFIED** with the exact error. The log
  follows the P1/P2 research-log discipline: URL + date + observed quote/result.

## R1 — gitiles JSON APIs on chromium.googlesource.com (the zero-clone primitives)

All against `https://chromium.googlesource.com/chromium/src` (2026-09-07):

| Primitive | Form | Result |
|---|---|---|
| Log (branch) | `+log/refs/heads/main?format=JSON&n=N` | **200.** Returns `)]}'`-prefixed JSON; entries carry `commit`, `tree`, `parents`, `author`, `committer` (RFC dates), `message`. Sampled tip `f6f91ad8ff0e0…` (committer "Chromium LUCI CQ", Mon Sep 07 13:36:48 2026). |
| Log (range) | `+log/<rev1>..<rev2>?format=JSON&n=N` | **200** (public without path scope). |
| Log (path-scoped) | `+log/refs/heads/main/<path>?format=JSON` | **403 Forbidden — "Please sign in to view the history pages."** Path-scoped history is auth-gated; per-file last-touch attribution is NOT available anonymously. Design consequence: issue bundles carry range logs + file contents, and document the path-scoped limitation. |
| File at rev | `+/<rev>/<path>?format=TEXT` | **200.** Base64 body. Verified: `chrome/app/theme/chromium/BRANDING` at pin `d04cdb24…` returns the real Chromium BRANDING file (`COMPANY_FULLNAME=The Chromium Authors` … `MAC_BUNDLE_ID=org.chromium.Chromium`). ~0.2 s/file observed. |
| Directory at rev (archive) | `+archive/refs/heads/main/<dir>.tar.gz` | **200.** Whole-directory snapshot at a rev in one request. |
| Ref lookup (exact) | `+refs/tags/152.0.7977.82?format=JSON` | **200.** `{"refs/tags/152.0.7977.82": {"value": "d04cdb24d67b081f6cf80200ffc5233f44b61109"}}` — **the tag resolves to exactly our DEPS pin** (pin provenance re-verified live). |
| Ref prefix listing | `+refs/tags/<prefix>?format=JSON` | Empty body (not a usable prefix filter). Discovery therefore enumerates candidate tags from chromiumdash releases (R3) and verifies each with the exact-ref lookup. |
| Commit detail | `+/<rev>?format=JSON` | **200** (parents, tree, message). |
| `+/<rev>^!?format=JSON` (per-commit file list) | — | **400.** Per-commit file lists are not served in this form; the cherry-pick plan carries commit metadata (SHA/subject/author date) from the range log, and files when obtainable from range diffs. Documented recall limit, not a silent gap. |

## R2 — Partial/shallow fetch feasibility (measured; decides the real-rebase lane's cost)

All measurements from this sandbox, 2026-09-07, against
`https://chromium.googlesource.com/chromium/src`:

| Fetch form | Measured result |
|---|---|
| `git fetch --depth 1 <url> <sha>` (arbitrary-SHA want, unfiltered) | **TIMEOUT >300 s** (server accepts the want; the transfer is a full-snapshot pack — never completed) |
| `git fetch --depth 1 --filter=tree:0 <url> <sha>` | **TIMEOUT >180 s**, 0 bytes landed (filter not honored for this form) |
| `git fetch --depth 1 --filter=blob:none <url> <sha>` | **TIMEOUT >150 s**, 0 bytes landed |
| `git fetch --depth 1 --filter=blob:none <url> refs/heads/main` | **13.6 s, 19.0 MB** — works and is cheap (commit+trees, no blobs; promisor lazy-fetch on checkout) |
| gitiles `TEXT` file fetch | ~0.2 s per file (R1) |

**Conclusion (drives the design):** arbitrary-SHA `git` wants are server-side
expensive on googlesource (all three forms time out from this environment);
a **branch-ref** `blob:none` depth-1 fetch is viable (13.6 s / 19 MB) for
farm-scale lanes that need a real checkout. For P3's classification job the
correct primitive is the **zero-clone gitiles TEXT/archive fetch of only the
patch-touched files at each rev** — measured ~0.2 s/file, no repo, no SHA-want.
`build/upstream/fetch.py` implements exactly that, with the branch-ref
`blob:none` form documented as the P4+ farm lane. Recorded as UNVERIFIED for
environments with different egress shaping: nothing about googlesource's
SHA-want slowness can be claimed outside this sandbox's observations.

## R3 — Milestone/cadence truth right now (R9 snapshot, 2026-09-07)

Live sources queried 2026-09-07:

- `https://chromiumdash.appspot.com/fetch_milestones?n=8` → **200** (JSON;
  M59..M154 present). M153 = branch **8010**, main-branch position 1681091;
  M154 = branch **8037**, position 1689415 (matches main's live tip position);
  M152 = branch **7977**, position 1669021 (matches the P2 pin provenance).
- `https://chromiumdash.appspot.com/fetch_releases?channel=…&platform=Windows&num=N` → **200** (JSON; **allowlisted** domain). Observed 2026-09-07:
  - **Stable: 153.0.8010.27** (previous 153.0.8010.12), milestone 153
  - **Extended: 152.0.7977.83** (previous 152.0.7977.76), milestone **152 — the current even-milestone Extended-Stable series** (Plan §12.1's promotion target series)
  - **Beta: 154.0.8037.0** (154 branched), **Dev: 155.0.8040.2**
  - each row carries `time` (epoch ms), `previous_version`, and per-component `hashes` (chromium hash included)
- `https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/{stable,extended,beta}/versions?pageSize=N` → **200** (cross-check source; **NOT on the fetch allowlist** — research/cross-check only, never a runtime dependency). Precise serving times observed: 153.0.8010.12 → 2026-08-26T17:09:31Z; 152.0.7977.83 → 2026-09-03T18:49:05Z; 153.0.8010.27 → 2026-09-03T20:12:07Z. chromiumdash `time` for 153.0.8010.27 (1788466327614 ms) matches versionhistory's serving start to the millisecond — **chromiumdash (allowlisted) is the SLA clock source of record**.
- Google (blog.google, "Stronger with every update: How we're making Chrome and the web safer in the AI Era", 2026-07-30), quote: *"We are in the process of transitioning to a two-week cadence for major Chrome milestones, with weekly security updates."*

**Cadence-state snapshot (answers the R9 "2026-09-08 — tomorrow" note):** the
two-week milestone cadence is **in effect**: the M153 series is on Stable
(153.0.8010.12 went stable 2026-08-26; 153.0.8010.27 on 2026-09-03 — a
second security bump within the same milestone series, consistent with the
weekly-security-update statement), M154 is already on Beta, and the
**even-milestone Extended-Stable series is M152** (152.0.7977.83 backported
2026-09-03). No plan contradiction found: R9's ruling (daily canary rebase;
8-week even-milestone promotions; security tags decoupled) matches live
reality. The promotion job encodes cadence as **data** (channel, milestone
parity, schedule) in `build/upstream/promotion-config.yaml`, never hard-coded
week math.

**SECURITY_NOTES.md (falsified assumption → draft-issue):** the phase research
brief expected `chrome/desktop/SECURITY_NOTES.md` to exist at the pin.
Observed: **HTTP 404 at the pin `d04cdb24…`, at main HEAD, and the directory
`chrome/desktop/` does not exist at all on main** (gitiles listing of `chrome/`
shows `app, browser, child, common, …` — no `desktop`). A web search for
in-tree per-release security notes found no such file; per-release security
information is published on the Chrome Releases blog (blogspot — not
allowlisted) and machine-readably via chromiumdash releases (allowlisted).
Design consequence: the fast-lane watcher watches **chromiumdash releases +
gitiles tag existence** (both allowlisted, both with publication timestamps),
not an in-tree SECURITY_NOTES file. Filed as `docs/adr/draft-issue-0001-security-notes-source.md`
(Plan untouched, per the date-sensitivity rule).

## R4 — Upstream security-commit conventions at the pinned rev (what detection can honestly claim)

Sampled `+log/refs/heads/main?format=JSON&n=100` (2026-09-07; newest
2026-09-07 13:36:48, oldest 09:27:39 — ~4 h of main traffic):

- **CVE- references in commit messages: 0/100.** CVEs are assigned/published
  at release time on the release-notes channel, not in the commits.
- Marker counts: `Bug:` footer 68/100 (new buganizer form `Bug: b:522291279`),
  `Reviewed-on:` 100/100, `Cr-Commit-Position: refs/heads/main@{#N}` 100/100,
  cherry-pick backports 0/100 (main carries originals; backports live on
  branch-heads), incidental "security" wording 3/100 (none a severity marker).
- Standard footer shape (observed):
  `Bug: b:… / Change-Id: I… / Reviewed-on: https://chromium-review.googlesource.com/c/chromium/src/+/… / Reviewed-by: … / Commit-Queue: … / Auto-Submit: … / Cr-Commit-Position: refs/heads/main@{#…}`

**Honest recall limits (documented in the fast-lane tool and SLA contract):**
security fixes are **not distinguishable from ordinary commits by message
markers on main** — severity labels live in the (access-restricted) tracker.
Therefore XR's fast-lane detection is **release-driven** (new
Stable/Extended-stable version + tag ⇒ security-bearing release until proven
otherwise), with commit-message heuristics (`CVE-`, security wording) as
*advisory enrichment only*. A missed fix is an SLA breach (L6): the design
fails toward *more* candidates (every new stable/extended release is a
candidate), never fewer. Per-commit file lists are not anonymously available
(R1 `^!` → 400), so cherry-pick plans carry commit metadata from the public
range log; the files list is filled from the branch diff when a checkout
exists (P4+ farm lane).

## R5 — `git apply --3way` / `git merge-file` semantics (classification engine)

Measured locally (git 2.47.3) on synthetic trees, 2026-09-07:

- `git apply --check` — clean check at identical base: OK.
- `git apply --3way` **requires the patch's pre-image blob to exist locally**
  (`index` line hashes). Observed failure mode without it:
  `"error: repository lacks the necessary blob to perform 3-way merge. Falling back to direct application…"`.
  Since git blobs are content-addressed, a scratch repo committed with the
  **pin-rev file content** reproduces the exact base blobs — but the XR patch
  corpus carries plain unified diffs **without `index` lines** (verified: the
  real `0001-brand-ui.patch`), so `--3way` cannot key off them.
- `git merge-file` (base/ours/theirs, blob-level): **rc=0 ⇒ clean three-way
  merge (textual drift), rc>0 ⇒ conflict count (semantic conflict), missing
  theirs-file ⇒ file-deleted**. This classifies drift **without** needing
  patch `index` lines, using only content the bot already fetches
  (pin content = base, patched-pin content = ours, target content = theirs).
- Classification engine (T1) therefore: apply patch to pin-rev files in a
  scratch repo (must be clean — the patch's recorded base), then merge-file
  each file against the target-rev content. Classes produced:
  `clean | textual-drift(3way-ok) | semantic | file-moved | file-deleted`
  (file-moved: target file absent but the pin-content blob reappears under a
  different name in the target-rev directory archive — content-hash match).
- `git log --follow -- <path>` — works only with a local history (not
  available zero-clone; see R1 path-scoped 403). Documented limitation for
  issue bundles.

## R6 — GitHub: `gh` CLI + Actions (definitions only; no hosting claims)

- `gh` CLI: **absent in this environment and in CI** (`command -v gh` fails);
  the dependency rule is absent-tolerant. Documented minimal authorization for
  `gh issue create` (docs.github.com / cli.github.com, read 2026-09-07):
  classic PAT `repo` scope, or fine-grained token with *Issues: Read and write*
  (+ *Metadata: Read*) on the target repository. XR wires this only as
  `XR_ISSUES_TARGET=github` producing a ready-to-run command script
  (`gh-commands.sh`) — **no credential is read or used by the bot**; actual
  filing is human-gated (HG-16). Mini-eval: `docs/dependencies/github-api.yaml`.
- Actions `schedule:` (cron), `workflow_dispatch:`, `concurrency:` groups,
  self-hosted runner labels (`runs-on: [self-hosted, xr-linux]`-style) are
  committed YAML **definitions** in `ci/` — nothing is claimed to "run
  nightly" until HG-19 enables it. Pinned-actions discipline
  (`docs/process/pinned-actions.md`) applies to any future live workflow.
- Governance CI (`.github/workflows/governance.yml`) is live on every push;
  this phase's new gates run there.

## R7 — Plan anchors (transcribed verbatim for the DoD rows)

From the pinned plan `docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md`
(sha256 `02743146…65a7b`, verified by `tools/plan_pin_check.py` this session):

- **§12.1** "`xr-core@main`: **daily** rebase onto Chromium canary (bot). Conflicts ⇒ auto-issue to owning team with context (§4 P3-T2); the queue is the *truth* of fork health, public." / "Never pause the bot for deadlines; never merge a feature branch onto an un-rebased tip."
- **§12.2** "Manifest `patches/manifest.yaml`: `{id, files[], category, owner, risk(S0..), upstream_bug?, rebase_notes, retirement_plan}` per patch file… Tooling: `xrctl patches audit` (drift, orphans, budget), CI-blocks unregistered diffs in `src/` outside `src/xr`."
- **§12.3** "Rebase-merge onto pinned chromium rev; conflicts resolved in *patch semantics*, never by dropping hooks ('disable & TODO' is forbidden — a patch that can't be carried is *retired with a user-visible consequence* + review entry)."
- **§12.4** "Security fast-lane (P3-T5): 72 h critical/IIT / 14 d high SLA from *tag publication*… missed window ⇒ feature freeze (§15 R1's kill-switch…). **Upstream-assumptions suite:** … Site Isolation partition-suitability rule, `GetStoragePartitionConfigForSiteInstance` contract, per-partition NetworkContext, HCMS mediation points, extension dispatch funnel, component-updater signature path, Safe Browsing v5 mode APIs. Each gets an *assumption test*… runs per rebase; failures = P0 to the owning team *before the promotion lands*."
- **§12.5** "Metrics published per promotion: patched-file count (budget meter), **seams retired**…, WPT delta, crash-rate vs Chrome, SLA adherence."
- **§1.2 budget table** (transcribed into `build/upstream/budget-config.json`): branding/defaults **unlimited-ish (cheap)**; hook points **~45 files**; Blink seams **~25**; content/ seam uses **~30**; NetworkService seam **~20**; UI **~35**; extension chokepoint **≤2**; **total upstream-touched files ≤150, enforced by CI, count published per release**.
- **§15-R1** (kill-switch → feature freeze on missed SLA windows; referenced by §12.4 and L20), **§15-R20**: not present as R20; the anti-divergence register row is **R1**; **L20** = "Rebase is oxygen. No release, deadline, or demo outranks the SLA; a missed window twice in a quarter freezes feature work. (§12.4 kill-switch)". **L10** = "No unnecessary Chromium divergence. Patch budget is law; hooks over in-lines; 'upstream or delete' per promotion; every patch has a retirement plan. (patch ledger + budget meter)".
- **§4 P3 rows:** Tests — "synthetic rebase drill — inject a fake upstream refactor across 5 XR patches, verify classification+issues+fix; budget-break injection fails CI." / Manual — "2 consecutive real promotions executed by on-call, ≤2 person-hours each." / Perf — "rebase bot wall-clock ≤ 8h end-to-end." / DoD — "3 consecutive upstream ranges auto-rebased green; published budget meter; two synthetic security-fast-lane drills < 72h."
- **Budget cross-check (evidence duty):** P2's `build/patching/categories.py`
  caps — hook_points 45, blink_seams 25, content_seams 30, network_seams 20,
  ui 35, extension_chokepoint 2, branding uncapped, TOTAL_CAP 150 — **match
  the §1.2 table exactly**; no drift found (recorded in evidence/P3).

## R8 — DCO/commit conventions for this phase's commits (house)

`tools/dco_check.py` (P1) requires `Signed-off-by` email == committer email on
every commit; the restored true history (30 commits) passes 90/90 after the
T0.1 restoration. All P3 commits use `XR Platform <platform@rrrtx.example>`
with `-s`. Conventional scopes: `upstream(rebase|budget|issues|…)`,
`ci(promotion)`, `build(remediation)` (T0). No Register-Change trailers
unless a DR row changes (none do).

## UNVERIFIED (recorded, never guessed)

- googlesource SHA-want behavior **from other networks** (only this sandbox's
  timeouts are claimed).
- `gh` CLI runtime behavior (binary absent everywhere XR runs it today) — only
  its documented authorization surface is cited.
- Chrome Releases blog contents as a *runtime* source (not allowlisted; used
  only as research context for where security notes are published).

## R9 — Live series state at P3 execution (2026-09-07; promotion-config.yaml transcription source)

chromiumdash (allowlisted, via fetch.py): **Stable 153.0.8010.27 (M153 —
the first two-week-cadence series, live)**; **Extended 152.0.7977.83
(M152 — the current even-milestone series)**; Beta 154.0.8037.0 (M154
branched). Promotion follows Extended/even-milestone (§12.1, R9 rule);
cadence lives in `build/upstream/promotion-config.yaml` as DATA — a further
upstream cadence change is a config edit + a research-log row, not code.

## R10 — Pin-surface verification for the §12.4 rows (gitiles TEXT @ pin d04cdb24…, 2026-09-07)

Verified per file BEFORE encoding assumptions.yaml (L5: no guessed strings):

- `content/browser/browser_context.cc` L138
  `site_instance->GetSecurityPrincipal().GetStoragePartitionConfig()` and
  L159 `SiteInfo::GetStoragePartitionConfigForUrl(this, url)` — the plan's
  verbatim symbol `GetStoragePartitionConfigForSiteInstance` **does NOT
  exist at the pin** (the API evolved). A2 encodes the EVOLVED surface;
  further drift = FAIL = P0 before promotion. Deviation is documented, not
  silent (draft-issue-0002).
- `services/network/mojom/network_context.mojom` L1024 `interface NetworkContext` ✓
- `components/permissions/permission_context_base.h` L92 `class PermissionContextBase` ✓ (HCMS mediation surface for P15)
- `extensions/browser/extension_function_dispatcher.h` L48 `class ExtensionFunctionDispatcher` ✓
- `components/crx_file/crx_verifier.h` L47 `VerifierResult Verify(` ✓
- `components/safe_browsing/core/browser/db/v5_get_hash_protocol_manager.h` exists ✓ (v5 APIs)
- A1 (Site Isolation partition-suitability RULE) stays **pending-feature**:
  needs runtime tests (P4/P12), SKIP is visible and never passes (L6).

Live suite run at pin: **6 PASS / 1 SKIP (A1) / 0 FAIL** (`evidence/P3/logs/t6-assumptions-run.txt`).

## R11 — Real-ranges lane results (T1; gitiles TEXT only; XR_LIVE_NET gated)

- pin d04cdb24 → main e3b770a13414 (2.576s, 724,198 B): **GREEN**
- pin d04cdb24 → main c60b3b1cdb2f (2.012s, 384,343 B): **GREEN**;
  LOCAL candidate branch `rebase/chromium-c60b3b1cdb2f` prepared (never
  pushed, L24). Branding patch 0001 applies cleanly at both targets.
- Wall-clock per range: seconds, not hours (the ≤8h budget holds trivially
  for classification; full build time is P9's farm concern).
- xr-core sibling was at c34cd66 (T0.4) ≠ DEPS pin 6416bf1 → the rebase
  bot correctly REFUSED until DEPS was bumped to the sibling's main
  (sanctioned operator edit this phase; same patch set, docs-only delta).

## R12 — Drills, promotion, retirement (T5/T4/T7 execution evidence)

- Fast-lane drills: **2/2 PASS** (in-window 30h → no breach/marker; breach
  80h → marker written), each drill's negative proved `--channel stable`
  structurally refused; elapsed fields honest (real ≈0.12s vs simulated
  30/80h). `evidence/P3/logs/t5-fastlane-drills.txt`.
- SLA clock vs the real tag 152.0.7977.83 (published 2026-09-03T18:49Z):
  critical deadline 2026-09-06T18:49Z, breached by 19.63h at run time —
  recorded as ADVISORY-ONLY pre-GA (no XR stable until P10; the note rides
  in the JSON itself). Backdated `--at` demo shows 54.82h remaining (in-window).
- Promotion run (live discovery): Extended M152 152.0.7977.83 → candidate
  79460ebecaa5…; compat-smoke v0 **6/6 GREEN** (argsets, brand fixtures +
  scan, SBOM fixture+gate, patch round-trip at the candidate rev over a
  gitiles-fetched scratch tree, blocking assumptions) → **promo-ready**
  bundle prepared locally (never merged; HG-18). `evidence/P3/logs/t4-promotion-run.txt`.
- Retirement: `xr-patch retire` proven on a COPY of xr-core (ledger row +
  surgical manifest removal + rollback on failure); removal-without-ledger
  negative FAILS `retire lint` (exit 1); ledgered removal PASSES.
  Zero-baseline ledger committed (0 rows — stated, not hidden).
  `evidence/P3/logs/t7-retirement.txt`.

## R13 — Where P3 tools landed (map for reviewers)

`build/upstream/{fetch,classify,fixtures,issues,rebase_bot,gen_budget_config,
assumptions,assumptions.yaml,budget-config.json,promotion,promotion-config,
fastlane,fastlane_drills,retirements,retirements.json,fork_health}.py` +
`tests/`; `build/patching/retire.py` (xr-patch retire); splits keep every
file under the 400-LOC law; `tools/fetch_allowlist_check.py` (chokepoint).
dispatcher subcommands rebase/promotion/fastlane/sla/assumptions/retire/
fork-health/budget/audit; xr-patch `retire`; CI: governance.yml P3 gates +
nightly-rebase-build.yml (definitions; HG-19 gates activation);
contracts patch-ledger-v1 + sla-metrics-v1; docs upstream-bot.md +
runbooks/fastlane-runbook.md + dependencies/github-api.yaml; state docs
budget.md + fork-health.md (generated).
