# release/keys/key-hierarchy.md — the XR signing key hierarchy (v1)

Status: the DESIGN is real-in-repo; the KEYS are human-gated (**HG-36**).
No key below exists yet (ADR-0004) — this document is what the ceremony
will execute, and `tools/ceremony_check.py` holds it to the sections.

```
offline root (xr-root-1)                      air-gapped, 2-person, HSM-backed
  └─ per-platform signing keys                held by the release infrastructure
       ├─ xr-signing-linux-repo   → apt/rpm repo metadata (gpg clearsign)
       ├─ xr-signing-appimage     → AppImage update metadata + artifacts
       ├─ xr-signing-mac          → codesign/notarytool (HG-37 credentials)
       ├─ xr-signing-win          → Authenticode (HG-37 credentials)
       └─ xr-signing-<train>      → update manifests (minisign-ed25519)
             └─ the ACTIVE epoch pins exactly one of these (epochs.yaml)
```

## Custody rules

1. **The root never signs artifacts.** It signs (a) per-platform signing
   keys at rotation time and (b) epoch revocation notices. The root's
   HSM is the **stable-key custody class**: operations require the
   two-person ceremony (below), and the device lives offline between
   ceremonies.
2. **Per-platform keys live in the release infrastructure** (CI
   secrets/HSM partition), scoped per platform, rotatable without root
   ceremony.
3. **Epochs pin signing keys**: the active epoch's `key_id` must equal
   the manifest signature's `key_id`, and the client refuses any key
   substitution with `unknown-signing-key` (update/core/verify_policy.cc
   — the key-substitution test is a golden vector).

## Rotation runbook (per-platform signing key)

1. Generate the NEW key under the same custody class (infrastructure
   keys: CI secret rotation; ceremony class: repeat HG-36 steps).
2. Open a NEW epoch (`epochs.yaml`): `epoch_id` bumps, `seq` increments,
   `key_id` = the new key. Both keys are pinned during the overlap.
3. Land the epoch notice via `epoch-apply` (signed by the ROOT — this is
   a root-ceremony-class operation when it changes the pinned key).
4. Re-sign artifacts with the new key only after the epoch rollout
   window passes; the client refuses the old key from that moment
   (`unknown-signing-key`), and anything already-installed keeps working
   (verification is update-time only).
5. Record every step's evidence per `ceremony.md` §evidence capture.

## Epoch revocation runbook (compromise or rotation-to-broken)

1. Write the revocation notice body (epoch_id/key_id/seq/reason) — the
   wrapper is exactly `{body, signature}` (update_host strict-parse law).
2. Root-sign the notice (minisign-ed25519 over the canonical body bytes).
3. Publish on the update server (`epochs.yaml` `revoked:` + serve the
   notice); clients `epoch-apply` it: `revoked` goes sticky, seq must
   exceed the client's current (stale notices are ignored, monotonic).
4. **Client effect — the forced manual path**: a revoked epoch means
   `EpochAcceptable` fails ⇒ every update deny carries
   `manual_path: true`; the About view renders the reason + the manual
   download pointer + "check again" (no silent failures — P10-T8 law).
   The client NEVER downgrades past the revoked epoch.
5. If the WHOLE epoch is burned: new epoch id + new key (rotation steps
   2–4), old epoch stays revoked forever (revocation is monotonic).

## Which credentials this does NOT create

Everything above needs HSM hardware, certificates, and accounts that do
not exist in this phase: **HG-36** (ceremony + HSM devices; recorded
costs in `docs/state/research-log-P10.md` item 9) and **HG-37**
(code-signing certificates, Apple Developer ID, SmartScreen). The
runbooks for THOSE credentials live in `docs/release/signing-runbook.md`.
