# XR Shield v1 — the list pipeline, attribution, and the hot-pin runbook (P11-T3)

Home: `xr-lists/` (repo choice recorded as D4 in
`docs/state/research-log-P11.md`: the TEST-only signing channel
`build/signing/`, the house `tools/` gate dir, and the vectors/negative
machinery all live in xr-browser; xr-core is the C++/Rust tree a Python
data pipeline would compile into nothing). **Lists are DATA, never code**
(plan DR-04): nothing in a bundle is executed; the scriptlet/`$replace`
surface is refusal-by-default (`docs/shield/scriptlets.md`, ADR-0045).

## 1. Pipeline (compile → attribution → sign)

| step | tool | law |
|---|---|---|
| compile | `xr-lists/compile.py` | ABP/uBO syntax → the normalized `xr-list-bundle-v1` document; every unsupported directive becomes a TYPED refusal (refusal table ≥30 cases enforced — 100 compile vectors / 47 refusals via `tools/gen_lists_compile_vectors.py`, vectors at `docs/contracts/vectors/xr-lists-compile-v1.json`) |
| attribution | `xr-lists/attribution.py` | the attribution shape law + the `LICENSE.attribution.txt` sidecar; anything off-shape reddens |
| sign | `xr-lists/sign.py` | the FROZEN `list-bundle-manifest-v1` schema + a detached signature over TEST channels only (release channels refuse — the P10 key ceremony HG-36 has not run) |
| canonical bytes | `xr-lists/bundle_bytes.py` | the pipeline's ONE copy of the frozen canonical-bytes rules |
| gate | `tools/list_bundle_check.py` | frozen-schema sha256 pin, schema/binding/state laws, refusal coverage, `--check` regeneration (diff-clean in `run_checks.sh`) |
| round-trip | `xr-lists/tests/roundtrip.sh` | the real matrix: gpg sign/verify/tamper/wrong-key, SKIP-visible absences, release-channel refusal, host binding, hot-pin-out, replay |

The frozen manifest is consumed UNTOUCHED: `run_checks.sh` prints the
sha256 comparison (`docs/contracts/FROZEN.yaml` byte-identical every run).
Attribution rides inside the frozen schema's only legal home — `lists[]`
entries (top level is `additionalProperties:false`) — so no schema change
was needed and the STOP condition in the brief never armed.

## 2. Client verification = P10's path only

The client verifies bundles with the P10 update machinery — pinned keys,
`epoch` rotation/revocation, `seen` replay refusal, monotonic version,
LKG fallback, last-2 retention — reusing
`xr-core/update/core/{verify_policy,epoch,seen,backoff,manifest}.cc`.
**No new signature format, no new rollback mechanism.** The apply law
(`xr-core/shield/core/apply.cc`) refuses downgrades and equal re-offers;
that refusal IS the replay path (tested end-to-end by the round-trip's
host cells).

## 3. Attribution — three bound places

1. the bundle's per-list `attribution` — required by the shield core's
   bundle grammar and INSIDE the list digest
   (`xr-core/shield/core/bundle.h`), so it cannot be stripped without
   breaking the binding;
2. the manifest's per-entry `attribution` — bound by the host's
   `bundle-check`: a manifest claiming other attribution than the pinned
   bytes carry is refused (`manifest-attribution:<name>`);
3. the `LICENSE.attribution.txt` sidecar emitted beside the bundle.

Sources today are **synthetic CC0 fixtures only** (`xr-lists/sources/`):
no upstream list bytes enter the repo until the R6 licensing posture is
cleared (human gate HG-1) and a `build/upstream/fetch.py` allowlist
ceremony lands. The pipeline is proven end-to-end on self-authored
fixtures; the licensing hold gates the SET, not the machinery.

## 4. Hot-pin runbook (removing a bad list in the field)

The hot-pin-out is signed DATA, not code and not a new mechanism:

1. remove the list's entry from `xr-lists/sources/config.json`;
2. bump `bundle_version` (monotonic per `bundle_id`);
3. re-run the gate + round-trip (`python3 tools/list_bundle_check.py
   --check && bash xr-lists/tests/roundtrip.sh`);
4. re-sign and publish through the update channel.

The client drops the list with NO network access beyond the offer it
already verifies, and a re-offered OLD bundle (with the bad list) is
refused by monotonicity — the round-trip's host cells test exactly this
sequence. LKG/last-2 semantics come from `update/core/backoff.cc` +
`seen.cc` (fail-closed to last-known-good, plan §arch 3).
