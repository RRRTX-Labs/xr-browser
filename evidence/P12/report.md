# Phase P12 — cosmetic filtering + scriptlet injection (renderer seam) — final report

**Phase:** P12 · **Content head:** `8db682f` (`8db682fe1c776ff8c6f8d5d357395d1e458ff015`)
· **Bundle state:** `final` · **Recorded final-CI head:** `ea996d9` (see §⑩ — the
re-anchor, and why it exists) · **Written:** 2026-09-29, in P13-P0-C, as part of
the append-only refresh the P13 brief ordered (`PHASE-P13.md` §P0-C item 3/4).

**Report order.** The twelve sections follow the order the P13 brief pins:
① reproduction/first-principles numbers · ② what shipped · ③ laws and gates ·
④ contracts · ⑤ evidence ledger · ⑥ the close-out · ⑦ this refresh ·
⑧ security · ⑨ reproduced clean-clone numbers · ⑩ hosted state (before any
"done" claim) · ⑪ NOT-RUN and HUMAN-GATED, with methods · ⑫ deviations,
corrections, human gates, what P13 inherits.

Every claim cites an artifact in this repo or a `path:line@pin`. Numbers this
sandbox cannot produce say `NOT-RUN (method: …)` in the same sentence.

---

## ① Reproduction / first-principles numbers

P12 asked for one thing: cosmetic filtering and scriptlet injection through the
renderer seam, proven byte-for-byte. Its task list (plan §4, Phase P12):
T0 (date-invariance, evidence, tee-asserts, scratch hygiene), T1 (renderer
cosmetic core, 200+ golden vectors, both flag states), T2 (cosmetic.mojom +
blob cache + fuzz), T3 (generic hide set), T4 (scriptlet degrade corpus),
T5 (one scope object, atomic), T6 (shield-page cosmetic rows + reason codes +
`block-event-v1` extension), T7 (cosmetic perf lane + trend law), T8 (mutation
freshness), CLOSE.

Measured at the phase's content head (all re-derivable today):

| number | value | how it is derived |
|---|---|---|
| commits | 44 | `git rev-list --count 7922648..8db682f` |
| close-out commits | 16 (+1 inclusive = the brief's 17) | `git rev-list --count d14d8c9..8db682f` |
| DCO on every commit | PASS | `tools/dco_check.py --range 7922648..8db682f` |
| cosmetic golden vectors | **249** | `docs/contracts/vectors/cosmetic-v1.json` (`cases`) |
| patch manifest | 4 patches / 21 files / **0 drifted** | `docs/contracts/patch-manifest.json` via `patch_manifest_check` |
| blink_seams budget | `5 | 1 | 25` | `docs/state/budget.md:8` |
| perf rows | 22, of which 4 `cosmetic-*` generator-made | `build/qa/perf/perf-budgets.json` |
| cosmetic mutation | **418/418 killed** | `docs/state/mutation-scores.json` (T8, `1347f72`) |
| shield parity (fake backend) | 1533 cases, 100.0% agreement, FP 0.0%, FN 0 | `gen_parity_corpus --check` (P12-CLOSE log) |
| scriptlet degrade corpus | 312 cases, `surface=model` | `10c707d` |
| `evidence/P12` rows | 24 (+ corrections appended in §⑦) | `evidence/P12/evidence.json` |

**The one number P12 could not produce.** `governance` never went green at
`8db682f`: the runner's annotation reads, verbatim,
`Process completed with exit code 126.` (`.github:21`, check-run
`108170646843`, run `36165052542`-family — the run id is `36165052572`; the
annotation endpoint is public). Cause: `tools/run_checks.sh` and
`tools/run_negatives.sh` were tracked **`100644`** while `governance.yml`
invoked both *directly*; the mode was flipped in `5e3d1d4` ("P12-T0-d: moving
NEG_TMP into the repo broke four gates…") and `bash tools/run_checks.sh` cannot
see a mode bit. P0-A of P13 fixed the bit and made the class impossible; P0-B
made the next red diagnosable from public endpoints. This report records the
finding rather than inheriting a green it never had.

## ② What shipped

| task | commit(s) | artifact that proves it |
|---|---|---|
| T0-a date-invariance + hermetic gate | `9ad7208`, `6158afe` | `tools/date_invariance_check.py`, `tools/wall_clock_lint.py`, `tools/wall_clock_allowlist.yaml` |
| T0-b J-1 evidence bundle + presence law | `3d7f55d`, `ac01ebb` | `tools/evidence_presence_check.py`, `evidence/P11/` |
| T0-c tee-assert law | `3c935c0` | `build/tee_assert_lint.py` |
| T0-d scratch preflight + tree hygiene | `05ee808`, `52688dc`, `4dad5f6`, `5e3d1d4` | `tools/scratch.sh`, `tools/negatives/p12_t0d.sh` |
| T1 renderer cosmetic core + vectors + seam round-trip | `169c823`, `0f6de19`, `ca573a7`, `3d734cd`, `d15f0f8`, `4f11af3`, `295e541`, `2103480`, `344def9`, `3a7aa84`, `ff3118a`, `d4e450a` | `xr-core/renderer/cosmetic/**`, `docs/contracts/vectors/cosmetic-v1.json` (249 cases), `build/webui/shield_seam_roundtrip.py` |
| T2 cosmetic.mojom + blob cache + fuzz | `a40251d`, `0fdcf8c` | `xr-core/mojom/cosmetic.mojom`, `docs/contracts/blob-cache-v1.md`, `docs/renderer/blob-cache.md`, `fuzz_fleet` target |
| T3 generic hide set (33 rules, never exception-able) | `e57311b`, `0c35cbb` | `docs/shield/generic-hide-set.json`, `tools/cosmetic_generic_set_check.py` + `build/qa/perf/generic-set-budgets.json` |
| T4 scriptlet degrade corpus (312 cases) | `10c707d` | `xr-core/renderer/cosmetic/scriptlets/**`, registry gate |
| T5 one scope object, atomic | `2a1da16` | `docs/contracts/vectors/cosmetic-v1.json` scope-key cases, `tools/negatives/p12_t5.sh` |
| T6 block-event-v1 extension + reason codes + shield rows | `4198241`, `c37cb8a`, `bd8e5bd` | `docs/shield/reason-codes.json`, `xr-core/shield/host_protocol.md`, `tools/shield_state_check.py`, `tools/attention_check.py` |
| T7 cosmetic perf lane, never-MET trend law | `0db250c` | `tools/cosmetic_bench.py`, `build/qa/perf/perf-budgets.json` (4 `cosmetic-*` rows), `tools/negatives/p12_t7.sh` |
| T8 mutation freshness on the touched core | `1347f72` | `docs/state/mutation-scores.json` (418/418) |
| CLOSE | `3b511b8`, `90417da`, `49fcf47`, `6b1b428`, `9643d2a`, `8db682f` | the six commits' own subjects + `tools/scheduled_lane_check.py`, `tools/mutation_freshness.py` |
| T0-U1..U4 (close-out follow-ups) | `d14d8c9`, `c1d4aaa`, `f47b54e`, `1816d20` | `tools/dev_deps_closure_check.py`, ADR-0047, `tools/evidence_ci.py` head law, `build/farm/budget_meter.py`, registry rows |

## ③ Laws and gates added (or hardened) by P12

* **Date invariance** — no gate verdict may read the wall calendar;
  `tools/wall_clock_lint.py` scans the gate closure, `date_invariance_check`
  probes two `--as-of` values. Measured today, unchanged:
  `PASS: date_invariance_check (3 invariant lane(s) identical across 2 dates
  [2026-01-01 .. 2038-01-18]; 1 freshness lane(s) still bite across their
  expiry boundary; ambient-clock probe UNAVAILABLE (faketime absent))`.
* **Evidence presence** — a phase that appears in git history must carry
  `evidence.json` + `human-gates.md`; P11's `logs/`-only shape is a FAIL
  (`tools/evidence_presence_check.py`, `3d7f55d`). Extended in P13-P0-C (§⑦).
* **Tee-assert** — a verdict-bearing `| tee` needs `pipefail` or a negative
  assertion (`build/tee_assert_lint.py`; PASS: 5 workflows, 11 pipes).
* **Scratch preflight** — fixtures tar whole trees; scratch must be preflighted
  and never inside the tree under test (`tools/scratch.sh`, `05ee808`).
* **Final-CI head law (T0-U2)** — a phase's final-CI claim must point at the
  phase's own head (`tools/evidence_ci.py::head_coverage_findings`,
  `c1d4aaa`), which is what detects the re-anchor in §⑩ rather than hiding it.
* **Dev-dep closure + optional-tool SKIP law (T0-U1)** — `libfaketime` left
  `tools/requirements-dev.txt`; `faketime` became an optional helper with a
  SKIP row, and a hard gate may never require an ambient tool
  (`tools/dev_deps_closure_check.py`, `docs/dependencies/helper-tools.yaml`,
  ADR-0047).
* **Budget unit = upstream files (T0-U3)** — caps measured on diff headers,
  not patch entries (`build/farm/budget_meter.py`, `f47b54e`).

## ④ Contracts

* `cosmetic-blob-v1` — LIVING, registered post-freeze
  (`docs/contracts/registry-post-freeze.md:247`); 249 vectors, both flag
  states byte-identical across backends.
* `cosmetic-host-protocol v1` — LIVING (ratification PENDING, HG-26);
  the 8-method stdio table in `xr-core/renderer/cosmetic/host_protocol.md`,
  parity-locked against `xr-core/fakes/cosmetic.py`.
* `cosmetic.mojom` — ninth interface, as an **RFC proposal** (an ADR, approval
  is a human act): `xr-core/mojom/cosmetic.mojom`, coverage law
  `tools/tests/test_mojom_coverage.py`.
* `block-event-v1` extension — `page_modifying` hit counts
  (`xr-core/mojom/cosmetic.mojom:41`, `xr-core/renderer/cosmetic/host/cosmetic_host.cc:291`),
  both backends byte-identical, and the two closed page-modifying `why_code`s
  in `docs/shield/reason-codes.json`.
* **`docs/contracts/FROZEN.yaml` untouched**: sha256
  `0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1`;
  `docs/contracts/INDEX.md` sha256 `7225489169944e381ec2ea15…` — both
  byte-identical to their `8db682f` bytes (verified at `8db682f` and today).

## ⑤ Evidence ledger

24 rows in `evidence/P12/evidence.json` cover the brief's DoD items one by one
(`P12-DOD-T0-a-1` … `P12-CLOSE-DOD-15`), each citing a transcript under
`evidence/P12/logs/` or a repo artifact. The bundle's `toolchain_capture` block
records what this sandbox has and lacks (`g++ 14.2, make, python 3.13, node
20.20 …; ABSENT gn/ninja/clang/cargo/rustc/go/minisign/shellcheck/actionlint`)
and what the hosted runner proved instead (cargo/rustc, cited by run ids).

## ⑥ The close-out

`d14d8c9`…`8db682f` is where P12 became honest: the dev-dep ceremony
(T0-U1), the final-CI head law (T0-U2), the budget-unit correction (T0-U3),
the per-DoD bundle rows + registry rows (T0-U4), the Rust-conformance count fix
(`90417da`), the treadmill canary exit contract (`49fcf47`), the perf_gate
mutation re-anchor (`6b1b428`), the generic-set `--check` fix (`9643d2a`) and
the strict-date-probe ordering fix (`8db682f`).

**The defect the close-out walked past.** `5e3d1d4` rewrote
`tools/run_checks.sh` and `tools/run_negatives.sh` in place and dropped their
exec bits. Three later commits (`6b1b428`, `9643d2a`, `8db682f`) chased real but
different causes ("fix the CI") and could not turn the lane green, because the
gate never *ran*: the runner could not execute a `100644` file. P13-P0-A
restored the bits and built the gate that makes the class impossible
(`tools/entrypoint_mode_check.py`, `tools/inplace.py`,
`tools/negatives/p13_p0a.sh`), and P13-P0-B made the next red self-describing
(`::error::<lane>: <gate> - <reason>`, `tools/gate_annotation.py`).

## ⑦ This refresh (append-only, P13-P0-C)

What changed in the bundle, and how. The refresh landed in two commits, and the
split is a property of the rule rather than a matter of convenience: **a bundle
cannot cite the run of the commit that contains it**, so the content that is
true without an anchor head landed first (`f969499`, the refreshed head), and
the head/claim fields landed in the commit that follows, on top of it.

1. `f969499` — six **append-only correction rows** for the CLOSE items that
   were `BLOCKED-PENDING-*` or PARTIAL for reasons this tree can now show
   (T5/T6/T7 landed; `docs/contracts/registry-post-freeze.md:236-249` carries
   the cosmetic contracts; the docs exist). No original row text or status was
   edited: each correction quotes the original status and supersedes it through
   the P11-T0-d rule-(d) `corrects` field, which is what
   `tools/evidence_ci.py` reads. The refresh's own transcript is
   `logs/p0c-refresh.txt`.
2. The commit that follows — four more corrections, all of them statements that
   only become true with a declared head or with the phase's own reading of the
   hosted state (DOD-11, -12, -14, -15), plus `phase_head` and `ci_claimed`.
   `ci_claimed` is `["governance"]`: core-hardening's path filter (DEPS,
   `tools/mutation_*.py`, `tools/*fuzz*.py`, its own workflow file) matched
   nothing in this window, so the workflow did not run and there is nothing to
   claim — the bundle claims exactly the workflow that ran.
3. **`state` is deliberately NOT asserted as `final`.** The phase's hosted
   certification cannot be produced in this window (see ⑩), and a phase that
   cannot be certified is not marked final by fiat. The law reads an absent
   state as final and reddens on exactly the missing row, which is the outcome
   this report stands behind: one red that names its cause beats a green claim
   that means nothing. `P12-CLOSE-DOD-12-C1` carries the chain link by link.
4. `report.md` (this file) — the 12-section report P12's DOD-15 demanded and
   P12 never wrote. It is written 2026-09-29 in P13-P0-C, not at P12's close;
   that deviation is stated here and in ⑫ rather than papered over.

## ⑧ Security and privacy posture

* No new crypto: `no_new_crypto_check` green at the phase head
  (`tools/no_new_crypto_check.py`).
* No new dependencies: `libfaketime` *left* the pins (`T0-U1`); toolchain pins
  unchanged.
* Zero product egress: the cosmetic path is in-renderer; the seam round-trip is
  a local stdio contract (`build/webui/shield_seam_roundtrip.py`).
* No vault material in any artifact: `tools/secret_scan.py --all` = PASS
  (3198 files, both repos).
* Cosmetic never gains an attention surface: `tools/attention_check.py` carries
  the P12-T6 rule (`:41`–`:45`) plus the planted-modal negative
  (`tools/negatives/p12_t6.sh`).

## ⑨ Reproduced clean-clone numbers

Re-measured in P13-P0-C at the refreshed, buildable head (§⑩ explains why not at
`8db682f`):

| measurement | result |
|---|---|
| `./scripts/build test` | **858 passed, 2 skipped, 0 failed** (P12's recorded 787/2 is the floor; +71 from P13-P0-A/B/C tests) |
| `tools/run_negatives.sh` | grown: 125 (P12's record) → **156** cases, exit 0 (log: `evidence/P13/logs/negatives-full-c4.txt`; the P13-P0-C area alone is N=8, `logs/negatives-p0c.txt`) |
| `date_invariance_check` | PASS, 3 invariant lanes identical, 1 freshness lane still bites |
| `wall_clock_lint` | PASS (133 files scanned, 10 allowlisted data timestamps, 0 dead rows) |
| `FROZEN.yaml` / `INDEX.md` | byte-identical to `8db682f` (sha256s in §④) |
| `dco_check --range 7922648..8db682f` | PASS |
| `check-pin-alive` | PASS (`DEPS xr_core_rev` = `f7c683d…` = xr-core origin HEAD) |
| trees | clean at every commit (`git status --porcelain` empty) |

## ⑩ Hosted state (before any "done" claim)

Every line below is read from the public API (check-runs, annotations, jobs) and
is reproducible with `tools/ci_triage.py --sha <head>`; the transcripts are in
`evidence/P13/logs/`.

| head | workflow | run | conclusion |
|---|---|---|---|
| `8db682f` (P12's own last commit) | governance | `36165052572` job `108170646843` | **failure** — step 9, annotation `Process completed with exit code 126.`, 10 steps skipped: the gate never executed (the entry-point mode defect P13-P0-A fixed) |
| `9979cd0` (P13-P0-A) | governance | `36602949426` | failure — a banned vocabulary word in `docs/process/ci-invocation.md` (reproduced locally, fixed next commit) |
| `ea996d9` (P13-P0-B) | governance | `36603483362` | failure — `tools/fetch_allowlist_check.py`: the new triage tool called `urllib` outside the chokepoint (reproduced, fixed in `a0ac40b`) |
| `ea996d9` | core-hardening | `36603483248` | **success** (the only green P13-era lane; it does not carry the governance gate) |
| `a0ac40b` | governance | `36606435399` | failure — this bundle cited `tools/evidence_finality.py` before that file was committed |
| `f969499` (refreshed head) | governance | `36610931823` job `109551846052` | **failure, EXTERNAL** — step 9, annotation `.github:134`: `governance: S-01 - BLOCKED-NET cannot fetch content/public/browser/content_browser_client.h at d04cdb24… : fetch failed … after 3 attemp…` |

**The honest conclusion.** No head that contains P12's work carries a green
governance run, and the reason for the current one is **upstream**: the runner
cannot fetch `chromium.googlesource.com` at the pinned revision, and the same
host answers this sandbox with HTTP 503 in 0.08 s (`FetchError` after three
attempts). The last green governance run in the repository's history is P11's
`7922648a` (`34905296564`); the lane was green then, so this is an outage, not a
standing property of the gate. The gate fails closed on no network by design,
and softening that to buy green is exactly what the phase brief forbids.

**Therefore:** P12's final-CI row is **absent**, `state` is **not** asserted,
and this phase closes with that one gap recorded — the brief's failure
condition 5, taken deliberately. The resumption procedure is mechanical:

1. when the outage clears, push any commit (or re-run the phase's own head
   check) and read the governance conclusion at that head with
   `tools/ci_triage.py --sha <head>`;
2. on green, append one `source: ci-run` row (`ci_run`/`ci_job` of that head's
   governance job, `head_sha` = that head) and set `phase_head` to it;
3. re-run `tools/run_checks.sh --phase-final`; the single red in this report
   disappears and P12 is final **by its own evidence**, with this report's ⑩
   left in place as the record of the gap.

The re-anchor is also why `ci_claimed` says what it says: the row lands for the
workflow that actually ran at that head, and for no other.

## ⑪ NOT-RUN / HUMAN-GATED, with methods

* **Rendered cosmetic results** (blank-page sweep, document-start p95 on a real
  build, 50 hard apps): `NOT-RUN (method: docs/qa/browser-harness.md)` — gn/
  ninja and a browser are absent here; any such number would be fabricated
  (HG-31).
* **Full mutation matrices** (24 h, every core, ≥ 95 %): **HUMAN-GATED**
  (HG-28); the touched cosmetic core's *fresh* matrix is 418/418
  (`docs/state/mutation-scores.json`).
* **Perf MET assertions on a real rig**: the trend rig can only ever be
  NEUTRAL here; four `cosmetic-*` rows are generator-owned and `--check`-clean.
* **`faketime` ambient-clock half**: `UNVERIFIED` on this host (tool absent, by
  P12-T0-U1's design); the `--as-of` half is the verdict and says so.
* **sast's next scheduled fire**: reported by `tools/scheduled_lane_check.py`
  as STALE/red-with-cause, never as a fabricated green.

## ⑫ Deviations, corrections, human gates, what P13 inherits

**Deviations recorded.** (1) The report is written in P13-P0-C rather than at
P12's close — stated wherever it is cited. (2) The final-CI head is anchored at
`ea996d9` (§⑩) because `8db682f` cannot host a green governance run:
`100644` + direct exec = 126, and a mode bit cannot be retracted from history.
(3) The P12-CLOSE bundle does not exist as a directory; its rows live here, as
the brief's P0-C item 4 directs.

**Corrections.** The eight `BLOCKED-PENDING-*` statuses in this bundle were true
when written and are false now; each is corrected by an appended row that quotes
it, never by an in-place edit. The two `PARTIAL` rows stay PARTIAL: mutation
matrices remain HUMAN-GATED (HG-28).

**Human gates that bound this phase** (do not act on them): HG-26 (14 `PENDING`
rows in `docs/contracts/FROZEN.yaml`; cosmetic contracts are LIVING +
registered post-freeze for exactly this reason), HG-34 (branch protection —
both repos still accept direct pushes to `main`, which is why "red at HEAD" was
possible at all), HG-31/HG-9/HG-27 (browser rig, real mojom bindings), HG-28
(24 h matrices / perf MET), HG-20 (the PAT supplied for P13 remains unrevoked —
user action; no agent touches or asks for credentials).

**What P13 inherits.** A green-capable gate with a 126-class hole closed and a
diagnosis path that speaks in annotations; evidence bundles that must declare
their state; a shielded surface whose scope object is the single source for
cosmetic+network flips — which is precisely the object P13's Site tab must
consult rather than duplicate; the `why_code` vocabulary + `reason-codes.json`
that P13's "why" drill consumes; and three scheduled lanes whose reds P0-D must
root-cause without widening a canary.
