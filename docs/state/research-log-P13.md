# P13 research log

Every external claim this phase makes, with the fetch that produced it. Rows that
could not be fetched say `BLOCKED-NET (sandbox egress)` and name the method; no
row is a remembered value. Written 2026-09-29; appended as the phase proceeds.

## Fetch transcripts

| # | what | endpoint / command | result |
|---|---|---|---|
| R1 | token identity + scopes (before any push) | `GET api.github.com/user` | 200 — user `ahmadrrrtx`; scopes `repo`, `workflow`, `read:org`, `read:user`, … (never echoed; used only through `/home/user/.gitcred.sh` at push time) |
| R2 | both repos reachable, default branch | `GET api.github.com/repos/RRRTX-Labs/{xr-browser,xr-core}` | 200 — public, `default_branch: main`, admin permission on both |
| R3 | the sandbox's upstream egress | `curl https://chromium.googlesource.com/...` | **HTTP 503 in ~0.08 s** (reproduced again in P0-D: `FetchError … after 3 attempts: HTTP Error 503`). Every network-dependent lane in this sandbox is labelled `BLOCKED-NET (sandbox egress)`; the runner is the proof. |
| R4 | registry reachability (for the WebUI lane) | `curl https://registry.npmjs.org/` | 200 — so WebUI lanes are *installable*, never labelled BLOCKED-NET; `npm ci --ignore-scripts` in `xr-core/ui/toolchain` is the method |
| R5 | the public CI surface (P0-B) | `GET commits/<sha>/check-runs`, `GET check-runs/<id>/annotations`, `GET actions/runs/<id>/jobs`, `GET actions/runs/<id>` | all **200 unauthenticated**; `GET actions/runs/<id>/logs` **403** (admin-only). Table + shapes: `docs/process/ci-triage.md`; recordings: `tools/fixtures/ci_triage/` |
| R6 | the red that started the phase | `GET check-runs/108170646843/annotations` (8db682f) | annotation text verbatim: `Process completed with exit code 126.` at `.github:21`, check-run `governance`; job `108170646843`, failing step 9 `Governance checks`, 10 steps skipped |
| R7 | P0-A's push (9979cd0) | `GET commits/9979cd0/check-runs` | the mode defect is gone: annotation is now `Process completed with exit code 1.` at `.github:39`, same step. The failure was a banned vocabulary word in `docs/process/ci-invocation.md` this phase added — reproduced locally (`work/p13-p0a-localgate.log:18`) |
| R8 | P0-B's push (ea996d9) | same endpoint + `GET actions/runs/<id>/jobs` | still `exit code 1` at the same step, and this time the cause was reproduced locally before any fix: `tools/fetch_allowlist_check.py` rejects any HTTP call outside the chokepoint — the first draft of `tools/ci_triage.py` called `urllib` directly (`evidence/P13/logs/p0b-fetch-allowlist-fix.txt`). Fixed by routing through `build/upstream/fetch.py` |
| R9 | P0-D: the treadmill's failing step | `GET actions/runs/<id>/jobs` for the scheduled treadmill runs | failing step `Canary rebase (classify at latest main; issues on drift)` — the step whose contract P12-CLOSE's `49fcf47` made explicit: a *classified* verdict (GREEN/DRIFT/BROKEN) exits 0, a *crash* (ToolError) exits 1 |
| R10 | P0-D: the crash shape, reproduced | `GitilesFetchSource().ref_value("heads/main")` here | `FetchError: fetch failed for https://chromium.googlesource.com/chromium/src/+refs/heads/main?format=JSON after 3 attempts: HTTP Error 503: Service Unavailable` → exit 1. Same shape as the hosted red, and it is network weather, not drift |
| R11 | P0-D: what still works offline | `./scripts/build promotion discover`, `retire lint`, `fork-health` | promotion series read live via **chromiumdash** (an allowlisted host that works here): `latest 152.0.7977.140, prev 152.0.7977.134, published 2026-09-22T18:09:56Z`; retirement lint PASS; fork-health rows OK/SKIP-visible |
| R12 | P0-D: the two propagation lanes | `GET actions/runs/<id>/jobs` for `36544991058` (compat-beta-parity) and `36412999029` (sast) | failing step is their own `Scheduled-lane health` step only — their analysis steps are green; the red is the treadmill's (P12-T0-c's documented exemption shape) |

## Claims the phase makes, and where they are checked

* `ci_triage` "never guesses": `--offline` with a missing fixture prints
  `BLOCKED-NET (offline fixture missing: …)` and exits 77 with **no verdict
  line** (`tools/tests/test_ci_triage.py`, negative case in
  `tools/negatives/p13_p0b.sh`).
* The finality law's four cases: `tools/negatives/p13_p0c.sh` (final+no ci-run
  red; final+parent-SHA ci-run red; final+PENDING red; interim+PENDING green),
  plus the in-flight and presence-law controls in the same file.
* The P12 refresh is append-only: every changed status is a new row carrying
  `corrects`, quoting the original (`tools/evidence_finality.py::_effective_rows`
  is what reads it; `tools/evidence_ci.py` uses the same field for hosted-claim
  corrections).
* No numbering here is remembered: the commit counts, vector counts, row counts
  and sha256s quoted in `evidence/P12/report.md` §① and §⑨ were re-derived in
  this turn from the tree itself.

## R13 — the negatives harness lost a verdict to SIGPIPE (2026-09-29)

`printf '%s' "$out" | grep -q PAT` under `set -o pipefail` returns 141 when
`grep -q` exits at its first match and the writer then takes SIGPIPE. On a
~30 KB transcript that reads, inside `if ! ...`, exactly like "the expected
reason is absent": a correctly-behaving case reported as a harness failure.
Reproduced deterministically at 3000 lines/20 KB; fixed by taking every verdict
off a FILE (tools/negatives/lib.sh `neg_out_file`/`neg_out_has`/
`neg_out_has_fixed`, and one `find | grep -q` rewritten to `[ -n "$junk" ]`).
Transcript: evidence/P13/logs/negatives-harness-fix.txt.

## R14 — the sandbox workspace drops `.git` (and `build/`) between turns

Twice in this phase the shared workspace came back without both clones' `.git`
directories and without every name in the snapshot exclusion list (`build/`,
`dist/`, `.local/`), and without the executable bits on tracked scripts. The
working files survive; the repository state does not. Recovery that works:
clone into a scratch dir, copy the fresh `.git` into the working tree, restore
the deleted tracked files (`git restore --worktree --source=HEAD
--pathspec-from-file=<(git ls-files -d)`) and re-apply the index modes
(`git ls-files -s | awk '$1=="100755"{print $4}'`). Nothing pushed was ever
lost — the remote is the source of truth, which is why every landing in this
phase ends with a push.

## R15 — the hosted gate's S-01 step is weather (2026-09-29)

`chromium.googlesource.com` answered this sandbox with HTTP 503 continuously
through the phase, and at 17:52 UTC the hosted governance run failed on the
same step for the same reason ("S-01 - BLOCKED-NET cannot fetch
content/public/browser/content_browser_client.h at d04cdb24…: fetch failed …
after 3 attempts", annotation .github:134 in run 36610931823). The next run
(fa5e35e) passed S-01 and failed only on the P12 finding, so the step is
intermittent, not broken: same-milestone measurements in docs/state/research-log-P11.md
were taken when it was up. The gate fails closed on no network by design; the
honest handling is a recorded BLOCKED-NET, never a softened check.

## R16 — what a sandbox can honestly measure about the panel (T7)

Two numbers are measurable without a browser: the frame's pure-core decision
cost (median 0.0046 ms over a 4096-focusable synthetic document) and a COUNT —
the open path reads exactly one subtree, its own. The second is the interesting
one: it makes "lazy tabs" falsifiable without a clock, so the claim does not
depend on the machine that produced it. The browser numbers (open ≤150 ms, ring
≤16 fps) stay NOT-RUN with methods in docs/qa/browser-harness.md; a surrogate
that dressed as the Blink rig would be the phase's disqualifier.

## Upstream-first ledger

Nothing in P13 diverges from upstream in a way that needs a filed issue; if that
changes, the entry lands here with the upstream path named and **no invented URL**
(HG-32: filing upstream is a human act).

## C-item citations (appended as the phase proceeds; every claim cites an artifact)

| C-item | Claim | Citation |
|---|---|---|
| C-0.1 | the §10 unit is a DECLARED tab/section; `focus-trap.ts`/`panel-frame.ts` are the frame, not tabs | `docs/contracts/coverage-allowlist.yaml` (`panel/xr`, `unit: frame`, `sources:`), `tools/coverage_check.py` R1–R5 |
| C-0.1 negatives | a landed undeclared surface bites; a non-tab source claimed under `panel/xr` is green; `skip:` is not a fix | `tools/negatives/p13_c01.sh` cases 1–6 |
| C-0.1b | a11y/pseudo-locale/l10n artifacts regenerated at the pin | `docs/qa/axtree-snapshot.json`, `docs/qa/qyy/xr_strings.qyy.txt`, `docs/qa/l10n-ratchet.json` |
| C-0.1c | no verdict-bearing assertion compares an embedded count literal; the grdp count is derived twice | `tools/l10n_count_law.py`, `tools/checks/p13_gates.sh::p13_l10n_count_law`, `tools/negatives/p13_c01c.sh` |
| C-0.2 | every sibling consumer is routed through one resolver, and the pin is proven before a verdict | `tools/xr_sibling.py`, `tools/sibling_pin_check.py` (59 readers classified), `docs/process/cross-repo-pin.md`, `tools/negatives/p13_c02.sh` 1–5 |
| C-0.3 | `--require-phase-final` binds on a `Phase-Close:` trailer; an in-flight phase may be interim without claiming closure | `tools/evidence_finality.py`, `docs/contracts/evidence-bundle-v1.md`, `tools/negatives/p13_c03.sh` 1–3 |
| C-0.4 | P12 is `interim` by decision (option (a)), with a dated reason: a same-head green `governance` run does not exist and cannot be created four commits back | `evidence/P12/evidence.json` (`state`, `not_done_by_design[#]`), `evidence/P13/report.md` §9 |
| C-0.5 | no VERIFIED row whose own text is false; every cited path in a bundle/report/human-gates exists | `tools/doc_reference_check.py`, `tools/negatives/p13_c05.sh` 1–4 |
| C-0.6 | the three-exit-code lane shape is load-bearing (`else … die`) | `tools/checks/p13_gates.sh::p13_exit_code_lane`, `tools/negatives/p13_c06.sh` 1–5 |
| C-1 (T2) | the Site tab reads ONE scope object; generic hides are not exception-able; isolation rows render NOT-RUN; scriptlets state INERT | `xr-core/ui/panel/site-tab.ts`, `ui/panel/tests/site-tab.test.mjs`, `docs/panel/site-tab.md` |
| C-2 (T3) | ring cap 2000 with drop count; window clamps; a11y rowcount = filtered total; export refuses by class and the refused bytes never reach the writer; both formats share one field list | `xr-core/ui/panel/observatory-tab.ts`, `tools/observatory_export.py --check`, `tools/tests/test_p13_c2_observatory.py`, `tools/negatives/p13_c2.sh` 1–5, `docs/panel/observatory.md` |
| C-2 enums | the export carries every enum-bearing ledger field; it may not invent a column | `tools/shield_state_check.py::observatory_findings`, `tools/observatory_export.py::FIELD_ALIASES` |
| C-3 (T4) | context is origin/UA-less tag/rule/list/action by schema; six smuggle classes refused pre-send with the match WITHHELD; `queue: fixture`; SLA is data; no network code | `docs/contracts/breakage-report-v1.{schema.json,md}`, `tools/breakage_report.py --check`, `tools/negatives/p13_c3.sh` 1–3, `docs/panel/breakage-report.md` |
| C-4 (T5) | the update tab's verb set is closed (no install/restart/apply) and its states cannot read as progress; the implication that an update happens by itself is banned copy | `xr-core/ui/panel/update-tab.ts`, `ui/panel/tests/update-tab.test.mjs`, `tools/vocab_lint.py`, `docs/state/vocab-allowlist.yaml` |
| C-5 (T6) | tabs are declared, additive-only, order-spaced; unknown ids and collisions are typed refusals; a declared tab must CLAIM its implementation; no frame names a tab id | `docs/contracts/panel-tab-registration-v1.{schema.json,md}`, `xr-core/ui/panel/tab-registry.ts`, `ui/panel/tests/tab-registry.test.mjs`, `tools/panel_registry_check.py`, `tools/negatives/p13_c5.sh` 1–3, `docs/adr/0049-panel-tab-registration-v1.md` |
| C-5 (T6) viewer | ONE serializer drives payload and preview; a planted field cannot be hidden | `xr-core/ui/panel/sent-tab.ts`, `ui/panel/tests/sent-tab.test.mjs`, `docs/panel/what-would-be-sent.md` |
| C-3/C-5 docs | the report path's live half is a human act | `docs/panel/breakage-report.md`, `docs/adr/0050-breakage-report-v1.md`, `evidence/P13/human-gates.md` (HG-33) |
| live/PAT rows | R1–R10 above; the push itself is the user's act (HG-20), performed through the token the user supplied for it | `evidence/P13/logs/`, `docs/process/ci-triage.md` |
