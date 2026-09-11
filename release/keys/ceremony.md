# release/keys/ceremony.md — the XR root key ceremony (v1 runbook)

Status: **the ceremony has NOT run** (HG-36; costs/terms recorded in
`docs/state/research-log-P10.md` item 9). This is the exact runbook it
will execute. Every step names its command and its evidence artifact —
if a step cannot produce its artifact, the ceremony STOPS and nothing
ships.

## Principles

- **Two-person witness**: every physical action (device unsealing, PIN
  entry, signing) happens with two authorized people present, both
  signing the evidence for that step. One operator, one witness; the
  witness holds the recovery card.
- **Air-gapped generation**: the root key is generated on a machine with
  no radio, no ethernet, no USB except the HSM and a cleared printer.
  The machine never touches the internet again (boot from clean media
  each ceremony).
- **release-refusal**: no repository tooling will generate or hold a
  release-marked key — `tools/` refuses on any `release`-marked keygen
  (negative fixture: `tools/negatives/p10_release.sh`,
  `signing_release_keygen_refused`). Keys are born in the HSM, in the
  room, or not at all.

## Ceremony steps

### 0. Pre-flight
- Command: `tools/secret_scan.py --all` (both repos clean).
- Artifact: `ceremony/evidence/00-preflight-scan.txt`.

### 1. Room + devices
- Command: photograph the sealed HSM (2 devices: primary + backup) and
  the air-gapped laptop booting clean media.
- Artifact: `ceremony/evidence/01-devices-<ts>.jpg`, unseal witness
  signatures.

### 2. Generate the root key IN the HSM
- Command (on the air-gapped machine, HSM attached):
  `ykman piv access change-pin` → `ykman piv keys generate 9a \
  ceremony/root-pub.pem` (PIV slot 9a, ED25519 where supported, else
  RSA-4096; the algorithm decision is recorded in evidence).
- Two people present; PIN never typed by the operator alone.
- Artifact: `ceremony/root-pub.pem` (PUBLIC only),
  `ceremony/evidence/02-keygen-log.txt` (device serials + witness
  signatures).

### 3. Name and fingerprint
- Command: `openssl pkey -pubin -in ceremony/root-pub.pem -outform DER \
  | openssl sha256` → the root fingerprint.
- Artifact: `ceremony/evidence/03-fingerprint.txt` (fingerprint +
  key_id assignment `xr-root-1`), read aloud and witnessed.

### 4. Backup device
- Command: repeat step 2 on the backup HSM; verify the SAME public key
  is exportable (PIV attestation) or document the split (primary-only
  custody + sealed backup PIN).
- Artifact: `ceremony/evidence/04-backup.txt`.

### 5. Signing-a-test-artifact (the proof the key works)
- Command: sign a synthetic `Release` file with the root via the HSM
  (`gpg --homedir <clean> --detach-sign ...` driven through the PIV
  slot, or the HSM vendor's tool), then verify with ONLY the public key:
  `gpg --verify Release.sig Release`.
- Artifact: `ceremony/evidence/05-test-artifact/{Release,Release.sig,verify-output.txt}`.

### 6. Evidence capture per artifact (closing the ceremony)
- Command: `sha256sum ceremony/evidence/* > ceremony/evidence/MANIFEST`
  then two-person sign (ink) the printed manifest; commit the PUBLIC
  artifacts (`*.pub`, fingerprints, signed manifests — NEVER private
  material) to `release/keys/` in a new commit.
- Artifact: `ceremony/evidence/MANIFEST` + the commit SHA, recorded in
  `docs/state/research-log-P10.md` follow-up.

## After the ceremony

- Per-platform keys are generated per `key-hierarchy.md` custody rules
  (infrastructure class — no air gap required, but still two-person).
- The first epoch notice pins the first signing key, root-signed, via
  `epoch-apply` (drill: `tools/rollout_drill.py`).

## What is deliberately NOT in this file

Code-signing certificate procurement, Apple notarization, SmartScreen —
those are **HG-37** and live in `docs/release/signing-runbook.md`.
