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
