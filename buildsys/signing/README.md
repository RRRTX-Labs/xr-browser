# Artifact signing — scaffold only (P2-T8)

**Real certs are HSM-backed and land in P10.** This directory is the
**test-cert scaffold** — the interfaces + test keys only. The absence of
production key material is *honest*, not a gap (ADR-0004).

- `testkeys/make_test_signing_material.sh` — generates a local TEST CA +
  codesigning TEST certs (mac/win emulation) + a minisign keypair. **Refuses**
  if `XR_PROD_SIGN=1`. Filenames/subjects/header all scream TEST.
- `sign_artifact.py` — abstract per-OS signer (linux minisign+`sha256sums.txt`,
  mac `codesign`/`notarytool` passthrough, win `signtool` passthrough).
  **Errors** on any `release`/`stable`-channel request (only `dev`/
  `nightly-test` until P10).

**Choice (ADR-0004, PROPOSED):** minisign for the test scaffold (simplicity;
no transparency-log machinery). Sigstore/cosign + Rekor transparency are
reserved to P10 per §13.6 — the scaffold deliberately does not pretend to be
a transparency log.
