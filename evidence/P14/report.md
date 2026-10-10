# P14 report: identity, closed honestly (P14-CLOSE)

**Phase:** P14 (T0–T10 · P0-1…P0-4), closed by P14-CLOSE (C-0…C-6).

**Trees at the close's open:** xr-browser `cabb36ff75512e3179da35190278846b929d4130`
(`origin/main`), xr-core `13a5f7d` (= `DEPS.xr_core_rev` at that commit). The
brief was written against older heads (`01baba0` / `81376ac`), so every claim
below was re-derived against `cabb36f`, never copied from the brief.

**Author:** the P14-CLOSE agent (committer `XR P14-Close Agent
<p14-close@users.noreply.github.com>`, author `ahmadrrrtx`). Every number below
is a transcript under `evidence/P14/logs/` or a command quoted with its output.
Anything this sandbox cannot see says so in the same sentence.

**The one-line version.** At `cabb36f`, P12 and P13 were still `interim`, two
P14 rows (T4, T7) were `NOT-RUN` for work that a sandbox *can* do, four rows were
`BLOCKED-PENDING`, and two mutation records (identity 204/204, commands 219/219)
were harness false kills. All of that is now fixed with code, laws and planted
negatives. What remains open is only what this sandbox cannot do (pixels, a
rendered WebUI page, a real `kill -9`, a real profile FS-diff) and what only
humans may do (S0 dual review, freeze ratification, token rotation). Each of
those is `NOT-RUN` with a method path, or `HUMAN-GATED` with named files.

---

## ① The reproduction, verbatim

Read at the opening heads with `git show` (no worktree, nothing rebuilt), in
`evidence/P14/logs/c6-reproduction-cabb36f.txt`:

```
state: interim  phase_head: f96949914955b38e2c0204ef9792e685264672e7  ci_claimed: ['governance']   (P12)
state: interim  phase_head: None  ci_claimed: None                                                 (P13)
state: interim  phase_head: None  ci_claimed: None                                                 (P14)
  P14-P0-3 BLOCKED-PENDING-P0-3
  P14-T4 NOT-RUN
  P14-T5 BLOCKED-PENDING-T5
  P14-T6 PARTIAL
  P14-T7 NOT-RUN
  P14-SECURITY BLOCKED-PENDING-SECURITY
  P14-CONTRACTS BLOCKED-PENDING-CONTRACTS
  P14-DOCS BLOCKED-PENDING-DOCS
  P14-EVIDENCE BLOCKED-PENDING-EVIDENCE
identity 204 / 204 100.0 at 9ee4952ce89c
commands 219 / 219 100.0 at 62b2c923aa7a
0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1  (FROZEN.yaml)
docs/identity/: binding, lifecycle, memory-accounting, provisioning, templates (5 of 9)
```

The brief's description held on every point it made. Two things it did not say
turned up while working: both 100% mutation records were false kills (⑨), and
`LooksOpaque` made identity creation fail by chance for short all-hex display
names (④, an S0 fix).

---

## ② C-0: P13 and P12 closed

xr-browser `fc9a8c4` (trailers `Phase-Close: P13`, `Phase-Close: P12`). Both
bundles flip to `state: final` with `phase_head` `cabb36f`, where governance run
`37975129363` (job `113971387085`) and core-hardening run `37975128332` are both
`success`, read from the public Actions API. Each bundle gets same-head `ci-run`
rows for both workflows, with per-step conclusions in the notes. It is
append-only: the PENDING rows (P13-EVIDENCE, P13-REPORT, P12's BLOCKED-CAUSE row)
are superseded by correction rows with `corrects` links; no row is edited.
P12's `phase_head` moved from `f969499` (no green run, and never will be) to the
first green head whose tree contains its work, with a dated reason.

The before/after negative is `tools/negatives/p14c_c0.sh`: final WITH the links
passes, final with the links stripped fails on the PENDING law. Transcripts:
`evidence/P13/logs/`, `evidence/P12/logs/` (`p14c-c0-*`).

---

## ③ C-1 … C-5: files, commits, status

| item | xr-core | xr-browser | status |
|---|---|---|---|
| C-1 identity chrome (T4) | `a569801` | `1f04e96` | PARTIAL: code, state law, 20 structural snapshots run here; pixels NOT-RUN (`docs/qa/browser-harness.md#identity-chrome-visual`) |
| C-2 ledger `identity_id` (T5) | `ad3026c` | `d9e6adb` | VERIFIED |
| C-3 `xr://identities` (T7) | `5ffa695` | `3a46725` | PARTIAL: model, gate, view core, laws run here; rendered page NOT-RUN (`docs/qa/browser-harness.md#identities-page-rendered`) |
| C-4 security | `f031c33`, `aaf79bd`, `a7ed1ab`, `dec1d83` | `d9e6adb` | PARTIAL: every automated half run; S0 dual review HUMAN-GATED |
| C-5 docs and contracts | `e18b82f` | `18caead` | VERIFIED |
| fix | — | `990fd1d` | a human-gate row cited a rewritten sha; corrected |

**C-1.** `xr-core/ui/identity-chrome/`: `states.json` (3 states × 4 layouts), a
pure core, lit elements, 20 structural snapshots (4 layouts × 5 themes, 28 edge
lines recorded). `tools/identity_chrome_check.py --check` is the law: every
state needs a class, an accessible name, an SR string, a route string and a
sample; sample colours equal `templates.cc`; contrast is computed from theme
tokens. Eight planted defects redden it (`tools/negatives/p14c_c1.sh`),
including a state with a missing SR string. Transcript `logs/c1-identity-chrome.txt`.

**C-2.** `ledger-identity-overlay-v1` (LIVING) makes `identity_id` REQUIRED on all
10 event classes (the 8 frozen `ActivityKind` values, read live from the mojom,
plus `kHistory`/`kBookmark`). 35 golden vectors replay byte-identically against
the C++ host and the Python twin. The differential oracle prints
`history-oracle: upstream history diff-clean (2 vectors)`. A row without an id is
`unknown`; a cross-identity omnibox row is dropped and not counted, and its
planted leak reddens both backends. No frozen stamping condition blocked it
(⑤). Transcript `logs/c2-ledger-identity.txt`.

**C-3.** The page model `identity/core/manager_page.{h,cc}` (states `normal`,
`empty`, `purge-unverified`, `dev-refused`; per-identity tab count, storage bytes,
permission count; rename/recolor/archive; reset-all). Dev only BY ENFORCEMENT:
`identity_host --build-channel` defaults to `release` and every non-dev channel
gets `build-channel-not-dev:<channel>` with no page bytes; the roster command
`identities.page` rides `build.channel-dev`. `shield_state_check` is EXTENDED
(`tools/identity_page_states.py`), not bypassed; `attention_check` stays green
with the new copy and now scans the identity surfaces. l10n/a11y generators
regenerated, all `--check` green. Transcript `logs/c3-identities-page.txt`.

**C-4.** ④.

**C-5.** Four guides (`docs/identity/{visual,disposable,manager,restore}.md`;
nine in the family). §1.13 regenerated BY ITS GENERATOR: `tools/isolation_matrix.py`
also emits the Isolation Card's identity rows
(`xr-core/test/isolation/identity-card-rows.json`) and the generated block in
`docs/limitations.md`; the P13 card renders them (`identityCardView`) and
REFUSES prose, in the generator and in the view, each proved by a planted
negative. The papercut census gains a ledger (status, test, owner, budget,
run-here) for all 15 rows, enforced by `build/spike/census_lint.py`. The
registry records the card rows and the PROPOSED `IdentityProvisioning` freeze
row (⑤). Transcript `logs/c5-docs-contracts.txt`.

---

## ④ Security evidence

* **Derivation probes, byte-absence.** For partition name, URL, title and log
  line, a secret-shaped value is planted and its absence asserted in stdout AND
  stderr, including `MoveTab`'s reload message and every error string
  (`xr-core/identity/tests/test_derivation.cc`, 163 checks; matrix cell
  `identity-derivation-probe`).
* **Cross-identity process assertion in the fast lane.** `IdentityStore::Insert`
  refuses a partition shared across identities; the test cites the P4/P6
  partition code it mirrors so the two cannot drift; a planted share reddens
  (`tools/tests/test_p14c_security.py::test_planted_partition_share_reddens`,
  `tools/negatives/p14c_c2.sh`).
* **Purge and verify.** The `disposable-zero-residue` cells run a real
  `build/spike/fsdiff.py` diff around the host: `fs-diff clean close 0 paths +
  planted leftover caught=True` on all 5 pairs; neutering the diff turns the cell
  FAIL.
* **Policy consulted on the path.** Stubbing the vault consult (absent, or
  granting) makes the check fail (`test_vault_consult_stubbed_*`).
* **An S0 fix made here.** `LooksOpaque` refused short all-hex display names
  ("B", "Cafe", "Dad") because a random domain contains them by chance (about
  87% for one letter), so `Create` failed with `kNotPermitted` at random.
  xr-core `f031c33` judges only all-hex probes of 8+ characters. The mint
  digest decoding became a tested function (`dec1d83`), output byte-identical
  and pinned by two independent known answers.
* **S0 review stays HUMAN-GATED** (`evidence/P14/human-gates.md`):
  HG-S0-IDENTITY, HG-S0-P14C-OPACITY (`f031c33`), HG-S0-P14C-MINT-DECODE
  (`dec1d83`), HG-S0-P14C-OVERLAY (`ad3026c`, `aaf79bd`) and HG-S0-P14C-PAGE
  (`5ffa695`), each naming files and invariants. Green CI satisfies none of
  them. `tools/owners_sync.py --check` is green.

Transcript `logs/c4-security.txt`.

---

## ⑤ Contracts

* `docs/contracts/FROZEN.yaml` is byte-identical. Mine:
  `0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1`; the
  brief's: `0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1`.
  No `mojom/` file, no frozen vector and no `ratified:` value was touched.
* `ledger-identity-overlay-v1`: LIVING, registered in
  `docs/contracts/registry-post-freeze.md` as an amendment record. Failure
  condition 1 was checked and does not fire: the frozen `ActivityRow` already
  carries an identity, and living schemas without one are wrapped, not edited.
* `identity-isolation-card-rows` v1: LIVING, generated.
* `IdentityProvisioning` internals: a PROPOSED freeze row, recorded in the
  registry as a human ratification item (HG-26) and NOT applied. Each item is
  checked against ADR-0042 "Contracts out" (a)–(d) and the tests that hold it.
* No new mojom, so no new mojom ADR and no `mojom_fuzz` change. No ADR or RFC
  changed state.

---

## ⑥ Perf & budgets

* No perf row was produced or changed. Switch/wake to first paint and RSS stay
  NOT-RUN with methods in `docs/qa/browser-harness.md`; no MB or ms figure
  appears anywhere as measured.
* No upstream patch file was added (`git diff --name-only cabb36f..HEAD`
  contains no patch). The budget unit (upstream FILES) is unchanged.
* The papercut ledger sums the reservations honestly: 99 files, of which ui 47
  and extension_chokepoint 8 exceed the §1.2 caps (35 and 2). That is a planning
  fact for the phases that land the browser halves, stated in
  `docs/spike-identity/papercut-census.md`, not hidden.
* Mutation (full matrices, seed 20261010, at the pin `5ffa695`, which is
  byte-identical to `e18b82f` for both cores): identity 286/292 = 97.95%,
  deny-guard 32/32, PASS; commands 215/219 = 98.17%, deny-guard 8/8, PASS. Every
  survivor is dispositioned as an equivalent mutant in
  `docs/state/mutation-scores.json`; `mutation_freshness` is green. Transcripts
  `logs/t-mutation-identity-v4.json`, `logs/t-mutation-commands-c3.json`.

---

## ⑦ Gates & regressions

Every line below is quoted from a transcript in `evidence/P14/logs/`.

**The full gate**, `logs/c6-full-gate-18caead-keepgoing.txt`, was run in fresh
detached worktrees at the content heads (xr-browser `18caead`'s lanes, xr-core
`e18b82f` = `DEPS.xr_core_rev`), with the lint tools installed.
`bash tools/run_checks.sh --keep-going` reports **one FAIL lane:
`check-pin-alive`**. That lane asks GitHub whether the pin exists on origin, and
`e18b82f` cannot be there until xr-core is pushed. It is re-run after the push
(⑩), from a clean clone. Every other lane passes, including:

```
PASS: ledger_identity_check (35 vectors, 10 event classes, backends: C++ identity_host + Python twin)
PASS: identity_chrome_check (3 states, 7 samples, 4 layouts x 5 themes = 20 snapshots; 28 mark(s) carry a text-token edge for contrast)
PASS: owners_sync
PASS: sibling_pin_check (65 sibling reader(s) classified, arg-only=16, gate-ordered=15, probe=4, routed=5, self=2, test=23)
PASS: touched-file size law (34 touched .py/.sh in 01baba0d6ce8d923b833e30dbf25463211ec8d91..HEAD, all <= 380 lines)
PASS: evidence_check (15 bundle(s), 0 failure(s); presence law: every phase in git history carries a bundle)
PASS: census-lint
  actionlint: ran, clean
PASS: workflow-lint
PASS: host_protocol_check (7 host(s), every method literal documented, response law declared)
PASS: shield-state (all 5 host page states rendered: ... shield.page behind build.channel-dev ...)
PASS: parity_completeness (8 pair(s), 0 failure(s))
PASS: isolation_matrix --check (matrix record and identity card rows diff-clean)
PASS: date_invariance_check (3 invariant lane(s) identical across 2 dates [2026-01-01 .. 2038-01-18]; ... 12 ambient-clock probe(s) via faketime ...)
PASS: mutation-freshness (pin e18b82f7c345, 10 core(s) fresh)
surfaces_check: 15 surface(s), 0 violation(s) (PASS)
```

The attention lane passes with the new identity copy scanned (`P14-T7 identity
rule: 4 identity surfac…`, full line in the transcript).

**Commit by commit.** The rule is that every commit leaves the gate at 0 FAIL,
apart from the unpushed-pin lane. It is checked in worktrees at each pair:
`d9e6adb`/`dec1d83` (one FAIL: `check-pin-alive`), plus the C-1 and C-3 pairs
after the register fix in ⑫. Every pair's only red lane is `check-pin-alive`
(`logs/c6-intermediates.txt`, which also keeps the pre-amend red as the
finding).

**`./scripts/build test`**, `logs/c6-build-test-18caead.txt`:
`993 passed in 445.02s`. That is 0 failed and 0 skipped from the tool policy,
because the lint helpers are installed; codesign and signtool are absent, as is
normal for Linux. The baseline at the opening head `cabb36f` is **947
collected** (`logs/c6-build-test-baseline.txt`, same paths, collect-only), so
the suite grew by **46**.

**`tools/run_negatives.sh`**, `logs/c6-negatives-18caead.txt`, run 2: `ALL NEGATIVE CASES
REJECTED AS EXPECTED (N=232)`, with 2 cases SKIPped visibly (`policy_host` and
`commands_host` are not built in a negatives-only worktree; CI has g++). Run 1
in the same file shows the ordering fragility named in ⑫. The P13
figure was 163, and 220 cases were registered at `cabb36f`. This close adds 13
named cases:

`p14c_c0_final_with_corrects_is_green_without_is_red`,
`p14c_c1_identity_chrome_law_reddens_on_each_plant` (8 plants),
`p14c_c2_omnibox_cross_identity_leak_reddens`,
`p14c_c2_upstream_history_write_is_delta`,
`p14c_c2_laws_coverage_schema_drift_redden`,
`p14c_c2_cpp_omnibox_leak_reddens_test_ledger_tag`,
`p14c_c4_planted_partition_share_reddens_test_derivation`,
`p14c_c3_identities_page_state_law_reddens`,
`p14c_c3_reset_all_bypass_reddens`,
`p14c_c3_identities_modal_vocabulary_reddens`,
`p14c_c3_cpp_dev_channel_admits_all_reddens`,
`p14c_c5_papercut_ledger_reddens` (5 plants),
`p14c_c5_identity_card_refuses_prose` (3 plants).

One existing fixture was repaired: `p13_t1`'s scratch core now carries the
generated card rows (see `18caead`'s message).

**`evidence_check --strict --require-phase-final`**: `PASS: evidence_check (13
bundle(s), 0 failure(s); …)` at the content head. It is re-run at the freeze
commit and at the closing commit (⑩).

**Mutation**: see ⑥ (identity 97.95% and commands 98.17%, with every deny-guard
killed).

---

## ⑧ The laws changed this phase

| law | change | negative |
|---|---|---|
| identity chrome state law (new) | `tools/identity_chrome_check.py` (+ `--check` snapshots) | `tools/negatives/p14c_c1.sh` (8) |
| ledger identity overlay (new) | `tools/ledger_identity_check.py`: both backends, coverage, schema, drift, generator, oracle | `tools/negatives/p14c_c2.sh` |
| identities page state law (extension) | `shield_state_check` via `tools/identity_page_states.py` | `tools/negatives/p14c_c3.sh` |
| attention (extension) | the P14-T7 identity rule and ledger section | `tools/negatives/p14c_c3.sh` |
| Isolation Card identity rows (new) | `tools/identity_card.py` from `tools/isolation_matrix.py`; the view refuses prose | `tools/negatives/p14c_c5.sh` (3) |
| papercut ledger (extension) | `build/spike/census_lint.py` `lint_ledger` | `tools/negatives/p14c_c5.sh` (5) |
| C-0 finality before/after | the real bundles, links on and off | `tools/negatives/p14c_c0.sh` |

No gate was weakened, no `--check` rewrites in-tree, and every touched file
under `build/`, `tools/`, `release/` is within 380 lines. One negative fixture
changed: `p14_t9.sh`'s census fixture now links `tools/` and `evidence/`
read-only, because the ledger cites paths there; its control stays green.

---

## ⑨ Corrections to previous claims, and the parity verdict

1. **identity 204/204 (at `9ee4952`) was a false kill.** It predates the
   harness fix (xr-browser `3fe8d7e`, `b6cd40f`: stale objects and unrestored
   builds counted as kills). Re-scored: 220/248 = 88.71%, deny-guard 23/29,
   FAIL (`logs/t-mutation-identity-v3-rescore.json`). After new tests and the
   tested decode: PASS (⑥).
2. **commands 219/219 (at `62b2c92`, P11-T6) was a false kill too.** On the
   fixed harness the unchanged core scored 193/219 = 88.13%, deny-guard 4/8,
   FAIL (`logs/t-mutation-commands-c3-rescore.json`, reproduced twice on a clean
   `/tmp`). After new tests (no behavior change): PASS (⑥).
3. **P14-T4 and P14-T7 were `NOT-RUN` for work a sandbox can do.** Corrected by
   P14-T4-STRUCTURAL and P14-T7-DELIVERED; `NOT-RUN` now covers only pixels and
   the rendered page.
4. **HG-S0-P14C-MINT-DECODE cited a rewritten sha** (`990fd1d`).
5. The PENDING rows of P12, P13 and P14 are superseded by appended rows, never
   edited.

The parity tool's verdict line, verbatim, from `logs/c6-ci-parity.txt` (run 2,
with the lint helpers installed, as part of the full gate):

```
ci-parity: PARTIAL (2 lane(s) will be stricter on CI: cargo (Rust conformance + shield vendor/shim lanes); rustc (Rust conformance + shield vendor/shim lanes)) — exit 0 by design: a printed fact, never a gate red; re-run to re-prove
```

**The two ABSENT rows, explained.** `cargo` and `rustc` are absent on this
host. The lanes that need them (Rust conformance and the shield vendor/shim
lanes) SKIP here with a visible reason, and they run on the hosted runner, which
is stricter. They were not faked, and they are proven by the core-hardening run cited in
⑩. That workflow is the only one that installs a Rust toolchain; governance
does not use it. Installing a Rust
toolchain only to turn a printed row green would be a new host dependency that
the brief does not ask for.

The run 1 line (before the install) named six lanes: actionlint, cargo,
faketime, minisign, rustc and shellcheck. Four of them were closed by
installing the real tools, pinned the way `docs/dependencies/helper-tools.yaml`
prescribes. `python3.12 differs` (local 3.13) is printed as a note by design,
not as a weaker lane.

The live network probes in the same transcript were re-proved during this run
and not inherited from any earlier note.

---

## ⑩ CI + repo state

**The hosted state, before any "done":** at the time this file was written, no
P14-CLOSE commit was on origin:

```
$ git ls-remote https://github.com/RRRTX-Labs/xr-browser.git refs/heads/main
cabb36ff75512e3179da35190278846b929d4130	refs/heads/main
$ git ls-remote https://github.com/RRRTX-Labs/xr-core.git refs/heads/main
13a5f7d980101ac8d61b707d7728674f268f8990	refs/heads/main
```

The last hosted verdicts are at `cabb36f`: governance run `37975129363` and
core-hardening run `37975128332` (workflow_dispatch, run 45), both `success`
(`logs/c0-ci-triage-cabb36f.txt`, `logs/c0-scheduled-lanes-cabb36f.txt`). That
is the head P13 and P12 closed on, not this phase's.

**How the final-CI claim is made.** The commit that carries this file is the
**freeze commit**, and it becomes `phase_head`. It cannot cite its own runs:
they do not exist until it is pushed. So the claim is recorded by the next
commit, the closing declaration (`Phase-Close: P14`), the same way P13 and P12
did it. That commit adds:

* same-head `ci-run` rows P14-CI-GOVERNANCE and P14-CI-CORE-HARDENING, whose
  `head_sha` is the full freeze sha, each with run and job ids, the per-step
  conclusions and a `tools/ci_triage.py --sha` transcript;
* the scheduled-lane view;
* `check-pin-alive` and `ls-remote` for both repos, re-read from a clean clone
  after the push, plus DCO counts and clean trees, in `logs/repo-state.txt`;
* `state: final`, `phase_head` and `ci_claimed: ["governance",
  "core-hardening"]`, plus the additive `repos.close_head`.

The push order is xr-core first, so the pin is alive before governance checks
out the sibling, then xr-browser. Both are fast-forward pushes; nothing is
force-pushed.

Until the closing commit lands, this report claims **no** hosted result for the
freeze sha. If either workflow is red there, the brief's failure condition 3
applies: stop and paste the `tools/ci_triage.py` output and the annotation text.

---

## ⑪ Definition of Done, row by row

| # | status | proof |
|---|---|---|
| 1 | VERIFIED | ②; `evidence/P13/evidence.json`, `evidence/P12/evidence.json`, `tools/negatives/p14c_c0.sh` |
| 2 | PARTIAL (pixels NOT-RUN with method) | ③ C-1; `tools/identity_chrome_check.py`, `tools/negatives/p14c_c1.sh` |
| 3 | VERIFIED | ③ C-2; `docs/contracts/registry-post-freeze.md`, `tools/ledger_identity_check.py` |
| 4 | PARTIAL (rendered page NOT-RUN with method) | ③ C-3; `tools/identity_page_states.py`, `tools/attention_check.py` |
| 5 | PARTIAL (S0 review HUMAN-GATED) | ④; `evidence/P14/human-gates.md` |
| 6 | VERIFIED | ③ C-5, ⑤; `docs/identity/`, `docs/limitations.md`, `docs/spike-identity/papercut-census.md` |
| 7 | VERIFIED at the closing commit | this file; `evidence/P14/evidence.json` |
| 8 | VERIFIED at the closing commit: 0 FAIL except `check-pin-alive`, which is re-proved after the push; the range form is the hosted governance run; parity is printed in ⑨ | ⑦, ⑨, ⑩ |
| 9 | VERIFIED: build test 947 to 993 with 0 failed; negatives N=232, up from P13's 163, with 13 new cases named; identity mutation fresh; evidence_check strict is 0 failures; date-invariance identical; the protocol, parity, surfaces, owners and attention lanes are green; `check-pin-alive` and `ls-remote` are recorded at the closing commit | ⑦, ⑥, ⑩ |
| 10 | recorded by the closing commit | ⑩ |
| 11 | VERIFIED | this file, in order |
| 12 | VERIFIED | ⑥; every browser number is NOT-RUN with a method |

---

## ⑫ Deviations, human gates, and what P15 inherits

**Deviations and environment notes.**

1. **Local history was rewritten before any push, in both repos, and never
   after.** In xr-core, amends were made while the work was local. Superseded
   shas are never cited; `990fd1d` fixed the one stale citation. In xr-browser,
   the commit-by-commit validation found that C-1 and C-3 each added a sibling
   reader (`tools/identity_chrome_check.py`, `tools/identity_page_states.py`)
   that `tools/sibling_pin_check.py`'s register did not classify. That made
   those two commits red on one lane. They were amended, together with the
   commits after them (`1f04e96`, `990fd1d`, `3a46725`, `18caead`), so that
   every commit is green on its own. The C-3 and C-5 transcript headers name the
   pre-amend base and the one-line difference. No pushed sha changed, and
   nothing was force-pushed.
2. **`/tmp` is a 992 MB tmpfs here.** Running validation, pytest, negatives and
   mutation together filled it (ENOSPC), and a build failure counts as a kill in
   the mutation harness. Every mutation number in this report was re-run on a
   clean `/tmp`, sequentially; validation now uses `/var/tmp`.
3. **The lint helpers were installed for the final gate** (actionlint 1.7.7 from
   the pinned tarball, sha256-verified per `docs/dependencies/helper-tools.yaml`;
   shellcheck, faketime and minisign as OS packages). They are host tools, not
   repo dependencies.
4. **P15 opened before P14 closed** (`docs/state/phase-base.json` = P15). P14's
   close lands on top of it, append-only.

**Human gates** (`evidence/P14/human-gates.md`): the five S0 reviews in ④;
HG-26 (freeze ratification, including the proposed `IdentityProvisioning` row);
HG-P14-USABILITY (the usability session and SR audit); HG-28 (real-rig mutation
and MET rows); HG-35 (ADR approvals); HG-32/33 (upstream filings, breakage
queue); HG-19 (treadmill policy); HG-34 (branch protection); HG-20 (token
rotation: the PAT used for this push should be revoked or rotated as well).

**P15 inherits:** the papercut budget overrun (ui, extension_chokepoint); the
browser halves of every `open-browser` census row; the farm flows in
`docs/webui-e2e.md` (P14 stage); and `check-pin-alive`, which fails locally
until xr-core is pushed, so xr-core is always pushed first.

P15 also inherits **one negatives-ordering fragility**, found by this close
(`logs/c6-negatives-18caead.txt` records both runs). Run in a fresh worktree
BEFORE anything has installed `xr-core/ui/toolchain/node_modules`,
`p13_t1`'s leak case gets the lane's exit 77 (`npm ci` in a scratch copy
without a lock) and reports "rejected, but not for the expected reason". Run
after the toolchain is installed (the hosted order: Governance checks precede
Negative fixtures), every case is rejected for its reason. The case should
SKIP visibly, as its positive-control sibling already does. That fits P15's C10
(negatives hygiene).
