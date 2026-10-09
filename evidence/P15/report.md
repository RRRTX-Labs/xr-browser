# P15 report — Permission Firewall v1 (interim)

**State: interim.** This phase is NOT done. Several rows are PARTIAL or BLOCKED (see `evidence.json`), and the sandbox could not execute the Chromium or browser-runtime half of the brief. Hosted results at the final head are read from the Actions API after the push and reported in the run summary, not claimed here. The phase stays interim until every gate is green and every row resolves.

## 0. Heads

- xr-browser: opened at `01baba0d6ce8d923b833e30dbf25463211ec8d91` (P14 close). Code head `3fe8d7e` (the mutation-harness fix). The candidate gate ran at `503589f`, one commit earlier. The final head is the evidence commit that carries this file, which is the head of `main` after the push. This file does not record its own SHA.
- xr-core: `81376ac` at open, then `e2caedc`, `98946b1`, `410f34d`, `aab82f4`, `8b26589`, `f71fcdf`, `4d6672d`, all pushed to `main`. `DEPS.xr_core_rev` = `4d6672d04876b4daa29bd10355de0d3801c8f9b5`.
- Pin moves (DEPS `xr_core_rev`, each pushed the same day under the cross-repo pin process): `81376ac` → `aab82f4` (`bbed863`) → `8b26589` (`f416731`, after the 40-mutant survivors) → `f71fcdf` (`a54056f`) → `4d6672d` (`503589f`, after the audit in §7).

## 1. What shipped (code and contracts)

- **Resolver carrier (xr-core):** `ResolveRequest.permission_overlay`, a strict parse, and a pure consult in `resolve.cc`. The 66 frozen vectors and their expectations are byte-identical and still pass.
- **Permissions core (xr-core `permissions/core/`):** store with canonical round-trip, state-machine ops that emit audit rows, audit rows (permission-audit-event-v1 plus the frozen ActivityRow), the labelled merge, the prompt presentation and T3 ceiling, and the extras envelope.
- **Tests and bench (xr-core):** nine permissions suites with 2,257 + 80 + 47 + 1,204 + 36 + 23 + 15 + 36 + 38 checks, 0 failures. The policy suite's `test_resolve` runs 140 checks at `13a5f7d` (three P15 owning-suite cases were added in `f71fcdf`, and four more in `471a6a1`). Cross-core vectors run through the real resolver. Bench numbers are measured on one host.
- **Contracts and decisions (xr-browser):** ADR-0051 (DRAFT), permission-audit-event-v1 (schema, golden, doc), permission-overlay-v1 (seam doc, 33 vectors), two registry rows, and the P15-T7 section of the attention ledger.
- **Gates (xr-browser):** `permission_contract_check.py` (frozen bytes, golden, vectors), `permission_write_path_check.py` (write-path law), the T7 rule in `attention_check.py`, four negative cases, and the `permissions` lane in `ci-lanes.json`.

## 2. Verification

- Policy frozen suite: `test_vectors: 268 checks, 0 failures` (unchanged from base). `test_resolve: 107 checks, 0 failures`.
- **Planted defects, owning suite (final, xr-core `4d6672d`):** all eleven planted defects are killed by a reported test failure in the suite that owns the mutated file (`evidence/P15/logs/p15-planted-owner-4d6672d.txt`). The unmutated control passes for both suites. The compile-clean M02c stands in for M02, whose only kill was a compile error.
- **Corrections (both are in the transcripts and in research log §10):** at `8b26589` the owning policy suite killed only M04 of the five overlay defects, and the earlier "11 of 11 killed by the owning suite" line was wrong. M07 was killed by a segfault in `test_expiry`, not by an assertion; the test was fixed at `4d6672d`.
- **Sampled CI matrices** (governance parameters, `--sample 90 --seed 20260908`), measured under the fixed harness (`3fe8d7e`) at xr-core `4d6672d`: policy **62/90 killed, deny-guard 11/23: FAIL** (the governance gate is red); permissions 90/90, deny-guard 23/23: PASS. The earlier policy 90/90 at `8b26589` came from a harness that counted build failures as kills and reused stale objects. These are sampled, not the full matrix, which is HG-28.
- Store fuzz row (deterministic): 2,168 single-byte mutants of the fixture. 2,104 refused, and 64 accepted only as canonical bytes. None loads as a partial or silently repaired store. libFuzzer is NOT RUN (no clang).
- Baseline census at `01baba0`: exit 0, 165 PASS, 0 FAIL, 4 SKIP (sandbox tools absent).
- Candidate gate at `503589f` with xr-core `4d6672d`: see §5.

## 3. Task status (from `evidence.json`)

- VERIFIED: T1 (store and overlay), T3 (expiry), T6 (merge), T7 (attention), T9.1 (cross-identity), T9.2 (write-path), T10 (bench, one host), FROZEN (frozen bytes), CLOSE (artifacts).
- PARTIAL: T0 (register row blocked by the validator), T2 (the patch half and the Panel are not built), T4 (contract and generator verified; the Activity-tab rendering is not built), T5 (A4 anchor upgrade not done), T9.3 (libFuzzer not run), MUT (the full matrix is HG-28), GATE-CANDIDATE (see §5).
- BLOCKED-DEFERRED: T8 (settings section), T9.4 (Chromium isolation-matrix cells).
- HUMAN-GATED: T9.5 (S0 dual review). ADR-0051 is DRAFT, and its ratification is a human act.
- BLOCKED-PENDING-PUSH: HOSTED (governance and core-hardening at the final head; read after the push).

## 4. Not done, and why

Each item carries its method path in `docs/state/research-log-P15.md` §6. Scope items are scope, not sandbox limits: the A4 anchors (googlesource is reachable), the settings section, and the matrix cells. The sandbox-limited items are libFuzzer (no clang), the GN build check (no gn), and the rendered browser (no gn or ninja). The register row is blocked by the validator, and that is a human decision (HG-P15-REGISTER).

## 5. Gates

**This round (xr-core `13a5f7d`, xr-browser code head `63fcb0e`).** The full negative suite (`tools/run_negatives.sh`, N=219) passes on re-run (`evidence/P15/logs/negatives-local-63fcb0e.txt`). Its first run failed one case: the panel lane's `npm ci` inside a scratch copy failed once, and the cause was not confirmed (the registry answered HTTP 200 minutes later). The lane run directly passed 14 of 14 (`logs/panel-tests-local-63fcb0e.txt`), and the full re-run passed (`logs/negatives-local-63fcb0e-run1.txt` keeps the first run). Also passing at this head: `evidence_check` (15 bundles, 0 failures), `evidence_check --strict` (13, 0 failures), `evidence_finality` (in-flight P15, 0 failures), `mutation_freshness` (pin `13a5f7d`, 10 cores fresh), `sibling_pin_check`, `vocab_lint`, and `dco_check` over `53f70dd..HEAD`. FROZEN.yaml is byte-identical (sha256 `0b79e439…`), and no `ratified:` or `Contract-Amendment:` trailer appears. The hosted governance and core-hardening runs at the pushed head are read from the Actions API and reported in the run summary.

At the first push of the evidence commit (`66c0c6a`), governance failed at its negative-fixture step, and core-hardening passed. The failure was a harness defect in the mutation gate (section 7), and it was fixed in `3fe8d7e`. Local replay of the governance steps that had been skipped, at `3fe8d7e`: the full negative suite PASS (N=219, default `TMPDIR`), the tool tests, `contracts all`, vectors, the contract pytest, the budget, rebase, assumptions, retire, and fetch checks, and the policy bench all PASS; the policy fuzz reports 0 violations; the permissions matrix PASSes at 90/90; and the policy matrix FAILs at 62/90 (section 2). Core-hardening's four matrices (commands, settings, themes, update) were not re-measured locally, and they run hosted at the next head.

Final candidate: xr-browser `503589f` (code head) with xr-core `4d6672d` (the pinned head). Fresh clones under `/var/tmp/p15/final5`, with `TMPDIR` on the root filesystem. Command: `./tools/run_checks.sh --keep-going`, as CI runs it. Transcript: `evidence/P15/logs/gate-candidate-503589f.txt`.

Result: exit 1, with 164 PASS lines, 3 failing lanes, and 1 SKIP (actionlint, absent as at baseline). All three failing lanes trace to one cause: P15 appears in git history with a `logs/` directory and no bundle. They are `evidence_check` (default), `evidence_check --strict`, and the release gate `check --channel dev` (its finality item reads the same law). The evidence commit supplies the bundle, and the three lanes were re-run locally against it (see below). Every other lane passed: mutation-freshness (10 cores fresh at the pin), all ten C++ suite lanes (policy and permissions included), the P15 contract lane, the write-path law, the attention rule, the fetch allowlist, core-hygiene, secret-scan, DCO, the sibling pin, lane discovery, and pytest (444 passed).

Local re-run with the bundle in the working tree (before the evidence commit): `evidence_check` (15 bundles, 0 failures), `evidence_check --strict` (13 bundles, 0 failures), `evidence_finality` (in-flight phase P15, 0 failures), and `release_gate check --channel dev` (7 lanes green, 0 missing). The presence law is satisfied once the bundle is in history; hosted results at the final head are read after the push.

Earlier candidate, superseded: xr-browser `f416731` with xr-core `8b26589` exited 1, with 159 PASS lines and 3 failing lanes. All three trace to one cause, which is that P15 appears in git history without a bundle: `evidence_check`, `evidence_check --strict`, and the release gate `check --channel dev`, whose finality item reads the same presence law. Transcript: `evidence/P15/logs/gate-candidate-f416731.txt`. The baseline at `01baba0` exited 0.

Visible skips, not hidden ones. The final transcript shows one SKIP, actionlint (absent, as at baseline). The earlier candidate (`f416731`) reported 8 hosted `ci-run` verifications as offline, because unauthenticated GitHub API calls returned HTTP 403 from this sandbox. Those lines do not appear in the final transcript, and this report does not claim the hosted verifications were run locally.

## 6. Decisions that need humans

HG-P15-MUTATION: the operator chose option A this session (harden all three cores; thresholds and seeds unchanged). It is executed locally at `13a5f7d`. A maintainer should accept the seven argued equivalent survivors (policy 2, settings 3, update 2; research log items 26 and 28). The hosted confirmation is reported in the run summary.

See `evidence/P15/human-gates.md`. The main ones: ratify or amend ADR-0051 (HG-P15-ADR51); decide the register path (HG-P15-REGISTER); review the permissions core as S0 (HG-P15-S0-REVIEW); accept the xr-core committer record (HG-P15-COMMITTER); revoke or rotate the token that was pasted into the conversation (HG-P15-TOKEN).

## 7. Issues found in-session

Recorded in `docs/state/research-log-P15.md` §10. The notable ones:

- The first serializer lost the corrupt flag on save, and a test caught it before any push.
- **Owning-suite gap in policy/core.** A planted-defect audit found that the owning policy suite killed only one of the five overlay defects at `8b26589`. Three policy cases were added at `f71fcdf`, and the first M02 kill was a compile error (fixed with the compile-clean M02c).
- **A segfault counted as a kill** (M07). `test_expiry` read rows that might not exist. The guards are in `4d6672d`.
- **Stale kill records.** The first planted-defect run used an 86-check `test_store`, before the store sweep grew the suite to 2,257. All eleven are re-verified at the final suite sizes.
- **Mutation harness false kills (found by a governance run at `66c0c6a`).** The negative fixture "mutation: hollowed test suite" expected a red gate and got a green one. Two harness defects were the cause: a build failure was counted as a kill without restoring the file, and make reused stale objects because rapid rewrites share one timestamp. Both are fixed in `3fe8d7e`. The earlier 90/90 policy result was inflated, and the report now says so.
- **The policy mutation gate was red at `4d6672d` and is green locally at `13a5f7d`.** At `4d6672d` it was 62/90 killed, with 11 of 23 deny-guards. This round killed the non-equivalent survivors in their owning suites. At `13a5f7d` it is 88/90 with 23 of 23 deny-guards, and the two survivors are argued equivalent (research log items 25 and 26).

- **Author rule (this round).** The first commits of this round carried the P15 agent as author. They were rewritten (author only; trees identical) before the first push. The rule is in research log §8 and item 24.
- **Transient negative failure (this round).** The negatives suite failed once on the panel lane's `npm ci` inside a scratch copy. The cause was not confirmed. The lane run directly passed, and the full suite re-run passed 219 of 219. Both transcripts are in `evidence/P15/logs`.
- **Governance backstop (this round).** At `091a4da` the governance job reached its 45-minute backstop during the policy fuzz step and was cancelled. The policy mutation gate had already passed. The backstop is raised to 90 minutes, and no gate changed (research log item 30; HG-P15-BACKSTOP).
