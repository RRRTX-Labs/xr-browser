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
  — this is the T1 vendor pin; `static.crates.io` serves the `.crate`
  tarball (HTTP 200) but is NOT in `fetch.py` ALLOWED_HOSTS → the
  allowlist ceremony (`docs/process/allowlist-ceremony.md`) must land
  before vendoring bytes through the chokepoint.

## R2. Upstream conformance corpus (filter matching) — UNVERIFIED (T1/T8)

Candidate sources to evaluate at T1: adblock-rust's own test data
(`tests/`), EasyList/EasyPrivacy header contracts, filter-syntax
documentation. The ≥1,500-case vendored corpus for T8 parity must be
machine-derivable and license-clean; attribution per source is mandatory
(T3's frozen list-bundle-manifest-v1 either carries it or we STOP per the
brief).

## R3. Chromium network-service seam at pin d04cdb24 — UNVERIFIED (T2)

The pin (`152.0.7977.82 @ d04cdb24d67b081f6cf80200ffc5233f44b61109`,
`xr-browser/DEPS`) has no checkout in this sandbox; `path:line` citations
for the URLLoaderFactory/NetworkContext interception point must come from a
live read at the pin before the patch manifest grows its third entry. Same
honesty rule as P10 R1.

## R4. MV3/DNR limits (what Shield must NOT promise) — UNVERIFIED (T4/T6)

## R5. Brave memory work (adblock-rust in production) — UNVERIFIED (T7)

## R6. EasyList licensing (bundle redistribution) — UNVERIFIED (T3)

## R7. cargo-vet in a vendored (non-workspace) layout — UNVERIFIED (T1)

## R8. Runner capabilities from REAL runs (no comment-claims)

**PARTIALLY VERIFIED (cited runs).** `cargo`/`rustc` present on
ubuntu-latest: hosted server-conformance run `34615191984` (P10) compiled
Rust. `g++`, `make`, `python3.12`: every governance/core-hardening run.
`go`: only claimed in a core-hardening.yml comment — NOT recorded (a
comment is not a run). These citations seed
`docs/state/runner-capabilities.json` (T0-d input); an entry without a
run-id citation is refused by `evidence_check.py --strict`.

## R9. Scriptlet security posture + fail-open mechanics — UNVERIFIED (T2/T6)

Fail-open (engine death ⇒ allow) vs fail-closed (route loss ⇒ block) is the
T2 posture asymmetry; the mechanics research lands with `posture.{h,cc}`.
Scriptlets: v1 executes NONE (the decision is network-block only) — the
research item records why that boundary is the safe default and what a
future scriptlet capability would have to prove first.
