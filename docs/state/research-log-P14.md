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
