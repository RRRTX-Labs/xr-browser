# Research log — P15 (Permission Firewall v1)

Phase state: **interim.** Not every gate is green, several rows are PARTIAL or BLOCKED, and hosted results at the final head are read from the Actions API after the push, not claimed in-tree. No "done" wording appears anywhere in this phase.

## 0. Identity, scope, and the brief

- Brief: `/home/user/uploads/PHASE-P15.md` (456 lines). The operator wrote "phase-p8". The upload is P15, and the mismatch is recorded in `human-gates.md` (HG-P15-PHASEID).
- Plan: `docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v2.md` (sha256 `02743146…`, matches the pin).
- Repos: `RRRTX-Labs/xr-browser` and `RRRTX-Labs/xr-core`. Both `main` heads matched the brief at clone.
- Authorship: commits are authored as `ahmadrrrtx` (the operator's directive). The sign-off is `XR P15 Agent <p15-agent@users.noreply.github.com>`, and the DCO rule needs the committer email to match it, so the xr-browser commits use the P15 agent as committer. See section 8.

## 1. Pre-flight facts (observed, not assumed)

| Check | Result |
|---|---|
| xr-browser base | `01baba0d6ce8d923b833e30dbf25463211ec8d91` (P14 close), clean |
| xr-core base | `81376ac6da284faf28098acc39314b17231bea95`, clean; stray ref `refs/mainmain` left alone |
| `DEPS.xr_core_rev` before P15 | `81376ac…`. The trailing comment still described P13 (`0dd5748`), which confirms brief item 2a: the comment was stale, and it is replaced |
| `FROZEN.yaml` sha256 | `0b79e439…`, unchanged |
| 66 frozen vectors sha256 | `8d35c4c3…`, unchanged (`count` 66) |
| `prompts/PHASE-P14-CLOSE.md` | not present (`human-gates.md`, HG-P15-P14CLOSE) |
| `ci_parity_check` at base | PARTIAL, exit 0 (six lanes stricter on CI: actionlint, cargo, faketime, minisign, rustc, shellcheck) |
| Hosted runs at base | governance #94 success at `01baba0`; core-hardening #38 success at `6b09082` |
| Branch protection | none on either repo (404), so direct pushes are accepted (HG-34) |
| Sandbox tools | git 2.47.3, python 3.13, g++ 14.2, node 20, make 4.4 present; clang, actionlint, shellcheck, gn, ninja absent |

## 2. Design (decided; recorded in ADR-0051, DRAFT)

- **Carrier R2.** The overlay is a resolver input (`permission_overlay`), consulted last. Absent is inert, which keeps the 66 frozen vectors unchanged. Malformed or `null` is corrupt, which denies everything. A malformed overlay is never partially applied.
- **Envelope.** The frozen four are widenable (they have slots). Extras are deny-only (kAllow refused at parse).
- **Store integrity.** A stored document is accepted only if its bytes equal its canonical form. This rejects duplicate keys, which the shared parser keeps last. Corruption persists across save and reload. The first draft lost the corrupt flag on save, so a corrupt store would have come back as an inert, empty store, which is a widening. A test caught it; the serializer now writes a corrupt marker.
- **Time.** Every operation takes `now_ms`. The 7d scope is active while `expires_at > now` (fail-closed at equality, matching `ExceptionActive`). Evaluation time is monotone (`EffectiveNow`).
- **Fortress deny-list.** Host data (`denied_identities`), never derived in the resolver. It is final.
- **Revocation.** Tombstones, so stale copies cannot revive grants. Revoke-all never widens: it leaves the host-owned deny-list and the deny-only extras untouched.
- **Audit.** One row per real mutation, none for a no-op. `deciding_layer` says which layer decides afterwards. Origins are bare domains, and anything else is refused, never truncated. The frozen ActivityRow is reused (kind kPermission).
- **Attention.** T3 is capped at 3 per hour from a local counter. Overflow and stacked prompts demote one tier to T2, and the demotion is logged.

## 3. Commits (pushed)

| Repo | SHA | Subject |
|---|---|---|
| xr-core | `e2caedc` | policy: P15 overlay carrier in ResolveRequest (ADR-0051 R2) |
| xr-core | `98946b1` | permissions: P15 core library (overlay store, ops, audit, merge) |
| xr-core | `410f34d` | permissions: P15 test suite (9 suites), bench, cross-core vectors |
| xr-core | `aab82f4` | permissions: exhaustive single-byte mutation sweep for the store |
| xr-core | `8b26589` | policy: P15 mutation kills (binding without identity; overlay isolation) |
| xr-core | `f71fcdf` | policy: P15 owning-suite kills for the overlay (7d boundary, deny-list final, corrupt overlay) |
| xr-core | `4d6672d` | permissions: guard the expiry test's row reads (a segfault had hidden the assertion) |
| xr-browser | `615f0c5`, `ff9ccb3`, `bbed863`, `84fc4a0`, `5eb451c`, `f416731` | docs, tools, DEPS pair-bumps (to `aab82f4`, then `8b26589`), fetch-allowlist fix, mutation suite map, mutation records |
| xr-browser | `a54056f` | deps: pin xr-core to `f71fcdf` |
| xr-browser | `27cbddf` | mutation: owning-suite correction for policy/core, and the P15 kill scripts |
| xr-browser | `503589f` | deps: pin xr-core to `4d6672d` (the final code head) |

The final xr-browser head is the evidence commit that follows the code head. A commit cannot record its own SHA, so this file does not state it. The remote `main` head is the final head, and hosted results for that SHA are reported in the run summary.

## 4. Verification

**Policy suite, existing 66 vectors untouched.** `make -C policy/tests test`: all pass, with `test_vectors: 268 checks, 0 failures`, the same count as at base. `test_resolve` runs 107 checks, up from 91 after the three owning-suite cases added at `f71fcdf` (section 10, item 10). Transcript: `evidence/P15/logs/p15-policy-make-test.txt`.

**Permissions suite.** `make -C permissions/tests test`: nine suites, 2,257 + 80 + 47 + 1,204 + 36 + 23 + 15 + 36 + 38 checks, 0 failures. Transcript: `evidence/P15/logs/p15-permissions-make-test.txt`.

**Isolation (T9.1).** A 4 × 4 × 25 grid of identity-A operations against identity-B state (400 cells). B's record and view slice must stay byte-identical. A planted identity-ignoring lookup must be caught by the same grid.

**Mutation.** Three different checks, with three different outcomes. (a) The planted-defect check at xr-core `4d6672d` (`evidence/P15/logs/p15-planted-owner-4d6672d.txt`) runs eleven planted defects (M01–M11) and a compile-clean M02c, each in the suite that owns the mutated file: all twelve are killed by a reported test failure, and the unmutated control passes. This check does not use the mutation gate's harness. (b) The sampled CI matrix (`tools/mutation_test.py --sample 90 --seed 20260908`, the governance command) was **not** measured correctly until `3fe8d7e`. The harness counted build failures as kills and reused stale objects, so the earlier 90/90 (at `8b26589`) was inflated. Under the fixed harness at `4d6672d`, the policy core is **62/90 killed, deny-guard 11/23: FAIL** (`evidence/P15/logs/mutation-policy-fixed-4d6672d.json`, with the 28 survivors listed as OPEN in `docs/state/mutation-scores.json`). (c) The permissions core under the same parameters is **90/90, deny-guard 23/23: PASS** (`evidence/P15/logs/mutation-permissions-fixed-4d6672d.txt`). Both matrices are sampled, and the full matrix is HG-28. Two earlier claims were also wrong and are corrected in section 10: the owning policy suite killed only M04 at `8b26589`, and M07 was a segfault. Transcripts: `evidence/P15/logs/p15-mutation-run.txt` (original text kept, with a correction appended), `evidence/P15/logs/p15-mutation-owner-f71fcdf.txt`, and the planted check above. The superseded 90/90 transcripts stay in the log as `mutation-policy-ci.json` and `mutation-permissions-ci.json`. Scripts: `evidence/P15/mutation/`.

**Store fuzz row (T9.3, deterministic).** Libfuzzer is absent (no clang), so the fuzz row is an exhaustive single-byte mutation sweep. The fixture is 379 bytes. Six substitutions at each position give 2,168 mutants: 2,104 are refused as corrupt, and 64 are accepted only as canonical bytes that re-serialize to themselves. No mutant loads as a partial or silently repaired store.

**Contract lane, write-path law, attention rule, negatives.** `tools/permission_contract_check.py` (PASS; the frozen bytes, the 9 golden rows, and the 33 overlay vectors), its two fixtures (both redden), `tools/permission_write_path_check.py` (PASS over 271 product sources; the planted renderer call reddens), and `tools/attention_check.py` (PASS; the planted modal reddens). The four new negative cases are registered in `run_negatives.sh`, and they pass in isolation (N=4). Transcript: `evidence/P15/logs/p15-contract-and-rules.txt`.

**Baseline census.** On the pristine `01baba0` tree, `run_checks.sh --keep-going` finished with exit 0 and "every lane green": 165 PASS lines, 0 FAIL, and 4 SKIP lines for tools this sandbox lacks. Transcript: `evidence/P15/logs/census-baseline-01baba0.txt` (987 lines).

**Candidate gates.** Four candidates were gated, each on fresh clones under `/var/tmp/p15`. (1) `bbed863` with `aab82f4`: an intermediate gate, superseded. (2) `f416731` with `8b26589`: complete, exit 1 (section 9). (3) `27cbddf` with `f71fcdf`: stopped early, when the expiry-test segfault (section 10, item 11) was found. (4) `503589f` with `4d6672d`: the final candidate (section 9).

## 5. Task status (see `evidence/P15/evidence.json` for the rows)

| Task | Status | Basis |
|---|---|---|
| T0 ADR-0051 | PARTIAL | ADR DRAFT written; register row blocked by `dr_parse` (HG-P15-REGISTER) |
| T1 overlay store | VERIFIED | `test_store` (2,257 checks, incl. the sweep), `test_cross_core` (33 vectors) |
| T2 presentation | PARTIAL | button order and scope-copy key verified as data; ≤4-file patch half and Panel not built |
| T3 expiry | VERIFIED | `test_expiry` (boundary grid, session restart, backward clock, idempotence) |
| T4 audit | PARTIAL | contract, golden, and generator VERIFIED; Activity-tab rendering not built |
| T5 revoke | PARTIAL | revoke-by-site and revoke-all VERIFIED; A4 anchor upgrade not done (section 6) |
| T6 merge | VERIFIED | `test_merge` (24-cell cube; planted mislabel killed) |
| T7 attention | VERIFIED | `attention_check` markers and surface scan, `test_present` ceiling, negative |
| T8 settings | BLOCKED-DEFERRED | not started in this session (section 6) |
| T9.1 cross-identity | VERIFIED | `test_isolation` grid plus `test_cross_core` (the Chromium matrix cells are T9.4) |
| T9.2 write-path | VERIFIED | `permission_write_path_check` + negative |
| T9.3 fuzz | PARTIAL | exhaustive sweep VERIFIED; libFuzzer NOT-RUN (no clang) |
| T9.4 isolation cells | BLOCKED-DEFERRED | the Chromium matrix cells are not wired (section 6) |
| T9.5 S0 review | HUMAN-GATED | HG-P15-S0-REVIEW |
| T10 bench | VERIFIED (one host) | `permissions/bench`, numbers in section 7; reference re-check is HG-28 |

## 6. Not done, with method paths

These rows are NOT-RUN or BLOCKED-DEFERRED. Anything the sandbox *can* do is labelled as scope, never as a sandbox limit.

- **A4 anchor upgrade (T5, scope).** `googlesource` is reachable. Method: fetch `https://chromium.googlesource.com/chromium/src/+archive/d04cdb24d67b081f6cf80200ffc5233f44b61109/<path>.tar.gz` for each anchor in `build/upstream/assumptions.yaml` row A4, confirm each `contains:` string, then run the assumptions gate. Not done in this session.
- **Settings section `xr://settings/permissions` (T8, scope).** Method: a WebUI section in `xr-core/settings/` type-checked by the existing WebUI toolchain (node 20 is present), with the coverage bijection. Not started.
- **Isolation-matrix Chromium cells (T9.4, scope).** Method: add the P15 cells to `tools/isolation_matrix.py`, then run it. Not wired.
- **libFuzzer row (T9.3, sandbox).** No clang in the sandbox. Method: `./scripts/build fuzz` with clang on a build host, targeting the store loader.
- **Panel surface and live propagation to open tabs (scope and sandbox).** Needs the rendered browser (no gn or ninja) and the Panel. Method: the Chromium build on a build host.
- **GN wiring for `xr-core/permissions`.** No `gn` in the sandbox, so the build file cannot be checked. The core is std-only and is built and tested with g++ and make, as `policy/tests` is.
- **Register row (T0).** Blocked by `dr_parse` (HG-P15-REGISTER).
- **Hosted CI at the final head.** Read from the Actions API after the push. It is not recorded in-tree, since a commit cannot record its own hosted result.

- **Policy mutation gate (P15, open).** The sampled policy matrix is 62/90 killed, with 11 of 23 deny-guard mutants killed, under the governance parameters at `4d6672d`. The gate needs at least 90% and zero deny-guard survivors. The 28 survivors are listed as OPEN in `docs/state/mutation-scores.json`. Method: for each survivor, write a test in `xr-core/policy/tests` that fails the mutant, and re-run `tools/mutation_test.py --sample 90 --seed 20260908 --timebox 900 --json`. Decision: HG-P15-MUTATION.

## 7. Bench (T10): MEASURED on one shared host

Methodology mirrors `policy/bench`: `steady_clock`, warmup excluded, 100,000 measured iterations per case, p50/p99/p99.9, `-O2`. The numbers are verdicts for this host, not budgets, and the reference re-check is HG-28. The raw results are in `evidence/P15/logs/bench-results.json`.

| Case (busy store: 50 identities x 4 defaults, 200 live 7d grants) | p50 | p99 | p99.9 | What is timed |
|---|---|---|---|---|
| store load (strict, cold) | 0.97 ms | 1.62 ms | 2.50 ms | `LoadStore` of the canonical text |
| warm projection (read) | 0.31 ms | 0.55 ms | 0.82 ms | `ProjectViewJson` of the store |
| resolve with overlay | 0.20 ms | 0.28 ms | 0.35 ms | parse of the request JSON (with the overlay view), then `Resolve` |
| single overlay mutation | 16 us | 43 us | 89 us | `GrantTemp` on the store (copy plus one audit row) |

Host: one shared sandbox host (2 vCPU, 1.9 GiB RAM), `-O2`, 100,000 measured iterations per case after 2,000 warmup. Raw output: `evidence/P15/logs/bench-results.json` and `evidence/P15/logs/bench-table.txt`. No budget is claimed. These are verdicts for this host only, and the reference-hardware re-check is HG-28.

## 8. Identity and credential handling

- The operator's token was used only through a credential helper that reads `/tmp/xrcred/token` (mode 600) at push time. It was never written into a repo file, a remote URL, `.git/config`, a commit message, or a log. Pushes used `https://github.com/RRRTX-Labs/<repo>.git`, with no credentials in the URL.
- The token is deleted at the end of the session (`/tmp/xrcred/` removed). Revocation is a human act (HG-P15-TOKEN).
- Author: `ahmadrrrtx`. Committer: `XR P15 Agent` (DCO). Three early xr-core commits (`e2caedc`, `98946b1`, `410f34d`) carry committer `ahmadrrrtx`; from `aab82f4` on, the committer is the P15 agent. xr-core has no DCO lane, and rewriting `main` needs a human decision (HG-P15-COMMITTER).

## 9. Candidate gates

**Final candidate: xr-browser `503589f` (code head), with xr-core `4d6672d` (the pinned head).** Fresh clones under `/var/tmp/p15/final5`, with `TMPDIR` on the root filesystem (roomy, outside the repos). Command: `./tools/run_checks.sh --keep-going`, executed directly as CI does. Transcript: `evidence/P15/logs/gate-candidate-503589f.txt`.

**Result: exit 1** (`GATE_RC=1`; the gate reports "3 lane(s) failed"), with 164 PASS lines, 1 SKIP (actionlint, absent in this sandbox as at baseline), and 3 failing lanes. All three trace to one cause, the bundle-presence law: P15 appears in git history with a `logs/` directory and no bundle. The lanes are `evidence_check` (default), `evidence_check --strict`, and the release gate `check --channel dev`, whose finality item reads the same law. The evidence commit supplies the bundle, and the three lanes were then re-run locally against it (section 5 of the report).

Every other lane passed, including: mutation-freshness (pin `4d6672d`, 10 cores fresh); all ten C++ suite lanes, policy and permissions included; the P15 permission contract (frozen 66 vectors, FROZEN.yaml byte-pinned, 9 golden rows, 33 overlay vectors); the write-path law (271 sources); the attention rule; the fetch allowlist (290 files); core-hygiene; secret-scan; the DCO check; the sibling pin; lane discovery (10/10); and pytest (444 passed in 578 s). The transcript is 999 lines: `evidence/P15/logs/gate-candidate-503589f.txt`.

**Local re-run with the bundle in the working tree** (before the evidence commit): `evidence_check` (15 bundles, 0 failures), `evidence_check --strict` (13, 0 failures), `evidence_finality` (in-flight P15, 0 failures), and `release_gate check --channel dev` (7 lanes green, 0 missing).

**Earlier candidate: xr-browser `f416731` with xr-core `8b26589` (superseded).** Exit 1, with 159 PASS lines and 3 failing lanes. All three trace to one cause, which is that P15 appears in git history without a bundle: `evidence_check` (default), `evidence_check --strict`, and the release gate `check --channel dev`, whose finality item reads the same presence law. Every other lane passed, including mutation-freshness (10 cores fresh), the P15 C++ lane, the policy suite, the contract lane, the write-path law, the attention rule, the fetch allowlist, core-hygiene, secret-scan, and pytest (444 passed). Visible skips, not hidden ones: 8 hosted `ci-run` verifications were offline, because the unauthenticated GitHub API returned HTTP 403 to the tooling, and actionlint is absent, as at baseline. Transcript: `evidence/P15/logs/gate-candidate-f416731.txt`. The baseline at `01baba0` exited 0.

**Hosted runs at `66c0c6a`** (the first push of the evidence commit; they caused item 13 of section 10). Governance run `37902632055` (run #95) FAILED at its "Negative fixtures" step (the mutation fixture), and the later steps were skipped. Core-hardening run `37902632129` (run #40) PASSED. Recorded because they are the CI facts that led to the harness fix. The local candidate gate (`run_checks.sh`) does not run the full negative suite or the governance-only steps, so this failure was not caught locally. Section 10, item 15 records the local replay of those steps.

**Stopped candidate: xr-browser `27cbddf` with xr-core `f71fcdf` (not evidence).** Stopped a few minutes into the run, when the expiry-test segfault (section 10, item 11) was found and fixed in xr-core `4d6672d`.

## 10. Issues found and fixed in-session

1. **Corrupt flag lost on save** (found by `test_store`). Fixed: the serializer writes a corrupt marker, which reloads as corrupt.
2. **Duplicate-key records** (found by design review). The shared parser keeps the last key, so the round-trip check was added.
3. **Expectation error** in the cross-core lifecycle (my test's expected camera default). Fixed in the test, not the code.
4. **Attention marker drift**: "demoted" did not match the required "demote one tier" phrase. The checker caught it, and the text was reworded to the law's wording.
5. **Negative fixture name** in the attention negative. Fixed.
6. **Mutation suite selection** (run 1, disclosed in the mutation log). Re-run against the owning suite.
7. **DCO identity**: the DCO check requires the committer to match the sign-off. The xr-browser commits were re-committed with the P15 agent as committer, before any push.
8. **Stale DEPS comment** (brief 2a). Replaced, with a lineage line added.
9. **Register conflict** (`dr_parse` fixes DR-01..DR-30). Not resolved by editing the validator. Left as HG-P15-REGISTER.
10. **Owning-suite gap in policy/core** (found by a planted-defect audit on the `f416731` candidate). At `8b26589` the owning policy suite killed only M04 of the five overlay defects. M01 (7d boundary) and M03 and M05 (corrupt overlay) survived it. The compile-clean M02c survived it too. The original M02 was a compile-error kill (`-Werror`, unused variable `id`), not a test kill. Fixed: three cases in `policy/tests/test_resolve.cc` (xr-core `f71fcdf`, 91 to 107 checks). All five now die in the policy suite by test failures. Before and after: `evidence/P15/logs/p15-mutation-owner-f71fcdf.txt`. The earlier line "11 of 11 killed by the owning suite" was wrong, and the report, the mutation record note, and the evidence row are corrected.
11. **A segfault counted as a kill** (M07, the sweep boundary). `test_expiry` read `rows[0]` after its size check had already failed. That is an out-of-bounds read, so the planted defect surfaced as a segfault rather than a reported assertion. Fixed with size guards (xr-core `4d6672d`). The same defect now fails with `test_expiry: 44 checks, 5 failures` on the mutant, and the unmutated suite still reports 47 checks, 0 failures.
12. **Kill results were recorded against an earlier suite size.** The first planted-defect run used `test_store` at 86 checks, before the store sweep (`aab82f4`) grew it to 2,257. The line saying the kills "still hold" was not verified at the time. The planted-defect check at `4d6672d` re-ran all eleven against the final suites, and all eleven are killed.
13. **Mutation harness false kills** (found by the governance run at `66c0c6a`, negative fixture "mutation: hollowed test suite", which expected the gate to fail). Two defects in `tools/mutation_test.py`. A mutant that failed to build was counted as killed, but its file was not restored, so later mutants in the same TU and the suites that link it also failed to build and were counted as killed. And make compares mtimes, and rapid rewrites share one timestamp on this filesystem (measured: zero nanoseconds apart), so a mutant could reuse the previous object and survive falsely. Fixed in `3fe8d7e` (the file is restored after a build failure, and the mapped binaries and the TU's objects are removed before each build). The corrected numbers are in the Mutation paragraph of section 4.
14. **The policy mutation gate is red at the code head.** At `4d6672d`, under the fixed harness, the policy core is 62/90 killed, with 11 of 23 deny-guard mutants killed. The governance gate requires at least 90% and zero deny-guard survivors. The 28 survivors are real: the mutants were built and the suites passed. Most are parse guards (`resolve_io`, `snapshot`, `store`) and boundary or boolean branches that the frozen vectors and the P15 tests do not exercise. P15 did not kill them, and this is an open decision (HG-P15-MUTATION). Killing them is the next step, and the report does not claim the gate green.
15. **Governance steps behind the failed one were not run.** GitHub Actions stops at the first failed step, so the policy matrix, the policy fuzz, the policy bench, and the upstream treadmill checks did not run at `66c0c6a`. They were replayed locally at `3fe8d7e` (`evidence/P15/logs/govsteps-local-4d6672d-summary.txt`): the tool tests, contracts (`contracts all`, vectors, pytest), the budget, rebase, assumptions, retire, and fetch allowlist checks, and the policy bench all returned 0. The policy fuzz reported 0 violations. The policy matrix is the step that fails, as item 14 records.
16. **Environment sensitivity in one negative.** Under a non-default `TMPDIR`, the panel focus-trap negative reported "rejected, but not for the expected reason": inside the harness the lane tried `npm ci` and reported SKIP, because this sandbox cannot reach the npm registry. With the default `TMPDIR`, the full negative suite passes (N=219, `evidence/P15/logs/negatives-local-3fe8d7e.txt`). This is a replay artifact, not a P15 regression, and CI passed the same case at `66c0c6a`.

17. **Mutation harness: stale objects in nested build trees.** The per-mutant cleanup used a non-recursive glob (`build/*stem*.o`). The update and settings test trees compile into nested directories (`build/update/core/x.o`), so the previous mutant's object could be reused when two writes shared an mtime. On this filesystem rapid writes do share one (zero ns apart). The update survivors `manifest.cc:228` and `:152` (`->` changed to `->=`, a syntax error) survived for that reason. The hosted run at `3fe8d7e` reproduced the fixed numbers, so the hosted figures were not affected on hosts with finer timestamps. Fixed in `ab38dab` (match objects at any depth by name). Same seeds, samples and gates. With the fix, the local matrices at `4d6672d` reproduce the hosted numbers exactly: update 78/90 (deny-guard 6/10) and settings 68/90 (deny-guard 2/5).
18. **A local layout error inflated one matrix.** A clone without the sibling `xr-browser` directory makes the golden-vector path point nowhere. The golden-vector suite then fails for every mutant, and a failing suite counts as a kill. Update read 90/90 that way. CI checks out xr-browser beside `../xr-core`, so CI is not affected. The local runs now mirror that layout. Keep the sibling symlink when re-running locally.
19. **Environment reset during the session (pushes blocked).** After the reset, `/tmp/xrcred/` (the token) was gone, `.git/config` was gone in both repos (so no remote and no commit identity), and `/var/tmp` scratch was gone. Working-tree `build/` directories were absent because the snapshot excludes them; they were restored from git (`git checkout`), with no content change. The local heads equal the pushed heads (xr-browser `53f70dd`, xr-core `4d6672d`). Everything added since is local only: xr-core `31cba7c` (update tests), `9b26ba5` (settings tests), `c9086b1` (policy tests); xr-browser `ab38dab` (harness) and the evidence commit that carries this entry. Pushing needs the token again and the remote config re-added. Not done in this session. HG-P15-TOKEN applies.
20. **Hosted state at `53f70dd`.** Governance run `37912361025` (#98) failed at step 16, the policy mutation gate (62/90). Vocab lint and the other governance steps passed. No core-hardening run exists for this head. Core-hardening must run at the final head before any "done" wording.
21. **Local results at xr-core `c9086b1` (not pinned, not pushed; CI parameters, fixed harness).** Update 88/90 (97.78%), deny-guard 10/10, PASS at gate 95; the two survivors are equivalent (`backoff.cc:26`, `cohort.cc:17`). Settings 87/90 (96.67%), deny-guard 5/5, PASS at gate 90; the three survivors are equivalent (`search.cc:78`, `:150`, `:93`). Policy 74/90 (82.22%), deny-guard 20/23, FAIL at gate 90 with deny-guard survivors 3 (gate requires 0). The 16 policy survivors are listed in `evidence/P15/logs/mutation-policy-c9086b1.txt`. Transcripts: `evidence/P15/logs/mutation-{update,settings,policy}-c9086b1.{json,txt}`.
22. **Equivalence checks.** `cohort.cc:17` (accumulator starts at 1 or 0): the initial bit leaves the 64-bit accumulator after eight 8-bit shifts. The digests and the bucket values match on 2,000,000 random inputs (`evidence/P15/mutation/equivalence/cohort_eq.cc`). `search.cc:93` (`start < size` versus `<=`): the empty trailing token is skipped either way. The tokens match on 2,000,000 random fields (`evidence/P15/mutation/equivalence/search93_eq.cc`). `search.cc:78`, `:150` and `backoff.cc:26` assign an equal value or return 0 on both sides; argued, not sampled. Equivalent survivors still count against the gate. The gates are not weakened. Update and settings have headroom (update allows 4 survivors at 95%, settings allows 9 at 90%), so no user decision on equivalents is needed for them.
23. **Policy: what remains (not done in this session).** To reach 81 of 90 kills and zero deny-guard survivors: (a) deny-guard: `snapshot.cc:149` (non-object entry in a full snapshot), `snapshot.cc:188` (kind check in the decoder), `resolve.cc:150` (grant with an unknown scope must not be live). (b) Non-deny-guard, at least seven: `events.cc:26`, `:27`, `:64`; `resolve.cc:80`, `:117`, `:119`, `:132`; `effective_policy.cc:65`; `store.cc:352`; `snapshot.cc:72` (a test was added and did not kill it, so the comparator reached is probably a different one); `snapshot.cc:258`, `:302`; `cache.cc:69`. Each needs a test in its owning suite. The owning suite for `snapshot.cc:72` needs checking first.
