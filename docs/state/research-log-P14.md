# P14 research log

Every claim this phase makes, with the command that produced it. Rows that
could not be run say so and name the method; no row is a remembered value.
Written 2026-10-01; appended as the phase proceeds.

## P0-1 — the errexit/`!` class: the sweep, fixed or recorded harmless

The hosted `governance` failure at `724b466` was
`actionlint → shellcheck SC2251` in `core-hardening.yml` (annotation quoted in
`evidence/P14/logs/p0b-workflow-lint-before.txt`). Root cause of the
local/hosted divergence, the fifth in this program: **actionlint runs its
shellcheck pass only when `shellcheck` is installed on the host**. This
sandbox had actionlint but not shellcheck, so the deep pass was silently
shallower here than on the runner image. Both linters are now installed here
exactly as CI installs them (see the versions below), and P0-2's parity tool
makes the difference a printed fact forever after.

Linter installation, reproduced from the workflows' own recipes:

* actionlint **1.7.7**, tarball
  `https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz`,
  sha256 `023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757`
  — the exact version+hash `governance.yml` pins (`sha256sum -c` output in
  `evidence/P14/logs/p0a-linter-versions.txt`).
* shellcheck **0.10.0** via `apt-get install -y shellcheck` (local-only use;
  the runner image ships its own). The version is recorded in the same
  transcript, and P0-2's parity tool prints it on every run — a finding class
  that depends on the linter's version must at least be able to name it.

The sweep, over all 5 workflow files (64 `run:` blocks):

| where | shape | disposition |
|---|---|---|
| `core-hardening.yml:236` (Rust conformance) | `! grep -q "test result: FAILED" …` — statement-level `!`, errexit-exempt, followed by 3 more lines that mask its status | **FIXED** — `if grep -q …; then echo FAIL; exit 1; fi`. This is the line the hosted annotation named (reported at the step's `run:` line 214:9, SC2251 at 22:1 inside the script) |
| `core-hardening.yml:297` (vendored-copy build) | `! grep -qE "^error(\[|:)" …` — same shape, but the **last** statement of its script | **FIXED** — harmless as written (a trailing `! cmd`'s negated status *is* the script's exit status, which is why shellcheck 0.10.0 does not flag it), but that safety evaporates the moment a line is appended below; rewritten as the explicit check like its siblings so it cannot regress by growth |
| `core-hardening.yml:322` (offline shim build) | `! grep -qE …` followed by `test -f target/release/…` | **FIXED** — the `test -f` line decided the step's status; the hunt was inert |
| `core-hardening.yml:382` (real-engine parity) | `! grep -q '"verdict": "FAIL"' …` followed by a python block | **FIXED** — same masking shape |
| `core-hardening.yml:234,302,335,400` | `cargo … \| tee /tmp/x.log` pipelines | **harmless, recorded**: every one of those scripts sets `set -euo pipefail` (line numbers verified in the same pass), so cargo's real status propagates; the brief's "no verdict may depend on a piped exit code" law holds |
| `governance.yml:235,237` | `grep -q "MET\|DEVIATION" …` | **harmless, recorded**: the `\|` is BRE alternation inside a quoted grep *pattern*, not a shell pipeline; each is a single command whose failure triggers errexit (that is the assertion) |
| `governance.yml` + `run_checks.sh` `if cmd; then :; elif [ $? -eq 77 ]` (governance.yml lanes; `tools/run_checks.sh:197,204,343,367`; `tools/checks/p11_gates.sh:28`) | `$?` compared in a condition | **harmless, recorded**: `$?` is explicitly checked in a condition context — exactly what SC2251 asks for; this is the repo's SKIP-law idiom, not the exempt class |
| repo shell scripts (`tools/*.sh`, `tools/checks/*.sh`, `build/webui/*.sh`, `build/qa/drill/*.sh`, `build/signing/tests/*.sh`) | `grep -rn '^\s*! '` | **no hits** — the class does not exist outside the workflow set (rc=1 from grep, i.e. nothing matched) |

Sweep method: `grep -n '^\s*!' .github/workflows/*.yml` for statement-level
negation, plus a per-`run:`-block pass that flags every statement-level
pipeline, every `$(…)` inside a `[ ]` test (none found in any workflow), and
every negation — the extractor and its output are transcribed in
`evidence/P14/logs/p0b-workflow-lint-before.txt`. Post-fix, the same commands
return **no findings** and `./scripts/build workflow-lint` (actionlint 1.7.7 +
shellcheck 0.10.0 present) reports **PASS, actionlint: ran, clean**
(`evidence/P14/logs/p0c-workflow-lint-after.txt`).

What the fix does **not** prove: that no *future* workflow edit reintroduces
the class. That is P0-2's job — the parity tool prints whether shellcheck is
present locally, and the hosted lane always has it, so the next
local-green/hosted-red of this class is at least visible before the push.

## P0-2 — the parity tool: what this host lacks, as a printed fact

The mechanism: `tools/ci_parity_check.py` (+ the host probes in
`tools/ci_parity_probes.py`, split by the touched-file size law), wired early
into `run_checks.sh` via `tools/checks/p14_gates.sh`; the final tally
(`kr_finish`) re-echoes the verdict line; `docs/process/ci-invocation.md` §
"the parity line" documents the contract.

Design decisions, each recorded because the next agent will need them:

* **Exit 0 on PARTIAL, by design.** A red gate would train people to install
  everything or to ignore the lane; the enforcement is the echoed verdict
  line plus the report law (evidence §⑨ must quote it). The negative battery
  pins this: `tools/negatives/p14_p02.sh` case
  `parity_gap_is_partial_and_exits_zero` FAILS if PARTIAL ever becomes a
  gate red.
* **A run with no verdict line IS a gate red.** The lane function refuses a
  verdict-less run (the never-silent law); the negative proves it with a
  PATH-stubbed interpreter.
* **Network probes go through the fetch chokepoint and are re-proved every
  run** — never cached, never read from a note. `updates.rrrtx.labs` (the
  release egress policy row) is NOT probed: the chokepoint refuses it by
  design (it is HG-38 policy data, not a fetch surface), and the refusal is
  itself the printed row.
* **4xx ≠ blocked.** A 403/404 answer proves DNS+routing+TLS work; only 5xx,
  timeouts and connection failures are "blocked" rows (the P13 503 shape).
  RATE-LIMITED vs ADMIN-ONLY for a given 403 is `ci_triage`'s call —
  finished here: `classify_refusal` (C-0.7) gives 429 its own
  RATE-LIMITED class and 401/403 the ADMIN-ONLY-or-QUOTA class that names
  `/rate_limit` as the discriminator. Two fixture tests +
  `negatives/p14_p02.sh` case 4 pin it.
* **The self-test proves the verdict is a function of the host** (the
  all-present case prints PASS; the sabotage negative — `verdict_of`
  forced to always-PASS in a scratch copy — must FAIL the self-test).
  A detector that always prints one verdict detects nothing.

Measured on this host, 2026-10-01 (transcripts
`evidence/P14/logs/p0d-parity-before.txt` and `p0e-parity-after.txt`):

* The **before** capture reproduces the P13-CLOSE host shape exactly
  (actionlint present, shellcheck removed): the composite row prints
  `actionlint+shellcheck COMPOSITE GAP … the shellcheck pass will not run
  here — the exact shape of the P13-CLOSE governance red`, while
  `./scripts/build workflow-lint` on the same shape says only
  `actionlint: ran, clean` — **silently shallower**, which is the whole bug.
* The **after** capture (both linters present) drops the composite row and
  still honestly prints PARTIAL for what this host really lacks:
  cargo/rustc (Rust lanes), faketime (the ambient date probe),
  minisign (the sign drill). Python differs (3.13.14 local vs the runner's
  pinned 3.12) — printed as a note, deliberately not counted as a weaker
  lane.
* The api.github.com quota line printed `core 60/60` at capture time — this
  sandbox's unauthenticated quota was exhausted (reset hourly), which is
  exactly the state P13 misread as "the endpoint is private". The parity
  tool prints the numbers so the next reader cannot repeat the mistake.

What this does NOT prove: that the hosted runner image's shellcheck version
(whatever ubuntu-latest ships) equals 0.10.0 — the row prints the local
version and the ledger records the runner's presence by run-proof, not by
version. If a finding class ever turns on the runner's shellcheck version,
that fact is findable in the run logs, not assumed here.

## seam decision (P14-T0) — written BEFORE the implementation commits

**The artifact read:** `docs/state/research-log-P4.md` (the measurement),
`xr-core/mojom/identity.mojom`'s PROVISIONING TIMING note (the frozen
contract's own record of it), ADR-0042, `xr-core/test/isolation/matrix.yaml`
and `isolation-matrix.json` (the §11.4 cells), and `fakes/identity.py` (the
behavioural fake whose vectors the new core must stay byte-compatible with).

**The measurement lines the decision rests on** (all file:line@pin from the
P4 log, re-verified by `./scripts/build spike citation-audit` at this tree):

* `content/browser/site_info.cc:335` — the embedder override
  (`GetStoragePartitionConfigForSite`) is consulted **only when the UrlInfo
  carries no config**, and `:282` takes the config from `url_info` when
  present — i.e. upstream's own call order makes the R2-class override a
  FALLBACK, not a primary.
* `content/public/browser/site_instance.h:255` —
  `SiteInstance::CreateForFixedStoragePartition(BrowserContext*, const
  GURL&, const StoragePartitionConfig&)`, documented as creating a
  SiteInstance in a new BrowsingInstance whose custom StoragePartition is
  **preserved across navigations**; `site_instance_impl.cc:244-256` builds
  the fixed-config UrlInfo and CHECKs the config is non-default.
* `content/browser/browsing_instance.cc:178-183` — one StoragePartition per
  BrowsingInstance is upstream's own CHECK-enforced invariant; RPH reuse
  requires `InSameStoragePartition` (`render_process_host_impl.cc:4947`).
* `content/public/browser/storage_partition_config.h:37/:57` — an empty
  `partition_domain` **is** the default partition: the fail-open trap this
  phase's mint must make unrepresentable (opaque UUIDs, never empty, never
  site- or name-derived).
* `chrome/browser/ui/navigator/browser_navigator.cc:479-504` —
  `CreateTargetContents()` is the earliest embedder point where "which
  identity is this tab?" is answerable, before the WebContents exists: the
  binding race §1.4 feared does not exist at this seam.

**The choice: ship the R3 public seam.** Identity v1's partition selection is
`SiteInstance::CreateForFixedStoragePartition` at WebContents-creation time
(the `CreateTargetContents` point), with an opaque-UUID `partition_domain`
and `in_memory=true` for Disposables (R6: `storage_partition_impl.cc:3378`
— `GetStoragePartitionPath()` returns nullopt when in-memory). The R2-class
embedder override is the **documented fallback**, not the shipped primary:
it is site-keyed (wrong granularity for identity-per-window — the partition
must follow the window's identity, not the site), and it only runs when the
UrlInfo is config-less, which is exactly the case the fixed-partition seam
prevents. This is the same resolution the frozen contract already encodes
(`identity.mojom`: "identity MUST be attached BEFORE the first SiteInstance
association; an identity CANNOT be attached to an existing tab without a
destructive reload (MoveTab encodes this ordering dependency)").

**Does the measurement support the plan's assumption?** The plan locked
"R2 seam (or documented fallback shipped)". The measurement shows the R2-
*named* mechanism is real but fallback-by-construction, and the spike's own
R3 finding is the seam that is public, patch-free (§12.7 satisfied: zero
`content/**` changes, zero patch-budget consumption) and CHECK-guarded
upstream. That IS the plan's parenthetical — the documented fallback is what
ships — so there is no cross-subsystem redesign question and nothing to
escalate. The seam needs no seam patch at all, so the patch budget is
untouched by this decision (`budget.md` unchanged: 4 entries / 21 files /
150 cap).

**What this decision does NOT prove:**

* No runtime behaviour — nothing was compiled against Chromium (HG-9; every
  browser-measured claim in this phase is NOT-RUN with its method in
  `docs/qa/browser-harness.md`). The seam's existence, publicity and
  invariants are static, cited facts; its behaviour under load is the rig's
  to prove.
* DNS isolation is qualified, not proven: R5 measured one
  `HostResolverManager` per NetworkService (`network_service.cc:492`), so
  "per-identity DNS" is NOT claimable from the seam choice; per-partition
  `NetworkContext` params (`storage_partition_impl.cc:3506`) are the hook
  that exists, and the OS resolver cache is outside the browser entirely.
* Storage-key plumbing for BroadcastChannel/SharedWorker/`window.name` was
  never fetched (P4's recorded census gap) — the §11.4 matrix documents
  those cells rather than guessing them.
* The R2-vs-R3 granularity argument is a design argument from the measured
  call order, not a measured runtime difference.

### P0-2 addendum — where the probe URLs live (a law found by the gate itself)

The first full-gate run reddened `fetch_allowlist_check` on the parity tool's
probe URLs: URL literals in code outside the chokepoint are refused
(the ci_triage precedent — "a literal here would be a second, unreviewed copy
of the network surface"). Two candidate fixes were rejected before the
shipped one:

* **Rejected:** URL constants in `build/upstream/fetch.py` — the file sits at
  the 380-line touched-file ceiling (measured: 380 before, 403 after), and
  the size law splits by responsibility, never by squeezing the chokepoint.
* **Rejected:** an `EXEMPT_FILES` entry for the parity tools — the exemption
  also disables the network-import/socket checks for the whole file; a
  narrower fix exists.

**Shipped:** the canonical probe paths are reviewable DATA —
`docs/state/parity-probe-paths.json` (host → canonical read-only path → what
real lane fetches it), the same class as `release/egress-allowlist.json`, and
inside the `docs/state/` class the checker itself sanctions for doc-data.
The chokepoint file is **untouched** and remains the ONLY enforcement: every
probe still goes through `fetch.http_get`, whose `assert_url_allowed` runs on
every call regardless of what the data file says — the data can never widen
the network surface, only name paths within it. Two laws pin the contract in
`tools/tests/test_ci_parity.py`: every data host must be on the chokepoint's
allowlist, every allowlisted host must have a path (completeness — a gap is
its own visible row in the tool's output, never a silent skip), and the
probes module holds no URL literals of its own.

## T1/T2/T3/T10 — the identity subsystem lands (xr-core 420d854, pair-bumped)

Six xr-core commits (85e4a2a core → 23e3acb templates → 2b5a576 binding →
70a793e attribution → e52bea2 host → 420d854 fleet-timebox fuzz), all with
green `make test` suites under `-std=c++20 -Wall -Wextra -Werror
-D_FORTIFY_SOURCE=2`, pair-bumped same-day in DEPS (the cross-repo-pin law).

Decisions recorded (why, not just what):

* **Two host surfaces, one binary.** The frozen mojom v1 surface
  ({method,args} JSON) keeps the P5 fake envelope and replays
  BYTE-IDENTICALLY against fakes/identity.py — verified for all 15 corpus
  cases before the corpus was committed. The P14 living surface
  (provision/templates/ceremony/scheduler/binding/attribution) ships as
  SUBCOMMANDS (the policy_host precedent), because the alternative — a
  second `method ==` table — would demand a Python fake speaking the new
  surface, i.e. a post-freeze amendment of a contract we did not need to
  touch. The living surface is covered by the C++ suite +
  tools/tests/test_p14_identity.py and recorded as data in
  tools/parity/manifest.json (`living_surface` field): accounted for,
  never silently omitted.
* **The frozen table's 40-char third entry** (`…00000000000ef`) is a quirk
  frozen with the v1 fixtures: the shape law accepts 39 AND 40, the entropy
  mint always produces the canonical 39, and the quirk is documented at the
  constant (mint.h). A v2 amendment would normalize; none is smuggled in.
* **mode_lint:** /identity/ carries the frozen mojom grade field
  (kStandard/kFortress wire spellings). Rather than dodge the lint, the
  exemption is in xr-core/policy/mode_lint.cfg with the full rationale
  (grade is DATA the resolver consumes; no tier decisions in identity) —
  S0 review surface, the documented path the lint itself prescribes.
* **The hex-encoding limit, honestly stated:** LooksOpaque rejects literal
  probe embeds (the name-in-domain bug); a hex-ENCODED name is
  shape-indistinguishable and undetectable by containment. The LAW that
  actually prevents name-derived domains is the mint's purity (sha256 of
  caller entropy only) + the host's entropy duty — test_mint documents
  this rather than pretending a checker could catch every encoding.
* **Fuzz oracle obeys the fleet timebox law** (XR_FUZZ_SECONDS/XR_FUZZ_SEED,
  the themes shape): ~565k ops/s, 9.6M invariant checks in a 3 s smoke,
  0 violations across seeds. The invariants are checked CONTINUOUSLY
  (mint opacity, purge-verify, no-resurrect, never-auto-switch, ceremony
  completeness, attribution sum), not just at exit.

The gate found real things during this work (recorded so the next agent
does not re-learn them): creating a host mid-gate reddens
host_protocol_check + parity_completeness by DESIGN (the P11-T0-a law —
write the protocol doc in the same commit as the host); the sibling tree
must be CLEAN and AT THE PIN for any xr-browser gate run (stage new-core
work outside the tree while gating P0 items); mode_lint scans xr-core
tests too (tier tokens in test assertions need the exemption, like
shield/tests before us).

## P14-T8/T5/T6/T9 + P0-4 — the second landing set (216cdda lineage)

**P0-4, the census verdict.** The clean-clone census at 6530cb1a ran 156
lanes: 154 PASS, 2 FAIL, one root cause — `tools/run_checks.sh` and
`tools/run_negatives.sh` sat at index-100644 while `governance.yml`
executes them DIRECTLY (on a runner: exit 126, the class that kept the
governance lane red for three commits in P13). Fix is mode-only
(d15769c, same blob hashes): `git update-index --chmod=+x`. Lesson
recorded before, now re-learned as a LAW: **the on-disk mode must match
the index too** — the negatives battery mirrors the WORKING TREE, so a
correct index with wrong disk bits reddened the interpreted-exemption
control (`bash <path>` must pass for a 644 file). After `chmod 755` on
disk, disk == index == workflow expectation.

**The disk-full impostor.** Mid-run, 16 pytest lanes failed at once with
write errors — the census and the negatives battery had filled the 993 MiB
/tmp tmpfs (759 MiB of pytest-of-user fixtures). Symptom looked like a
mass regression; `df` said otherwise. Lesson: when MANY lanes fail
simultaneously with OSError/[Errno 28], check space FIRST; the census
transcript is worth keeping in evidence/P14/logs/ precisely because it
also documents the environment's limits.

**T8, the session store.** The contract (core/session.h): Snapshot drops
disposable-bound tabs AND reports the drop (never silent); RestoreSession
refuses any tab naming a non-live identity — kMalformedInput, tab id in
the error, "never defaulting" — so C-14's failure mode (restore falls
back to the default partition and silently merges identities) is
unrepresentable in the core. A disposable inside a session file is tamper,
never restorable. The chaos test's first draft destroyed the SAME
disposable at every kill-point and failed its own verification — the
second destroy is refused by design (no-resurrect). The honest shape is
the real crash loop: provision a FRESH disposable per cycle, bind tab 6
to it, snapshot, destroy, restore, assert its tab never comes back.
345 checks across seeds 20260910/7/424242.

**T5/T6/security-req-2, the identity matrix cells.** Three new fake-mode
mechanisms drive the identity HOST and the chaos SUITE (not the P6
resolver fake): disposable-zero-residue (clean close verified AND the
planted cookie jar fails destroy), identity-derivation-probe (six probes
per pair: partition name / URL / title / log line / a real vid /
partner-name — no source embedded, opaque shape only),
session-restore-no-bleed (the suite is the assertion). Two lessons: (a)
the runner grew past the 380-line size law mid-edit — split by
responsibility into tools/identity_iso_cells.py, the P13 precedent;
(b) a WIRING bug the count exposed: `run_identity_cells` was imported
but never CALLED — the run still passed with the OLD 30 cells (a
plausible number!). A new lane that "passes" at the old count is the
quietest failure shape there is; grep the new mechanism id in the
generated record before believing a green run.

**The DIRTY-SIBLING law, twice.** In-place `make` in xr-core/identity/
tests leaves build/ in the sibling and every pin-faithful gate (coverage,
csp, a11y, rtl, panel lanes) correctly refuses to read it. Two fixes:
the matrix runner and the pytest host fixture both build OUT-OF-TREE
(`BUILD=` override into xr-browser/work/scratch), and the Makefile now
accepts absolute BUILD paths (the run recipe's `./$(BUILD)/` prefix broke
them — a slash-bearing path needs no `./`). Rule for everything forward:
**nothing this repo runs may write into the sibling.**

**T9, the census closes honestly.** The closure table has one row per
C-id with a status from a closed vocabulary — closed-core (C-14 only),
matrix-covered (C-11's soft-reuse half), exception-documented (C-12
favicon, §1.13), open-browser (the rest, each naming its method). The
lint ENFORCES it: missing row, invented status, ghost artifact,
placeholder method, and closed-core-without-the-../xr-core-law all
redden (six negatives in tools/negatives/p14_t9.sh, N=215 gate green).
The fixture lesson: an earlier negative owns `$NEG_TMP/xr-core` as a real
directory (p3_p4's patch fixtures), so a SHARED sibling symlink lands
inside it and stops resolving — every fixture gets its own private
`census-<name>/root + ../xr-core` layout.

**T6/T7 homes.** The FS-diff harness (build/spike/fsdiff.py, synthetic-
tree tests) and the manager-page method (data cores real: attribution 19
checks, purge-verified storage, permission overlay counts; the page
itself NOT-RUN with method) now live in docs/qa/browser-harness.md —
the not_done_by_design rows point there, so no claim floats without a
home. Evidence rows for T0–T10 are set to their honest statuses
(VERIFIED only where the row's own DoD text is satisfiable in this
tree; NOT-RUN where the browser is the subject).

## The full gate at 4ddcb21 — one red lane, and it is the honest one

**Result:** keep-going at 4ddcb21 = 205 lane PASS lines, ONE red:
`check-pin-alive` (DEPS 7d70013 not fetchable from origin — the xr-core
commits are local until the human pushes; the lane is fail-closed BY
DESIGN and no bypass was attempted). ci-parity printed PARTIAL with 4
CI-stricter lanes (down from 5 — entry-point modes went green here after
d15769c). Transcript: evidence/P14/logs/p14-full-gate-4ddcb21-keepgoing.txt.

**Three environment lessons this gate run cost (all infrastructure, none
code):**

1. **The tmpfs ceiling.** The 993 MiB /tmp is enough for ONE gate run's
   pytest lane ONLY when it starts pristine. Leftover pytest-of-user
   fixtures from earlier runs (880 MiB) made the lane die with ENOSPC in
   a shape that looks exactly like a 16-test regression. Check `df /tmp`
   before believing a mass pytest failure.
2. **Never point the gate's TMPDIR at the big disk unconditionally.**
   One pytest session's retained fixtures measured ~20 GiB — on /tmp the
   tmpfs cap hid that; on the root disk it filled 20 GiB and killed git
   itself (`index.lock write error. Out of diskspace`). The census
   configuration (default TMPDIR, pristine /tmp) is the proven one.
3. **Never delete a live process's temp tree.** Clearing
   /tmp/pytest-of-user while the gate was mid-run turned 1 real red lane
   into 166 — every later lane's scratch died. Clean BEFORE, never
   DURING.

**The gate found four real defects on the way (all fixed in 4ddcb21's
lineage):** the identity suite lane was never recorded in ci-lanes.json
(the census's own lesson, re-taught); the fuzz fleet needed the in-tree
test_fuzz binary while building it dirtied the sibling — solved properly
by gitignoring identity/tests/build/ like every other core, not by
building and hiding; the identity core had no mutation score — FULL
matrix run and recorded (199/199 killed, deny-guard 19/19, zero
survivors); and mint.cc reached across cores for sha256 — now the alias
shim like its siblings (ADR-0043). The mojom_fuzz_gen "failure" was the
OOM killer under tmpfs pressure; re-ran clean.

## The fleet OOM postmortem — two append-only histories, one law (9ee4952)

**The find.** The first bare-gate run at the pushed 818f379 failed its
LAST lane: `FAIL: identity-core rc=-9` — the OOM killer. The census
(keep-going, same tree, same clone) had passed the same lane an hour
earlier, so the first reads were "environment flake"; the standing
re-run with clean /tmp passed, and the full-fleet standalone failed
AGAIN. dmesg gave the fact no log could: `test_fuzz invoked oom-killer`,
anon-rss 1.16 GB, oom_score_adj 100 — the fuzz binary itself was both
the allocator and the victim.

**Two measurement traps, recorded so nobody repeats them:**
1. /proc/<pid> sampling of a backgrounded env-prefixed command read the
   SHELL WRAPPER's status, not the binary's — "flat 1.6 MB" for a
   process ps showed at 1 GB+. `ps -C <comm>` is the honest instrument.
2. The OOM was intermittent because the peak (~1.1-1.2 GB) only crosses
   the 2 GB line when tmpfs holds pytest fixtures (~450 MB of unswappable
   shmem). "Passes on a clean /tmp" is not "bounded" — it is "marginal".

**The math that made it a must-fix, not a flake:** the fleet evidence
timebox law is 600 s. At the measured ~18 MB/s of audit growth, a 600 s
campaign needs >12 GB — it would OOM ANY runner, not just this sandbox.
The gate lane was the early warning for a broken evidence campaign.

**Root cause, two of them:** BindingModel.changes_ (append-only audit;
~10M rows in 60 s of oracle ops) and Scheduler.evictions_ (one event per
user hibernate; ~250 MB per 60 s). Both are "evidence" structures with
no bound — the store itself was already bounded (live ≤ 32), so the
oracle's own comment ("bound the campaign's memory footprint") was true
for the store and false for the histories.

**The fix is contract-preserving compaction, not truncation:**
CompactAudit keeps the LATEST row per tab — exactly the fold
session::Snapshot already computes — and the suggestion log keeps its
tail; CompactEvictions keeps the newest events in order, LRU untouched.
Both drop-only (never-auto-switch cannot appear by construction),
both deterministic, both proven by new deterministic cases — the money
assertion is Snapshot BYTES before == after compaction
(test_binding 44→71; test_hibernate 56→83).

**Measured after:** 60 s / 33.8M iters and 120 s / 73M iters both FLAT
at ~43 MB RSS; the 600 s campaign runs at the same 43 MB (transcript:
evidence/P14/logs/t-fuzz-identity-600s.txt). Mutation matrix re-run at
the fix pin: 204/204 killed (the five new compaction mutants die on the
new cases), deny-guard 19/19, zero survivors — recorded in
mutation-scores.json at 9ee4952.

**The ceremony this forced (all re-run, nothing waved through):** DEPS
re-bump to 9ee4952; mutation-freshness PASS at the new pin; the host
corpus byte-parity re-proven (38 pytest lanes); the full local gate; and
the P0-4 census triplet (clean-clone census + bare + CI-range) re-run at
the final pushed pin — the earlier 818f379 census remains valid for the
tree it ran at; the phase close cites the final one.
