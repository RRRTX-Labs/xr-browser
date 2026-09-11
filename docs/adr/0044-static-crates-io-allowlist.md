# ADR-0044: static.crates.io joins fetch.py's ALLOWED_HOSTS — pinned crate tarballs for the vendored-Rust layout

- **Status:** PROPOSED (drafted by the P11 coding agent; ratification rides
  HG-26's queue — agents draft, humans decide, L24)
- **Date:** 2026-09-11
- **Deciders (humans):** Platform lead + Security lead (network egress is an
  S0-adjacent surface, L13 dual review)
- **Plan anchor:** Plan §1.5/L9 (no dependency without an evaluation pack),
  DR-03 (native blocking engine = adblock-rust), DR-04 (link policy),
  P3-T1 chokepoint law; P11 brief T1 + research items 1/7
- **Evidence:** `docs/dependencies/adblock-rust.yaml` (refreshed 2026-09-11),
  `docs/state/research-log-P11.md` R1/R7, crate sha256
  `f44b96a666a23c12acad7c688bfe8638a7094e7eabe765b09a6864ab991c676d`
  (crates.io pin, matched through the chokepoint before unpack), tarball's
  own Cargo.lock, `xr-core/third_party/rust/supply-chain/`,
  `tools/vendor_rust.py` + `tools/vendor_check.py` (+ 36 pytest, negatives
  74–76)

## Context

P11-T1 vendors adblock-rust — the plan's chosen native blocking engine
(INTEGRATE verdict, evaluation pack on file since 2026-09-07). Vendoring
means fetching the published `.crate` tarball and its dependency closure.
House law: ALL repo network access flows through `build/upstream/fetch.py`
with an exact-host allowlist "enforced IN CODE (no config weakening)", and
the P11 brief forbids touching `ALLOWED_HOSTS` **except via the documented
allowlist ceremony**. The crates.io CDN (`static.crates.io`) was not on the
list; the brief also anticipated this ("one-time fetch through the
chokepoint with the allowlist ceremony if a new host is needed; then
offline-deterministic forever").

## Decision

Add exactly ONE host — `static.crates.io` — to `ALLOWED_HOSTS`, with the
ceremony recorded in five artifacts:

1. **This ADR** (draft; human ratification via the normal queue).
2. **Research-log rows** (R1 refreshed with the live-verified pin facts;
   R7 records what cargo-vet/audit cannot do here and the substitute that
   WAS run — advisories + licenses + double sha256 sealing).
3. **The dependency evaluation refreshed** (`docs/dependencies/
   adblock-rust.yaml`: v0.13.3 published 2026-08-20, tag `v0.13.3` =
   `886d45dcf5`, MPL-2.0, 0 open advisories, edition 2024).
4. **The checker's second lock updated in the same commit**
   (`tools/fetch_allowlist_check.py` mirrors the host set — the mirror is
   the point: an allowlist edit that forgets the checker goes red).
5. **Tests + negatives**: the ceremony test asserts the CDN tarball URL is
   allowed while `index.crates.io` / `crates.io` / `raw.githubusercontent.
   com` stay REFUSED (negative 76 keeps proving it); URL construction lives
   IN the chokepoint (`fetch.crates_io_crate_url`, like `github_api_url`).

**Why the CDN and not the index/API hosts:** the resolution truth is the
lock file that shipped INSIDE the sha256-pinned tarball — no live index
query is ever needed. `static.crates.io` serves immutable,
content-addressed artifacts whose sha256 upstream already published: the
host can serve wrong bytes but never unverified ones (vendor_rust.py
aborts on mismatch; negative-proven). The index hosts are mutable-truth
surfaces and stay off the list by design.

**Scope guardrails:** read-only GETs of `/crates/<name>/<name>-<ver>.crate`
only; one-time per pin (the tree is offline-deterministic forever after —
`vendor_check.py --check` runs in run_checks AND governance with no
network); pin bumps follow `UPDATING.md` and re-run the whole ceremony
chain (advisory hits abort the vendor).

## Also recorded here (found during the ceremony)

- Governance had been RED since T0-c: `tools/scheduled_lane_check.py`
  carried api.github.com URL literals in code (the chokepoint law's
  URL-in-code rule). FIXED, not exempted: URL construction moved into
  `fetch.github_api_url`; the human-hint message lost its scheme.
- Two pre-existing violations gained documented `EXEMPT_FILES` rows (the
  checker's own law requires an ADR or research-log row — R7 carries
  both): `build/qa/leaktest/engine.py` (loopback-only observer) and
  `build/signing/platform_argv.py` (TSA URL as argv data, never fetched).

## Alternatives considered

- **Vendor via `cargo vendor` on the hosted runner, commit the artifact.**
  Rejected: the committed bytes would be fetched by the runner, not the
  repo's chokepoint — unauditable provenance, and not locally reproducible.
- **Git-clone brave/adblock-rust at the tag.** Rejected: github.com/
  codeload are not allowlisted, and git-tree bytes ≠ published-crate bytes
  (the lock checksums pin `.crate` files; a clone proves nothing about
  them).
- **Manual drop (human downloads, agent verifies).** Rejected: not
  reproducible at pin bumps; the chokepoint path is.
- **Full dev-dependency vendoring for an all-offline `cargo test`.**
  Rejected on size + honesty grounds: ~150 crates / tens of MB incl. C
  sources (aws-lc-sys) and upstream's network-fetching tests; the recorded
  boundary is build-graph-offline + runner-side dev-dep fetch for tests
  (the sanctioned-lane pattern, like pip), stated in PROVENANCE.md and the
  final report's deviations.

## Consequences

- ALLOWED_HOSTS: 4 → 5 entries; egress surface grows by one CDN with no
  auth, no cookies, no write path.
- `xr-core/third_party/rust/` exists: 59-crate verified closure + root pin
  + supply-chain records; every gate re-proves it offline forever.
- Precedent: a future vendored crate (none authorized besides adblock-rust
  in P11) reuses the ceremony — including a new ADR; this one does not
  blanket-approve crates.io.
