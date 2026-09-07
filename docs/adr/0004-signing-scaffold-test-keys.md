# ADR-0004: Artifact-signing scaffold — test-cert only until P10 (minisign)

- **Status:** PROPOSED
- **Date:** 2026-09-07
- **Deciders (humans):** Principal, RRRTX Labs (agents draft, humans decide — ADR-0002 §4)
- **Plan anchor:** Plan §4 Phase P2 task T8; §13.6 (release verification & artifacts);
  §4 Phase P3 security req ("fast-lane artifacts signed with the same keys as
  releases; no unsigned hotfix path, ever"); L6 (fail visibly or fail closed).

## Context

P2 shipped the artifact-signing **scaffold** (`build/signing/`): interfaces
plus TEST key material only. Real certificates are HSM-backed and land in P10
(Plan §4 P10). The scaffold's content is transcribed from
`build/signing/README.md` (the P2 prose of record):

- `testkeys/make_test_signing_material.sh` generates a local TEST CA +
  codesign TEST certs (mac/win emulation) + a minisign keypair. It **refuses**
  to run when `XR_PROD_SIGN=1` is set. Filenames, subjects and the public-key
  header all carry an explicit TEST marker.
- `sign_artifact.py` is an abstract per-OS signer (linux: minisign +
  `sha256sums.txt`; mac: `codesign`/`notarytool` passthrough; win: `signtool`
  passthrough). It **errors** on any `release`/`stable`-channel request —
  only `dev`/`nightly-test` channels are signable until P10.

P3's security fast-lane (XR-P3-T5) signs drill artifacts through this exact
interface with TEST keys; release-key parity is P10 (human-gated) and **no
unsigned path exists even then** — there is no hotfix exception to the
signing requirement (Plan §4 P3 security req, L6).

What is *not* being decided here: the production signing infrastructure
(HSM vendor, certificate profiles, notarization service), which is P10's
decision with its own ADR.

## Decision

1. The P2 scaffold is the canonical signing interface for all pre-P10
   artifacts: **minisign** for the linux/test surface, OS-native tool
   passthrough for mac/win.
2. **Rationale (minisign for the scaffold):** simplicity — Ed25519 detached
   signatures, minimal dependency surface, no transparency-log machinery to
   fake. Sigstore/cosign + Rekor transparency entries are **reserved to
   P10** per Plan §13.6; the scaffold deliberately does not pretend to be a
   transparency log.
3. Channel refusal is a **law**, not a configuration: `release`/`stable`
   signing requests fail closed with an explicit error until P10 lands the
   real key ceremony. The absence of production key material is *honest*,
   not a gap.

## Consequences

- P3+ drill/pipeline artifacts are always structurally signable through one
  interface; when P10 swaps in HSM-backed keys, callers do not change.
- Every TEST-signed artifact is self-describing (TEST markers), so a
  TEST-signed file can never be mistaken for a release artifact.
- Approving this ADR ratifies the P2 scaffold choice as recorded; rejecting
  it requires naming the replacement signer before P3's fast-lane drills can
  produce evidence.
