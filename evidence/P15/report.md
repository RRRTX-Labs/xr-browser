# P15 report: Permission Firewall v1, closing rows (P15-CLOSE), interim

**State: interim.** P15 is not stamped `final`. Condition 4 of the P15-CLOSE Definition of Done (hosted governance and core-hardening green at the final head, after a human push) cannot hold yet: every P15-CLOSE commit is local, because P15-CLOSE rule 1 forbids the agent any token. ⑩ gives the hosted state, ⑪ goes through the DoD row by row, and ⑫ lists what a human must do.

**Heads.**
- Opening heads, re-read with `git ls-remote`: xr-browser `cabb36ff75512e3179da35190278846b929d4130`, xr-core `13a5f7d980101ac8d61b707d7728674f268f8990` (the brief's expected heads).
- P14-CLOSE ran first in this session, by operator choice, and landed on top: xr-core `e18b82f` and xr-browser `267de39` are pushed; the P14 closing commit `53a628c` is local.
- P15-CLOSE code head: xr-browser `ae10987` on top of `53a628c`, with xr-core `30adb622ae823efba169f7613f871f7433d69695`. `DEPS.xr_core_rev` equals the xr-core head (compared in Python as 40-hex strings).
- The evidence commit that carries this file is the xr-browser head. This file does not record its own SHA.

**Identity.** Author `ahmadrrrtx`. Committer and `Signed-off-by` are `XR P15 Agent <p15-agent@users.noreply.github.com>` on every P15-CLOSE commit in both repos.

**The one-line version.** At `cabb36f` the P15 bundle overstated T3 (no kill -9 test), left out RFC-0002, and did not mention the negatives interference hazard. Seven rows had nothing in the tree behind them. Each of those now has code, a law and a planted negative. Two mutation records that C5 made stale were re-scored on the fixed harness, and one of them (settings, 286/286) turned out to be false kills. What stays open is what this sandbox cannot do (browser runtime, pixels, clang, gn, a 24 h farm), what only humans may do (S0 review, ratification, register path, token rotation), and the push.

---

## ① The reproduction, verbatim

The brief's section-0 claims, re-read at the opening heads with `git show` / `git ls-tree` (no worktree). Full transcript: `evidence/P15/logs/c12-reproduction-cabb36f.txt`.

```
docs/rfcs/ at cabb36f:                0000-template.md, RFC-0001.md   (files mentioning RFC-0002: 0)
xr-core permissions/ at 13a5f7d:      README.md bench core tests       (no BUILD.gn, host/, host_protocol.md)
files under permissions/ naming kill: 0
fakes/ files naming permission:       0
fleet ids:                            policy-core commands-core settings-core themes-core cosmetic-core identity-core
A4 contains:                          ['class PermissionContextBase']
settings sections:                    ['network', 'privacy', 'identity']
permissions in test/isolation/matrix.yaml: 0     permissions in patches/manifest.yaml: 0
keyboard_tasks_check.py:23            REQUIRED_COUNT = 12
run_negatives.sh:                     72 lines, lock 0, mktemp 0
P15-T3 row:                           VERIFIED | test_expiry: 47 checks ...
FROZEN.yaml sha256:                   0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1
```

Every claim in the brief held. Two facts it did not state turned up while working (⑨): the settings mutation record 286/286 was a false-kill result, and the mutation harness crashed outright on a mutant that hangs a suite.

---

## ② Preflight (P0-1 … P0-5)

- **P0-1, tree.** The tree was restored after each sandbox reset by explicit path (`git checkout -- build scripts`, exec bits from `git ls-files -s`, `origin` re-added by plain URL with no credentials). Deletions were never committed.
- **P0-2, heads.** Recorded above and in `evidence.json` `repos`.
- **P0-3, P14-CLOSE status (HG-P15-P14CLOSE).** The operator answered: run P14-CLOSE first, in this session. Its record is `evidence/P14/` (state final, `phase_head` `267de39`). Hosted runs at `267de39`: governance `38071604754` and core-hardening `38071604748`, both success. P15-CLOSE writes nothing into P14's rows, and the identity-ledger amendment stays P14's.
- **P0-4, baseline.** The P15-CLOSE baseline is the P14-CLOSE tree. At `53a628c` the negatives battery gave `ALL NEGATIVE CASES REJECTED AS EXPECTED (N=232)`, EXIT=0; P14-CLOSE had grown it from 219. A separate `./scripts/build test` baseline was not recorded before the first P15-CLOSE change: P14's last recorded figure is build test 993 with 0 failed (`evidence/P14/report.md` ⑪). The parity verdict is quoted in ⑨.
- **P0-5, tools.** `clang` is absent. At the final gate, `actionlint`, `shellcheck`, `faketime`, `minisign`, `cargo` and `rustc` were also not installed, and their lanes are SKIP, which is not a PASS. Earlier in the session, P14-CLOSE had installed shellcheck, faketime and minisign as OS packages, and an intermediate gate (`rc-p15-b`) ran with them. After the last sandbox reset they were not reinstalled, per P0-5.

---

## ③ C1 … C11: files, commits, status

| item | xr-core | xr-browser | status |
|---|---|---|---|
| C1 RFC-0002 (DRAFT) | none | `baff074` | VERIFIED; the decision is HG-P15-RFC2 |
| C2 host layer, protocol, fake, kill -9 | `c1c5f09`, `94cc74f` | `f5562b4` | VERIFIED (GN link NOT-RUN: no gn) |
| C3 fuzz row 7 | `0c1e9e6` | `cb1c045` | VERIFIED (libFuzzer NOT-RUN: no clang, HG-28) |
| C4 A4 anchors + drift negative | none | `bfacc4d` | VERIFIED (live-tab revoke NOT-RUN, method path) |
| C5 settings section `permissions` | `35c998a`, `c9c51d8` | `a87d512` | VERIFIED (pixels and screen reader NOT-RUN) |
| C6 keyboard tasks, option (a) | `b480c45` | `dcbd776` | VERIFIED |
| C7 patch 0400, one file | `3871399` | `3ad1757` | VERIFIED (Chromium build NOT-RUN: no gn) |
| C8 isolation cells | `1d5f018` | `0d9ce73` | VERIFIED (2 browser cells NOT-RUN, method paths) |
| C9 audit count law, Activity option (b) | none | `31eba8f` | VERIFIED law; rendering NOT-RUN, surface decision HG-P15-ACTIVITY-SURFACE |
| C10 negatives isolation + lock | none | `3a3447a` | VERIFIED |
| C11 mutation freshness | `a94aff9`, `30adb62` | `ae10987` | VERIFIED; the equivalence arguments are HG-P15-MUTATION |
| C12 human gates + bundle | none | the evidence commit | interim (⑩) |

Each item's decision, measurement and "Does NOT prove" list is in `docs/state/research-log-P15.md` §11 and item 31. In short:

- **C1.** `docs/rfcs/RFC-0002.md`, from the template, has `status: DRAFT`. It proposes widening `PermissionPolicy` to carry `clipboard-read-write`, `sensors`, `midi` and `pics`, which ADR-0051 envelope (ii) keeps deny-only today. It names the dependents P35 and P21 (plan lines 803 and 815) and gives the alternatives. It contains no approval literal (`amend_guard.py:82` would match one anywhere).
- **C2.** `permissions/host/permissions_host.cc` owns the clock (`--as-of MS`, otherwise one read per call) and passes `now_ms` into the core. `permission_write_path_check.py` gains a clock-free row for `permissions/core/**`. `host_protocol.md` documents every method. `fakes/permissions.py` and `fixtures/permission-v1.json` give 80 cases, byte-identical to the host. `test_kill9.cc` is a real fork-and-SIGKILL test (④). `BUILD.gn` matches the sibling cores.
- **C3.** Row `permissions-overlay` in `build/fuzz/fleet.yaml`, plus `build/fuzz/libfuzzer/permissions_overlay_fuzz.cc`. 16 seeds are derived by `tools/seed_corpus.py`, whose `--check` covers the row. The runner and the SKIP text lose their count literals, and the core-hardening matrix follows the fleet. The 600 s run is clean (`logs/t-fuzz-permissions-600s.txt`).
- **C4.** A4 pins five anchors read live at `d04cdb24` (`ResetPermission`, `OnContentSettingChanged`, `NotifyObservers`, `OnPermissionChanged`, `class PermissionContextBase`). `assumptions.py run --use-deps --as-of 2026-10-11T00:00:00+00:00` gives 6 PASS / 1 SKIP / 0 FAIL. A planted rename reddens `assumption_drift_check.py --row A4`. `assumptions.py` now takes `--as-of`, so its timestamps no longer come from the wall clock.
- **C5.** Section `permissions` (order 10) and the command `settings.permissions` (the roster is now 28). The coverage-allowlist row, the help anchor in both directions, and `gen_registry --check` are clean. Deviation: the search terms are schema `aliases`, because `settings-search.ts` holds no terms.
- **C6.** Option (a): `docs/qa/keyboard-tasks-permissions.yaml` has its own law, which reads the fake's CAPS. Geolocation, camera and microphone get `[once, session, 7d, deny]`; notifications get `[deny, once, session, 7d]` (HG-P15-UX). The 12-task law is untouched.
- **C7.** Patch 0400 is one file, `chrome/browser/ui/views/permissions/permission_prompt_bubble_base_view.cc`: 1,383 B, sha256 `439110f8d1d6b58e…`, an order-only swap behind `ENABLE_XR_PERMISSIONS`. `permission_patch_roundtrip.py --check` regenerates it at the pin and byte-compares it.
- **C8.** Four fake-mode mechanisms run against the fake for every declared pair: 20/20 pass, and a planted identity-blind overlay fails 8/20. The JSON, the Markdown and the card were regenerated by the tool.
- **C9.** `permission_audit_count_check.py` replays 600 seeded operations and requires one audit row per store change. A planted silent grant reddens it. No Activity tab exists in either repo, so none was invented.
- **C10.** Per-case `mktemp -d` scratch is created through `tools/negatives/isolation.sh`. `run_negatives.sh` takes a lock (flock, with a mkdir and pid fallback). The red-then-green reproduction is in ④ and ⑦.
- **C11.** See ⑦ and ⑨.

---

## ④ Security evidence

- **Kill -9 (T3).** `permissions/tests/test_kill9.cc` forks the built `permissions_host` and sends SIGKILL at seeded delays during a sweep; at least one kill must land mid-run. The store must be byte-equal to the pre-sweep or the post-sweep generation, with no grant live past `expires_at` after the next start. A rolled-back clock cannot revive a grant. The `kill_matrix` permissions row runs 6 cells (SIGKILL and SIGTERM at mid-dispatch and mid-write, corrupt-load, disposable-zero-bytes) and all 6 pass; the whole matrix executes 28 cells and prints PASS.
- **Clock-free core.** A planted `time(nullptr)` in a scratch `permissions/core/sweep.cc` reddens the write-path law (`p15c_core_clock`).
- **Host and fake parity.** 80 cases are byte-identical. A planted divergence reddens (`p15c_parity_divergence`).
- **Cross-identity.** 20/20 isolation cells pass. A planted identity-blind overlay fails 8 of them (`tools/negatives/p15c_c8.sh`).
- **No silent grant.** 600 operations (seed 20261010): grant 228, revoke 155, expiry 70, default 95, deny 108, with 0 violations. The plant reddens (`p15c_silent_grant`).
- **Store fuzzing.** The fleet row ran 600 s clean (seed 20260910). libFuzzer is NOT-RUN (no clang; HG-28).
- **S0 review** stays HUMAN-GATED (HG-P15-S0-REVIEW). The agent does not stand in for a reviewer.

---

## ⑤ Contracts

- `docs/contracts/FROZEN.yaml` is byte-identical, sha256 `0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1` (re-proved by `permission_contract_check.py`). The 66 frozen resolver vectors are unchanged (sha `8d35c4c3…`).
- No edit to `mojom/`. No `ratified:` key, no `Contract-Amendment:` trailer, no approval literal. ADR-0051 and RFC-0002 are DRAFT.
- New living documents: `xr-core/permissions/host_protocol.md`, the `permission-v1` fake fixture, and the dated ADR-0051 addendum (C5, C6, C7, C9 decisions).
- No new dependency, crypto or egress. The C4 reads go through the existing `build/upstream/fetch.py` allowlist.

---

## ⑥ Perf & budgets

- Patch budget, regenerated by `build/farm/budget_meter.py`: ui 10/35, total 22/150 files. 5 patches and 22 files (`patch_manifest_check.py`).
- Touched-file law: every touched `build/`, `tools/` and `release/` file is at most 380 lines. `tools/run_checks.sh` is 377 and `tools/mutation_test.py` is 380. `run_negatives.sh` is 78 and `lib.sh` is 377; the lock lives in the new `isolation.sh`.
- Browser numbers (prompt latency, live revoke) are NOT-RUN here; no browser runtime exists in this sandbox.

---

## ⑦ Gates & regressions

- **Negatives:** `ALL NEGATIVE CASES REJECTED AS EXPECTED (N=247)`, EXIT=0, with 3 visible SKIPs (`policy_host` and `commands_host` binaries not built for two cases; `faketime` absent) (`logs/negatives-p15close-ae10987.txt`), up from N=232 at `53a628c`. New P15-CLOSE cases: `p15c_core_clock`, `p15c_parity_divergence`, `p15c_a4_drift`, `p15c_kp_misordered`, `p15c_kp_missing_first`, `p15c_kp_missing_task`, `p15c_patch_drift`, three in `p15c_c8.sh`, `p15c_silent_grant`, `p15c_interference_red`, `p15c_lock_flock`, `p15c_lock_mkdir` and `p15c_lock_stale`.
- **Lock proof (C10):** a second real `run_negatives.sh` started while the first ran refused with `held by pid … : bash tools/run_negatives.sh`, rc=1 (`logs/c10-concurrent.txt`). The reproduction: legacy rc=1 (`t4-norow` collision), fixed rc=0 (`logs/c10-interference.txt`).
- **`./scripts/build test`:** rc=0, 1015 passed, 2 skipped (actionlint and minisign absent), up from 993 at `53a628c` (`logs/build-test-p15close-ae10987.txt`).
- **Full gate `bash tools/run_checks.sh --keep-going`:** run at xr-browser `ae10987` + xr-core `30adb62` with the evidence edits uncommitted: 168 PASS lines, **1 LANE FAIL, `check-pin-alive`**, which is expected: the DEPS pin `30adb62` is not on origin until a human pushes xr-core (HG-P15-TOKEN). 17 visible SKIPs: 14 ci-run verifications and 2 scheduled-lane verdicts because the unauthenticated GitHub API returned 403, plus actionlint absent. rc=1 is from that single lane (`logs/gate-p15close.txt`). A first attempt was discarded: the kernel OOM-killed `mojom_fuzz_gen.py` because stale pytest temp dirs had filled the 1 GB tmpfs `/tmp`. After clearing them, the lane passed alone and the whole gate was run again from the start. The transcript above is the second run.
- **Mutation** (`docs/state/mutation-scores.json`; full matrices, seeds and gates unchanged):

  | core | run | result |
  |---|---|---|
  | permissions | sample 90, seed 20260908, xr-core `30adb62` | 90/90, deny-guard 23/23, PASS (fresh since `4d6672d`) |
  | commands | FULL, seed 20261010, `c9c51d8` | 215/219 = 98.17%, deny-guard 8/8, PASS |
  | settings | FULL, seed 20260911, `c9c51d8` | 242/290 = 83.45%, deny-guard 13/18, **FAIL** |
  | settings | FULL, `a94aff9` (tests added) | 277/292 = 94.86%, deny-guard 18/19, FAIL |
  | settings | FULL, seed 20260911, xr-core `30adb62` (deny-guard made reachable) | 278/292 = 95.21%, deny-guard 19/19, **PASS** |
  | settings | FULL, `30adb62` (SaveAt seam) | **278/292 = 95.21%, deny-guard 19/19, PASS**, 1 kill by timeout |

  `mutation_freshness`: PASS, pin `30adb622ae82`, 10 cores fresh.
- **Regressions caught on the way:**
  - At `1d5f018`, C5 broke count literals: 27 to 28 commands in `test_host.cc` (xr-core `c9c51d8`), and in three pytest literals (`test_p7_commands_tools`, `test_p8_t7_help_deep_link`, `test_patch_manifest_check`). They were fixed in the C5 and C7 commits.
  - The intermediate gate `rc-p15-b` had 4 failing lanes: pytest, `ci_lane_discovery` (the same literals), `check-pin-alive` (an unpushed pin, expected locally) and `mutation_freshness` (C11). Each is closed except `check-pin-alive`, which needs the push.
- **Per-commit gating:** only the final head was gated. The eleven xr-browser commits were staged from one working tree, so the intermediate commits were not each run through `run_checks.sh`. That is a deviation (⑫).

---

## ⑧ The laws changed this phase

Each law below comes with a planted negative.
- `permission_write_path_check.py`: the clock-free row for `permissions/core/**`.
- `permission_host_parity.py`: host and fake parity for permissions.
- `fuzz_fleet.py` and `seed_corpus.py`: fleet row 7, with no count literal. `seed_corpus --check` covers the row.
- `assumption_drift_check.py --row A4`: offline anchor drift.
- `keyboard_tasks_permissions_check.py`: its own law. The 12-task law is untouched.
- `permission_patch_roundtrip.py --check`: patch 0400 against the pin.
- `permission_iso_cells.py` inside `isolation_matrix.py`: the permission cells and the empty-run law.
- `permission_audit_count_check.py`: invariant 7.
- `neg_interference_repro.py` and the `run_negatives.sh` lock: the C10 hazard.
- `mutation_test.py`: a suite timeout counts as `killed(timeout)` instead of crashing the run. `tools/tests/test_p15c_mutation_timeout.py` runs a hanging suite and a passing control.
- `assumptions.py --as-of`: no wall clock in the gate closure.

No gate was weakened. No threshold, seed, sample size or timebox changed.

---

## ⑨ Corrections to previous claims, and the parity verdict

**Corrections.** Each one is an appended row with a `corrects` link; nothing was deleted.
- `P15-T3`: VERIFIED with no kill -9 test in the tree. Now `P15-T3-C`.
- `P15-T0`: RFC-0002 was missing. `P15-T0-RFC2` adds it, and `P15-T0-C` re-scores the row to HUMAN-GATED on the register.
- `P15-T2`, `T4`, `T5`, `T8`, `T9.3`, `T9.4`, `MUT`, `GATE-CANDIDATE` and `HOSTED` are corrected by their `-C` rows.
- The settings mutation record `286/286` at `85289cd` was a false-kill result of the pre-`3fe8d7e` harness. The FULL re-run measured 242/290.
- The mutation harness crashed with an uncaught `TimeoutExpired` on a hanging mutant (fixed; ⑧).
- HG-P15-A4 is closed by C4 and recorded as superseded, not deleted.
- §11 of the research log no longer says that `53a628c` was pushed.

**Parity verdict**, printed by `python3 tools/ci_parity_check.py` at the final head in this sandbox (verbatim):

```
ci-parity: PARTIAL (6 lane(s) will be stricter on CI: actionlint (workflow-lint deep pass (expressions+schema)); cargo (Rust conformance + shield vendor/shim lanes); faketime (date-invariance ambient probe (the scheduled governance lane installs it and demands it)); minisign (P3 fast-lane TEST signing drill); rustc (Rust conformance + shield vendor/shim lanes); shellcheck (actionlint's shell-script pass (the SC2251 class))) — exit 0 by design: a printed fact, never a gate red; re-run to re-prove
```

P14's line named 2 lanes. This one names 6, because the helper tools were not reinstalled after the sandbox reset (② P0-5).

---

## ⑩ CI + repo state

**The hosted state, before any "done":** no P15-CLOSE commit is on origin.

```
$ git ls-remote https://github.com/RRRTX-Labs/xr-browser.git refs/heads/main
267de392bda0253a1126cf16df3a7ad31c98ddaa	refs/heads/main
$ git ls-remote https://github.com/RRRTX-Labs/xr-core.git refs/heads/main
e18b82f7c345c6fb8b0aecbef2f39c53a8d84312	refs/heads/main
```

The last hosted verdicts are at `267de39` (P14-CLOSE): governance `38071604754` and core-hardening `38071604748`, both success. Nothing is claimed for any P15-CLOSE sha.

**What a human does** (HG-P15-TOKEN; the agent does not push in this phase):
1. Push xr-core `main` to `30adb62`, first, so that the pin is alive. This is a fast-forward from `e18b82f`.
2. Push xr-browser `main` to the evidence head, a fast-forward from `267de39` that carries `53a628c`.
3. Read governance and core-hardening at that head. Core-hardening triggers on `DEPS`, `tools/mutation_test.py`, `tools/fuzz_fleet.py` and `.github/workflows/core-hardening.yml`, which this push touches.
4. Record both runs as `ci-run` rows through `tools/evidence_ci.py`. Only then may the `Phase-Close: P15` commit set `state: final` and `phase_head`, with the before/after no-PENDING negative.

If either run is red, run `tools/ci_triage.py --sha <head>`, and read `/rate_limit` before believing an "access denied".

---

## ⑪ Definition of Done, row by row

**P15-CLOSE §6:**

| # | condition | status |
|---|---|---|
| 1 | C1–C11 are each VERIFIED, NOT-RUN with a method, or HUMAN-GATED | holds: ③; no C item is PARTIAL or BLOCKED-DEFERRED |
| 2 | original P15 DoD items re-scored against the tree | done as appended `-C` rows. The original P15 brief (`PHASE-P15.md`) is not in this workspace, so the re-score maps the P15 rows through the P15-CLOSE brief's items |
| 3 | the C10 hazard is resolved with a red-then-green negative | holds: ⑦ |
| 4 | hosted governance and core-hardening are green at the final head, after a human push | **does not hold**: no push (⑩) |
| 5 | only explicit human gates remain, each with its action | holds for gates (⑫); the push itself is the open act |

Because condition 4 fails, the state stays `interim`.

**P15 rows after correction:**

| status | rows |
|---|---|
| VERIFIED | T0-RFC2, T1, T3-C, T5-C, T6, T7, T8-C, T9.1, T9.2, T9.3-C, T9.4-C, T10, C10, MUT-C, FROZEN, CLOSE |
| PARTIAL | T2-C (Panel not built), T4-C (no Activity surface; rendering NOT-RUN), GATE-CLOSE (pin-alive needs the push) |
| HUMAN-GATED | T0-C (HG-P15-REGISTER), T9.5 (HG-P15-S0-REVIEW) |
| BLOCKED | HOSTED-C (human push) |

---

## ⑫ Deviations, human gates, and what is inherited

**Deviations.**
1. **Intermediate commits were not individually gated** (⑦). The xr-browser commits `f5562b4`..`ae10987` were staged per item from one working tree, with shared files rebuilt per commit. Only the final head ran the full gate.
2. **Two cores outside C11's named scope were re-scored** (commands, settings), because C5 made them stale. Settings needed tests plus two behaviour-preserving seams in `settings/core/counters.{h,cc}`: `RetentionCutoff` and `SaveAt`. Those seams change a core file, and its re-score is recorded.
3. **C5 search terms** live in schema `aliases`, not in `settings-search.ts`.
4. **C7 is one file.** Notifications keep the platform OK/Cancel order (HG-P15-UX).
5. **C9 is option (b).** No Activity tab was invented.
6. **The C10 lock is per checkout.** Two checkouts that share one sibling are serialized only by an operator rule (`docs/process/ci-invocation.md`).
7. **C2 BUILD.gn.** `identity/BUILD.gn` keeps the old shape, which belongs to the identity owner.
8. **The C7 roundtrip tool was rewritten from its spec** after a sandbox reset removed the untracked file. It reproduces the committed patch byte for byte.
9. **Helper tools.** P14-CLOSE installed shellcheck, faketime and minisign for its final gate. P15-CLOSE's final gate ran without them (P0-5), so their lanes are SKIP.

**Human gates** (`evidence/P15/human-gates.md`), each with its action:
- HG-P15-S0-REVIEW, HG-P15-ADR51, HG-P15-REGISTER, HG-P15-RFC2 and HG-P15-ACTIVITY-SURFACE;
- HG-P15-P14CLOSE (confirm the record; push `53a628c`);
- HG-P15-PHASEID, HG-P15-COMMITTER and HG-P15-UX;
- HG-P15-MUTATION (accept the 14 settings and 4 commands equivalence arguments);
- HG-P15-BACKSTOP, HG-28 and HG-34;
- **HG-P15-TOKEN**: the PAT pasted into this conversation, which was used for the P14-CLOSE push only, should be revoked or rotated.

**Inherited, not done here:**
- P14's papercut budget overrun.
- The `p13_t1` negatives-ordering fragility that P14-CLOSE recorded (exit 77 in a scratch copy before the toolchain is installed). C10 did not change that case.
- IdentityProvisioning stays PROPOSED only.
- The full permissions mutation matrix and libFuzzer (HG-28).
