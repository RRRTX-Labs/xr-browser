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

## Upstream-first ledger

Nothing in P13 diverges from upstream in a way that needs a filed issue; if that
changes, the entry lands here with the upstream path named and **no invented URL**
(HG-32: filing upstream is a human act).
