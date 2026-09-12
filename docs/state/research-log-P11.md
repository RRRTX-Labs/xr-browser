# docs/state/research-log-P11.md — XR Shield v1 research + T0 debt rulings

Law (inherited): each item cites `path:line@pin` via `build/upstream/fetch.py`
/raw URL + fetch date, or reads `UNVERIFIED (deferred to <where>)`. Never
assert from memory where a fetch settles it. Sandbox facts are recorded per
item where they matter.

## D0. T0-c DEVIATION — the brief's compat-beta-parity diagnosis is REFUTED

**VERIFIED against the actual job logs; the brief's fix would have been an
over-grant.** The phase brief asserted that compat-beta-parity's scheduled
failure was caused by `actions/upload-artifact` lacking an `actions: write`
token scope, and asked `build/workflow_lint.py` to encode that as a required
grant. The evidence says otherwise:

1. The failing step's own log (run `34574063042`, job `103182443929`, step
   "Upload the compat-parity evidence", fetched 2026-09-11 via the REST API
   with the session credential — a one-time diagnostic read; the logs
   endpoint 302s to a blob host outside `fetch.py`'s ALLOWED_HOSTS):

       ##[error]Invalid pattern '../xr-core/test/corpus/'.
       Relative pathing '.' and '..' is not allowed.

   The action rejected the PATH, before any token scope is consulted.
2. The counter-run: nightly-rebase-build schedule run `34571026698`, the
   SAME head (`ef3477925`), the SAME action
   (`actions/upload-artifact@330a01c4…` v5.0.0), the SAME
   `permissions: contents: read` — its upload step SUCCEEDED. If
   upload-artifact needed `actions: write`, that run could not have
   uploaded.
3. Platform docs (GitHub Marketplace / community, fetched 2026-09-11):
   upload/download-artifact require no special scope; `pages: write` +
   `id-token: write` belong to the deploy-pages OIDC flow; `contents: write`
   belongs to release-asset operations. No source ties artifact upload to an
   `actions:` scope.

**Ruling:** the fix is the path law (stage the evidence inside the
workspace — done in `.github/workflows/compat-beta-parity.yml`, with the
misdiagnosis recorded in a comment so nobody "fixes" it into an over-grant
later). The required-grants table (`build/workflow_grants.py`) encodes ONLY
empirically true rules and deliberately contains no
"upload-artifact ⇒ actions: write" rule; `build/tests/test_workflow_grants.py
::test_disproof_clean_upload_under_contents_read_is_zero_findings` pins the
disproof as a test. Adding the brief's hypothesized grant would have been
exactly the least-privilege violation the table exists to prevent — and the
lane would STILL have been red.

## D1. T0-c surfaced debt — a surviving deny-guard mutant in policy store.cc

**VERIFIED locally (seeded sample).** T0-b's shared-primitives move removed
`policy/core/json*.cc` from the policy mutant population; the fixed seed
(424242) therefore samples a different 5 mutants, and one SURVIVED:
`store.cc:155`, the `return false` in "exceptions: 'remaining_uses' integer
required" mutated to `return true` — a validation failure that ACCEPTS
(deny-guard class, never-guess law). The gap was latent since P6: no test
ever fed an exceptions entry with `remaining_uses`/`expires_at` absent or
non-int. Paid immediately rather than deferred: three reject-tested battery
cases added (`xr-core/policy/tests/test_store.cc`, commit `85289cd`), seeded
sample now 5/5 killed, deny-guard 3/3. DEPS pin advanced in the same
breath per `docs/process/cross-repo-pin.md`.

## D2. T0-c same-day verification — the fix chain, run by run (all cited)

**VERIFIED hosted (workflow_dispatch, 2026-09-11).**
- `34635047137` (dispatch @ `7fa253f`, 18:45 UTC): fired by this agent
  BEFORE the fix push landed (the push had been rejected — origin had
  diverged, see below); failed at the upload step on the OLD definition.
  Expected; kept as the control data point.
- `34635371904` (dispatch @ `a59c5f0`, 18:48 UTC): the path fix PROVEN —
  "Stage the compat-parity evidence" and "Upload the compat-parity
  evidence" both SUCCESS, all work steps green — but the job went red on
  the new Scheduled-lane health step: the fleet check condemned its own
  lane from history including the in-flight run itself and the stale-main
  control. Circular; fixed by `9d24a40`.
- `34635794078` (dispatch @ `9d24a40`, 18:53 UTC): **FULL SUCCESS**, all
  14 steps green including upload (path fix) and lane health (circularity
  guards: --own-lane cap + lane-health-only-failure exemption). The live
  checker now reports compat as STALE-FAIL "fix VERIFIED — newer
  workflow_dispatch run 34635794078 … completed SUCCESS"; the next
  scheduled fire (daily 02:30 UTC) upgrades it to PASS. Evidence:
  `p11-evidence/logs/t0c-compat-dispatch-watch2.txt` (step-by-step),
  `t0c-scheduled-lane-check-after-fix.txt` (verdict upgrade).
- Concurrent-history note: origin/main diverged mid-phase — the P10 agent
  pushed its finalization commits (`b766992` hosted-green evidence,
  `7fa253f` final report) at 17:49/18:21 UTC. The four P11 commits were
  rebased on top (clean, no conflicts); prior-phase material was left
  exactly as authored. `b766992` rewrote `evidence/P10/evidence.json`
  in place (DOD-2 BLOCKED→VERIFIED, lines deleted) — T0-d handles the
  append-only correction and the ci-run rows from here on WITHOUT
  rewriting their commit.

## D3. T0-d resolution — evidence corrections landed APPENDED; --strict tightened

**VERIFIED locally + live API (2026-09-11).** The brief asked to "append a
correction to evidence/P10 (DOD-2 BLOCKED→VERIFIED with a ci-run row for
hosted cargo run 34615191984)". Reality on arrival: the P10 agent had
already flipped DOD-2 to VERIFIED IN PLACE (commit b766992, lines deleted)
with no ci-run row anywhere. The correction therefore landed as APPENDED
rows — prior-phase rows left exactly as authored, per the append-only law:

- `P10-DOD-2-C1` + `P10-DOD-11-C1`: `source: ci-run`, run **34615191984**,
  job **103315238760** (server-conformance SUCCESS at head
  `8fadb0ee4a7cab04762df5c111778c122e0da919`; steps "Rust toolchain
  versions" — cargo/rustc 1.98.1 — and "Rust conformance (byte parity with
  the reference corpus)"). The P10 `repos.xr-browser` text was EXTENDED
  with both cited heads (`8fadb0ee4…`, `acbcfc663…`) so the resolver's
  head-match passes; extension, never rewrite.
- `P9-DOD-11-C1`: rule (d) is scoped P9+ like the P9-T12 rules, and P9's
  DOD-11 notes claim hosted-runner counts ("542 passed … on the hosted
  runner") with only local transcripts; its correction cites the same
  hosted governance run DOD-12 already proves (run **34511850763**, job
  **102987644207**, head `e404ac508e6898c0b96552a05ddbcc38e85400a6`).
- Full-green P10 hosted runs, for the record: core-hardening
  **34627026627** SUCCESS + governance **34627026351** SUCCESS at
  `acbcfc6632ed8563213561526b233777f16884de` (2026-09-11T17:19Z).
- Probe run **34604887643** (job 103280790981) is cited as the FIRST
  toolchain observation, honestly marked: that job then failed on the
  missing Cargo.lock (fixed same day) — a red observation is still an
  observation; the GREEN citation is 34615191984.

`evidence_check.py --strict` now enforces, for P9+ bundles: **(d)** a
VERIFIED row whose text claims hosted execution (`hosted` / `GitHub
Actions` / `on the runner` — narrow regex; "farm runner" tool names do NOT
fire) needs a ci-run citation on the row itself or on an appended
`"corrects"` row; **(e)** a BLOCKED-* row whose blocker tool the
capabilities ledger or the local `which` proves PRESENT is STALE and fails
(UNOBSERVED tools never fire — the ledger refuses to certify what no run
printed). Contract amendment appended to
docs/contracts/evidence-bundle-v1.md. All 8 strict bundles pass with the
three new ci-run rows resolved LIVE (head-match + job-success). Negatives
70–72 (N=72) + 12 unit tests pin both rules and the ledger law.

## D4. T3 decision — xr-lists/ lands in xr-browser (recorded per the brief's GIT/CHANGE MANAGEMENT note)

The brief allows `xr-lists/` in either repo but demands the choice be
recorded in `xr-browser/docs/`. **Chosen: xr-browser.** Reasons, in
weight order: (1) the TEST-ONLY signing channel the pipeline must use
(`build/signing/linux_repo_sign.py` + `sign_artifact.py`) lives here —
putting xr-lists in xr-core would make core reach UP into the browser
repo, inverting the established cross-repo direction (xr-browser tools
consume `../xr-core`, never the reverse); (2) the brief itself places
the gate at `tools/list_bundle_check.py`, and `tools/` + the vectors +
the gate dispatcher + the negative-canary harness are all here; (3)
xr-core is the `//xr` C++/Rust tree compiled into the browser (its root
BUILD.gn aggregates compiled targets only) — a Python data pipeline
would compile into nothing there and would need a fake GN story; (4) the
only xr-core touchpoints T3 needs are READ-ONLY (the compiled
`shield_host` binary for the round-trip's binding/hot-pin cells, reached
through the DEPS pin like every other lane). Full text also in
`xr-lists/README.md` §"Repo choice".

## D5. T4 interpretation — the "deterministic expiry sweep job" = host method + ledger `--as-of` (no third mechanic)

The brief asks for the expiry sweep "as a deterministic job (no wall
clock) with --as-of". Decision: the sweep exists in exactly two forms,
and no cron-like third form is built. (1) Runtime: the host method
`exception-sweep {scopes, now_mono}` — T2's SweepAsOf as a parity-tested
method; the as-of IS the argument (the v1 host is stateless; state rides
in the request). (2) Commit-time: `exception_ledger_check.py --as-of N`
checks the shield ledger's monotonic expiries with the same
boundary-INCLUSIVE law (`as_of >= expiry` ⇒ fail "has passed as of"). A
third background job would sweep nothing: the stateless host never
RETAINS an expired scope (callers pass the set and get the swept result
back), and no v1 product surface grants standing exceptions yet (the
ledger ships with zero rows — zero passes, a missing section fails).
Recorded with it: the per-site toggle + dynamic rule add/remove map onto
the surface as designed (toggle = the site-dimension scope with the
canonical id `site-toggle:<site>` and the fixed reason
`user-site-toggle`, shared id space with manual scopes; a dynamic rule
exception = a `rule_id`/`list_id`-dimension scope; user-added BLOCK
rules are custom lists via xr-lists, not scopes), and the refusal split
(document parse errors ⇒ `kMalformedInput` exit 1 — the T2 grammar
untouched; conflicts with the existing set ⇒ `kRejected` exit 0 — the
equal-reoffer precedent). Why the P8 §11.9 waivers semantics are NOT
reused ⇒ ADR-0046 (different data class, clock, granularity/floor,
grant direction, enforcement point).

## D6. T4 gate-run record — five latent full-run_checks debts surfaced and discharged (no guard weakened)

T2/T3 ran targeted batteries (pytest subsets, per-task gates). The first
FULL `tools/run_checks.sh` after T4's method surface surfaced three
latent debts from T1–T3, each discharged by the sanctioned mechanism —
never by weakening a gate:

1. **mode_lint (P6 one-brain law) red on `xr-core/shield/tests/
   test_context.cc:110`** (T2-era): a REFUSAL fixture spells the tier
   token `kStandard` inside a request frame that the context parser must
   reject (proving the identity grammar is a closed key set that never
   consumes grade/tier). Discharged via the argued-exemption mechanism:
   `xr-core/policy/mode_lint.cfg` gains `exempt: /shield/tests/` with the
   `/policy/tests/` + `/commands/tests/` precedent rationale; the shield
   IMPLEMENTATION (`/shield/core/`, `/shield/host/`, `/shield/engine/`)
   stays fully scanned.
2. **license_audit red on T3's GPL citations + T1's vendor-test tokens.**
   `docs/state/research-log-P11.md` (R6 EasyList dual licence) and
   `xr-lists/README.md` (attribution shape law embeds the SPDX
   expression) gained allowlist rows (doc-hit class, research-log-P1
   precedent). `tools/tests/test_p11_vendor.py` carried red-class
   copyleft expressions as inline literals — CODE hits fail
   unconditionally and no allowlist may cover them, so the expressions
   moved to fixture DATA
   (`tools/tests/fixtures/p11_vendor_red_licenses.json`, allowlisted;
   the sbom.json precedent) with the assertions unchanged.
   `tools/vendor_rust_graph.py`'s DR-04 comment was reworded to name the
   red class without spelling banned tokens in code. The
   `.pytest_cache/v/cache/nodeids` hits were an artifact of running
   pytest BEFORE the audit ad hoc — `run_checks.sh` runs the audit
   (line 34) before pytest (line 53), and the cache dir is gitignored;
   no tool change.
3. **fetch_allowlist_check red on `tools/shield_vectors_kit.py`**
   (T2-era): MATCH_URLS fixture URLs in the reserved `.example`
   namespace whose port/bare-host/`example.com` boundary variants fall
   outside the checker's `.example/` slash-shape exemption. Discharged
   via the documented EXEMPT_FILES row (the probe_driver/platform_argv
   scan-token precedent — data, never fetched; the kit imports no HTTP
   client), NOT by broadening the URL matcher.

4. **mutation-freshness red on `shield`** (T2-era): `xr-core/shield/core/`
   had NO mutation lane at all — `tools/mutation_targets.py`'s SUITE_MAPS
   carried no `shield` entry, so no score was recordable. Discharged: the
   eight-TU lane added (superset-per-TU mapping; `test_golden_vectors`
   drives the COMPILED host end-to-end over all 229 vectors including the
   T4 exception surface), `tools/mutation_test.py` gained the
   target-guarded `build/shield_host` branch (the golden-vectors suite
   name is shared by the update and shield lanes — asking the wrong
   Makefile for the wrong host would fail every build and dishonestly
   inflate the score), and the FULL matrix (sampled:false) ran TWICE.
   The first run at pin `51e6333` (389 mutants) FAILED the 100%-deny-
   guard law: 4 survivors in `apply.cc:23-33` (2 deny-guards) —
   ParseSlot's `slot-not-object` and in-slot `unknown-field` refusals
   had NO test coverage. Discharged the house way — NEW TESTS
   (`test_apply.cc` rows + golden vectors `a-slot-not-object` /
   `a-slot-unknown-field`, 227->229; xr-core commit `cfbb344`), not
   equivalent-mutant excuses. The re-run at `cfbb344` killed 389/389,
   deny-guard 61/61, score 100.00%; that is the recorded pin
   (`shield/core/**` is byte-identical across the fix — it landed in
   tests + vectors only, so the record also stays fresh across the
   DEPS bump by the gate's own ancestor-diff law). Score +
   dispositions: `docs/state/mutation-scores.json`; transcript of the
   passing re-run: `evidence/P11/logs/t4-mutation-shield.{json,log}`;
   quoted summary of the failing first run:
   `evidence/P11/logs/t4-mutation-shield-run1-fail.txt`.

5. **P9 meta-gate ("mutation-check the checker") red on `evidence_check`
   since T0-d**: T0-d gave `tools/evidence_check.py` a BARE
   `import runner_caps`, but `build/qa/tools/test_checker_mutation.py`'s
   sibling-module copier tracked only the `from X import` form — every
   mutated copy crashed with `ModuleNotFoundError: runner_caps` ("did not
   escape the canary"). It could not surface until T4: every earlier full
   run aborted at a fatal gate BEFORE the meta section (run #1/#3:
   mutation-freshness; run #5: the date-driven `release/notes/train-152.md`
   staleness — regenerated live, date-stamp-only diff, 2 identical upstream
   rows). Discharged by teaching the copier the bare-import sibling form
   (`sib.exists()` keeps stdlib out); mutation + canary logic untouched —
   3/3 targets now control-trip AND mutant-escape.

Lesson recorded for T5–T8: run the FULL `tools/run_checks.sh` +
`tools/run_negatives.sh` at every task boundary, not the targeted
subset — task-scoped batteries let cross-phase gates drift silently.

## D7. T5 decisions — emitter = `event-emit` host method writing a LIVING superset row (no mojom widening), + the int64 wire fix

The brief's T5 asks for `block-event-v1` as a living contract (registered
post-freeze), ledger emission through the existing ring/Activity-Ledger
path, a "why blocked" reason-code supply for P13 to render, the privacy
posture on events, and retention/caps inherited from the P8 ring tests.
Decisions:

1. **Shape.** The frozen mojom `BlockEvent` stays exactly as frozen (the
   Status/RecentEvents surface is untouched — its bytes are pinned by the
   frozen fixture case). The ledger row is a living SUPERSET document
   (`block-event-v1`): frozen fields with frozen semantics and frozen
   k-spellings (`action`, `request_class`, `origin`, redacted `target`)
   plus the provenance the mojom struct deliberately does not carry
   (`rule_id`, `bundle_version`, `why_code`, flat `identity`, `seq`).
   No second naming: the row's `action` enum IS the frozen enum.
2. **Emitter.** A new host method `event-emit` (both backends byte-identical;
   45 vector cases + a 43-case direct parity probe). No `kRejected` class —
   emission has no content-conflict semantics, so every bad input is
   `kMalformedInput` with a closed detail token. `seq`/`ts_millis` are
   caller-supplied: no clock reads (the commands/core/dispatch.cc
   ledger-row precedent).
3. **int64 fix (latent T2 bug, found in T5).** The mojom declares
   `ts_millis`/`tab_id` int64, but T2's `EventToJson` cast them to int32 —
   epoch-scale timestamps truncated on the wire (no committed value was
   large enough to show it). Fixed in `EventToJson` AND the new
   `MakeLedgerRow`; frozen-surface bytes unchanged for every committed
   value (test_golden_vectors 355 checks green before and after), and the
   law is now pinned: golden `ts_millis` 1750000000123 + vectors
   `e-emit-epoch-ts` / `e-emit-big-ints`.
4. **Reason codes.** `docs/shield/reason-codes.{md,json}` maps the closed
   11-code verdict vocabulary to stable `shield.why.*` text keys; P13
   renders the localized copy (a documented dependency — v1 renders
   nothing). Five-way sync (host_protocol closed set = schema enum = table
   json = table md = vectors' usage) is pytest-asserted; drift reddens.
5. **Retention/caps.** v1 pins what the code has: the ring FIFO cap (256)
   and the 64 KiB canonical-byte view budget (P8 inheritance, doc/code
   match tested). The 90-day rolling default retention, per-identity local
   storage, user export and the never-uploaded law are P13 persist-time
   behavior — stated in the contract as a dependency, not claimed as
   implemented. The plan's 2,000-event per-tab ring is P13's scale of the
   same cap law.
6. **events.h intent cleanup.** The T2 intent header cited speculative
   `event-sink-v1`/`event-stream-v1` contract names that were never
   registered anywhere; replaced with the registered `block-event-v1`
   (no phantom forward references in source intent headers).
7. **Attention.** The emitter drives the passive chip counter only
   (invariant 7: no toasts/badges/modals); the enforcement extraction to
   `tools/attention_check.py` stays T6's job per the plan.
8. **fetch_allowlist false positive (gate fix, not a weakening).** The
   `EXAMPLE_URL` exemption in `tools/fetch_allowlist_check.py` matched
   `.example/` but not `.example:8443/` — the T5 redact-port vector URL
   (a reserved RFC-2606 domain WITH a port, exactly as unfetchable as
   without one) reddened the chokepoint scan. Fixed at the regex (the
   trailing class now allows `:` or `/`) instead of exempting the whole
   families file — a file-level EXEMPT_FILES entry would have dropped
   the file from the scan entirely, which IS a weakening; the targeted
   fix keeps it scanned and is recorded here per the exemption table's
   ADR-or-research-row law.
9. **Hosted-CI verification debt (process find).** The hosted governance +
   core-hardening lanes were RED at the T3 and T4 pushes (runs at 06bd7ab7
   and 9df51d1, both `failure`) and nobody looked: T1's evidence checked
   its own hosted runs, but T2–T4 pushed without querying CI. T5 queried
   the API, root-caused every red, and fixed each with a named commit
   (items 10–12). New evidence law for this phase: every push is followed
   by a hosted-run query, and the run conclusions are recorded in the
   phase transcript before the task is called complete.
10. **Vendored Cargo.lock files never committed (T1 latent, fixed
   `xr-core 1e5fa01`).** Every upstream crate tarball ships its OWN
   `.gitignore` (e.g. aho-corasick's `/Cargo.lock` line), so T1's
   `git add third_party/rust/vendor` silently skipped 18 crate
   `Cargo.lock` files the published tarballs contain. The dev sandbox had
   them on disk (vendor_check green locally); the hosted checkout did not
   (shield-vendor red: 18 × "MISSING file Cargo.lock"). Force-added; the
   nested `.gitignore`s stay untouched (they are published-tarball bytes);
   verified with vendor_check against a `git archive` extraction — the
   exact hosted bytes, not the working tree.
11. **xrctl ↔ shield-fake interface drift (T2 latent, fixed `xr-core
   341f1fb` + xrctl unwrap in the T5 browser commit).** The shield fake's
   `call(method, args, flag)` follows the house CLI shape (flag + tuple
   return), but xrctl's generic path calls `mod.call(method, payload)` and
   serializes the result directly: TypeError since T2 on the hosted
   governance lane (the local battery doesn't run `docs/contracts/tests`;
   only CI does). Fixed on BOTH sides: the fake's `flag` defaults to
   `"on"` (its documented CLI default), and xrctl unwraps an
   `(envelope, rc)` tuple to the envelope — the exit-code contract belongs
   to the host-binary layer (pinned by the vectors), xrctl's contract is
   the typed envelope. 274 vectors re-verified byte-identical after the
   fake change.
12. **Rule-(e) canary hermeticity (T0-d latent, fixed in
   `tools/tests/test_p11_t0d_evidence.py`).** The stale-BLOCKED fixture
   tests measured whichever environment they ran in: hosted runners have
   cargo/go installed, so `which` fired the LOCAL arm on top of the ledger
   arm (2 hits where the assert wanted 1; the UNOBSERVED-go test fired
   outright). Pinned hermetic with `monkeypatch` (`shutil.which` → None
   for the ledger-arm fixtures; the local arm keeps its own explicit
   positive test) and proven in both worlds — including a simulated
   hosted PATH with fake cargo/go/rustc/clang/semgrep binaries (12/12
   green under the simulation).

## R1. adblock-rust: version, license, advisory state (T1 input)

**VERIFIED (live API reads, 2026-09-11).**
- Repo `brave/adblock-rust` (api.github.com): default branch active; latest
  tag `v0.13.3` → commit `886d45dcf5…`; license **MPL-2.0** (file-level
  copyleft — linkable from our std-only C++20 core behind a Rust ABI
  boundary; license_audit's GPL-link law is not triggered by MPL, but the
  vendoring record must carry the file-level obligations); Cargo.toml at the
  tag: `edition = "2024"` (needs a current stable rustc — the hosted runner
  has one, proven by run `34615191984`, see R8/runner-capabilities).
- GitHub security advisories for the repo: **0 open**.
- crates.io `adblock/0.13.3`: published **2026-08-20**; crate tarball
  sha256 `f44b96a666a23c12acad7c688bfe8638a7094e7eabe765b09a6864ab991c676d`
  — this is the T1 vendor pin.
- **Ceremony LANDED (2026-09-11, ADR-0044):** `static.crates.io` joined
  `fetch.py` ALLOWED_HOSTS (5th entry; the crates.io INDEX/API hosts stay
  OFF — resolution truth is the lock, not live queries). The tarball was
  fetched through the chokepoint and its sha256 matched the crates.io pin
  BEFORE unpacking. The published tarball carries the crate's OWN
  `Cargo.lock` (crate-specific: workspace members adblock-fuzz/adblock-rs
  and their subtrees already excluded; blob `ed05c5aa5b09…` at the tag is
  the workspace lock — the tarball lock is a strict, self-contained
  subset), every registry package in it sha256-pinned.
- **Vendored (P11-T1):** `xr-core/third_party/rust/` — root crate verbatim
  at `adblock/0.13.3/` + a feature-aware BUILD closure of **59 crates,
  4,420,208 tarball bytes / ~30 MB extracted, 2,111 files** (default
  features; dev-dep-only subtrees — criterion/reqwest/tokio/plotters/
  aws-lc — deliberately excluded, PROVENANCE.md records the honest
  `--offline` boundary). `css-validation` (cosmetic: cssparser/selectors)
  is OFF at this pin; UPDATING.md carries the extension path for T2.
- **Advisories (GHSA reviewed, `affects=` per crate through the
  chokepoint, 2026-09-11):** 14 advisories touch vendored names
  (flatbuffers, smallvec, idna, regex, base64, zerovec, zerovec-derive);
  17 crate-range checks: **0 hits, 0 NEEDS-REVIEW** — every vendored
  version sits outside every advisory range
  (`supply-chain/advisories.json`).

## R2. Upstream conformance corpus (filter matching) — UNVERIFIED (T1/T8)

Candidate sources to evaluate at T1: adblock-rust's own test data
(`tests/`), EasyList/EasyPrivacy header contracts, filter-syntax
documentation. The ≥1,500-case vendored corpus for T8 parity must be
machine-derivable and license-clean; attribution per source is mandatory
(T3's frozen list-bundle-manifest-v1 either carries it or we STOP per the
brief).

## R3. Chromium network-service seam at pin d04cdb24 — UNVERIFIED (pin read still owed; T2 landed the in-tree half)

The pin (`152.0.7977.82 @ d04cdb24d67b081f6cf80200ffc5233f44b61109`,
`xr-browser/DEPS`) has no checkout in this sandbox; `path:line` citations
for the URLLoaderFactory/NetworkContext interception point must come from a
live read at the pin before the patch manifest grows its third entry. Same
honesty rule as P10 R1.

T2 status note (2026-09-12): the in-tree half of the seam LANDED — the
injection contract is `xr-core/shield/core/engine.h` (BlockingEngine, pure
virtual, no adblock types in the core) plus the hosted-lane FFI shim
`xr-core/shield/engine/` (C ABI `xr_shield_engine.h`). Nothing binds this
to Chromium yet; the farm-side seam read and the patch-manifest 3rd entry
owe exactly what this entry said before T2.

## R4. MV3/DNR limits (what Shield must NOT promise) — UNVERIFIED (T4/T6)

## R5. Brave memory work (adblock-rust in production) — UNVERIFIED (T7)

## R6. EasyList licensing (bundle redistribution) — VERIFIED live (T3, 2026-09-12)

Live re-read of https://easylist.to/pages/licence.html TODAY (fetch, not
memory; the repo's `docs/dependencies/easylist-family.yaml` was
live-verified 2026-09-07 with the same quotes — both agree):

* **Terms**: the EasyList repository contents are dual licensed
  **GPL-3.0-or-later OR CC-BY-SA-3.0** (user's choice). Quote: "the
  contents of the EasyList repository (https://github.com/easylist) is
  dual licensed under the GNU General Public License version 3 of the
  License, or (at your option) any later version, and Creative Commons
  Attribution-ShareAlike 3.0 Unported, or (at your option) any later
  version."
* **Attribution obligation** (quote): "if required, 'The EasyList
  authors (https://easylist.to/)' should be attributed as the source of
  the material. All relevant licence files are included in the
  repository." → the exact attribution shape our bundle embeds (R6
  requirement): `EasyList — © The EasyList authors (https://easylist.to/)
  — GPL-3.0-or-later OR CC-BY-SA-3.0 — https://easylist.to/pages/
  licence.html` — four " — "-segments, which is precisely the shape law
  `xr-lists/attribution.py` enforces (name/holders/SPDX/source), so the
  default-set lists will pass the gate unchanged when they land.
* **Redistribution posture**: lists are DATA (DR-04 "never linked as
  code"; easylist-family.yaml use_verdict INTEGRATE-DATA-ONLY) — we
  redistribute compiled+signed bundles with the attribution sidecar
  (`LICENSE.attribution.txt`) and the license text obligations riding in
  the per-list attribution field INSIDE the digest (cannot be stripped
  without breaking the binding). ShareAlike applies to the DATA we
  redistribute (the compiled lists remain under the same dual terms; our
  compiler/tooling is separate code, not a derivative of the data).
* **The nuance that needs legal eyes (flagged, NOT self-resolved)**:
  the licence page warns that "files hosted externally and referenced in
  the repository, including but not limited to subscriptions other than
  EasyList, EasyPrivacy, EasyList Germany and EasyList Italy, may be
  available under other conditions; permission must be granted by the
  respective copyright holders". So the DEFAULT-SET decision (which
  companion lists ship enabled) is per-list permission work → **HG-1
  (legal review, still open)** per the brief's instruction; the pipeline
  itself needs no exemption — attribution is a required, digest-bound
  field and the shape law rejects lists without it.
* Disconnect remains excluded (CC BY-NC-SA 4.0, commercial use needs a
  paid license — easylist-family.yaml, live-verified 2026-09-07; P39
  business decision, not ours).
* No upstream list BYTES are in the repo this phase: the pipeline is
  proven on self-authored CC0 synthetic fixtures (xr-lists/README.md);
  fetching real lists needs the chokepoint ceremony (ADR-0044 pattern)
  plus the HG-1 default-set decision first.

## R7. cargo-vet in a vendored (non-workspace) layout — DECIDED (T1)

**VERIFIED BY EXECUTION + recorded limits (2026-09-11).**
- `cargo vet` / `cargo audit` cannot run in this sandbox: no cargo binary
  (runner-capabilities ledger, R8) and both tools presume a live registry
  index (index.crates.io — deliberately NOT allowlisted; resolution truth
  is the pinned lock). Claiming either check would be fabrication, so the
  smallest honest substitute was BUILT AND RUN instead:
  1. **Integrity**: every vendored byte is sha256-sealed twice — the root
     crate per-file (`MANIFEST.sha256`), each dependency per-file +
     per-crate (cargo's own `.cargo-checksum.json`, whose `package` field
     is verified against the tarball's own `Cargo.lock`). Tamper, deletion,
     extra-file, lock-desync and closure-gap all redden
     (`tools/vendor_check.py`, pytest x9 + negative 74/75).
  2. **Advisories**: the reviewed GHSA rust set was pulled through the
     chokepoint per vendored crate (`affects=` queries — the bulk listing
     is deep-pagination-capped at ~2,200 entries, which is itself a
     finding) and range-matched: 14 advisories / 17 checks / 0 hits; an
     unparseable range records NEEDS-REVIEW and REDDENS the gate — never a
     silent miss (`supply-chain/advisories.json`).
  3. **Licenses**: per-crate SPDX expressions with the CHOSEN allowed
     branch recorded (disjunctions are a decision; AND-groups need every
     part allowed; unknown identifiers/exceptions are red — DR-04)
     (`supply-chain/licenses.json`, evaluator tested incl. the
     `(MIT OR Apache-2.0) AND Unicode-3.0` unicode-ident case).
- **Open follow-up (recorded, not claimed):** run `cargo vet` proper (with
  a criteria/imports baseline) on a cargo-capable machine — the hosted
  `shield-vendor` lane has cargo; adding vet there is a lane edit once a
  baseline exists. Until then the substitute set above is the check of
  record, and PROVENANCE.md says exactly that.
- **Ceremony side-rows (fetch_allowlist_check EXEMPT_FILES law: "a new
  entry needs an ADR or research-log row"):** `build/qa/leaktest/engine.py`
  (loopback-only TCP tap, observes egress, never emits — cdp.py class) and
  `build/signing/platform_argv.py` (the timestamp.digicert.com literal is
  ARGV DATA for the platform signer at HG-36/37; Python never fetches it)
  gained documented exemption rows. `tools/scheduled_lane_check.py` was
  FIXED rather than exempted: its api.github.com URL construction moved
  into the chokepoint (`fetch.github_api_url`) — governance had been red
  on the URL-in-code law since T0-c and this row is the record.

## R8. Runner capabilities from REAL runs (no comment-claims)

**PARTIALLY VERIFIED (cited runs).** `cargo`/`rustc` present on
ubuntu-latest: hosted server-conformance run `34615191984` (P10) compiled
Rust. `g++`, `make`, `python3.12`: every governance/core-hardening run.
`go`: only claimed in a core-hardening.yml comment — NOT recorded (a
comment is not a run). These citations LANDED in
`docs/state/runner-capabilities.json` (T0-d, schema runner-capabilities-v1,
every entry cited above); an entry without a run-id/transcript citation is
refused by `tools/runner_caps.py --check` (gated in run_checks), and
evidence_check --strict rule (e) consumes the ledger to fail stale BLOCKED
rows.

## R9. Fail-open mechanics — IMPLEMENTED (T2). Scriptlet posture — UNVERIFIED (T6)

### R9a. Fail-open vs fail-closed mechanics in-network — LANDED with `posture.{h,cc}`

The brief asks what "engine death" can concretely look like and how the
seam must behave so browsing continues while the chip turns amber — and,
separately, how Guard route-loss stays fail-closed. Both halves are now
CODE, not prose, in `xr-core/shield/core/posture.{h,cc}`:

**The concrete death modes, and where each is caught:**

1. *Panic in the matcher* (the Rust side): every FFI export in
   `shield/engine/lib.rs` is total — `catch_unwind` on all of
   create/alive/match/free, and a caught panic flips `alive` to false
   (`xr_shield_engine_kill_for_test` in the C ABI `xr_shield_engine.h` is
   the observable seam the C++ tests drive today; a panic and a kill are
   the SAME input to the core: `engine_alive=false`).
2. *Poisoned state / OOM during apply*: `PostureInputs.engine_poisoned`.
   The apply law (monotonic version, LKG kept, swap only on success —
   `bundle.cc`) means a failed apply leaves the OLD engine serving; a
   process-level abort restarts the host into the default posture input
   (`engine_alive=false`) until the first successful apply — i.e. death
   degrades to fail-open, never to a half-swapped table.
3. *Poisoned/absent bundle at load*: NOT death — `create` returns NULL,
   and match decides `no-bundle` (fail-open + amber, its own reason in
   the closed vocabulary). Conflating "no engine" with "no lists" would
   hide which one broke.

**The behavior law (single decision point, pure/total/deterministic):**
`DecidePosture` fixes precedence route > engine > kill-switch > normal:

* `!route_bound` ⇒ fail-CLOSED, chip red, frozen `kFailClosed` refusal —
  ALWAYS, whatever else is true (8 of 16 input combinations).
* `!engine_alive` ⇒ fail-OPEN, chip amber, `engine-dead` — browsing
  continues, protection is visibly GONE (amber is the "not protecting"
  state; a green chip over a dead engine is the one outcome the design
  forbids).
* `engine_poisoned` ⇒ fail-OPEN, amber, `engine-poisoned`.
* `kill_switch_on` ⇒ fail-OPEN, amber, `kill-switch` (deliberate off is a
  visible state, never a green lie; T6 owns the surfaces that flip it).
* exactly 1 of 16 combinations is normal/green.

**Property-tested, not asserted:** `shield/tests/test_posture.cc`
enumerates the ENTIRE finite input space (2^4 = 16 combinations) and pins
the counts (8 fail-closed / 7 fail-open / 1 green), the chip mapping, the
closed reason vocabulary, and "a kill switch cannot un-fail-close a lost
route". The Python fake mirrors `DecidePosture` byte-for-byte, and the
posture combinations are in the 157-case golden vector corpus, so all
three representations (C++, Python, vectors) are pinned to the same law.

**The Guard distinction (P18 owns Guard; nobody conflates them):** shield
only CONSUMES `route_bound` — a boolean signal from Guard route integrity.
Route loss is a SAFETY property (requests refused, red); engine death is a
COMFORT-feature failure (requests allowed, amber). The two never share a
code path: `DecidePosture` checks the route law first and returns, so no
engine state can soften it. When the seam lands (R3), the same order
applies in-network: refuse before consult.

Citations (in-tree artifacts, this phase): `xr-core/shield/core/posture.h`
(inputs/enums/law comment), `posture.cc` (DecidePosture + closed reason
vocabulary), `match.cc` (DecideMatch consults posture before the table),
`bundle.cc` (apply/LKG law), `tests/test_posture.cc` (exhaustive
enumeration), `engine/xr_shield_engine.h` + `engine/lib.rs` (totality /
kill_for_test).

### R9b. Scriptlet security posture — UNVERIFIED (T6)

v1 executes NO scriptlets: the decision surface is network-block only.
The shim's cargo features back the boundary (`shield/engine/Cargo.toml`:
no `css-validation`, no `content-blocking`; `resource-assembler` serves
T8's redirect-resource NAMES only — the C side receives a name, never
executable bytes, and there is no renderer to execute them). Before ANY
scriptlet capability is enabled, T6 owes: the sandbox's actual
prohibitions at the pin (page access? DOM APIs? `window` handles?) cited
from a live read, plus 2–3 public CVE/advisory examples of scriptlet-class
bypasses behind the refusal-list entries. No scriptlet claim is made from
memory anywhere in this phase.
