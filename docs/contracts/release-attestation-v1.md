# release-attestation-v1 — the transparency attestation format (living contract)

Registered: `docs/contracts/registry-post-freeze.md` (P10 section).
Validated by: `tools/xr_schema.py validate release-attestation <file>`.
Emitted/verified by: `tools/attest.py` (REAL here: `--build`, `--verify`;
`--publish` is SKIP-visible without credentials/egress — HG-38).

## Shape (in-toto/SLSA-style, canonical bytes)

```json
{"predicate": {"builder": {"id": "..."}, "build_type": "...",
               "chromium_rev": "<pinned 40-hex>", "evidence_sha256": null,
               "plan_pin": "P10", "sbom_sha256": null},
 "schema": "xr-release-attestation", "schema_version": 1,
 "subject": [{"name": "<artifact>", "sha256": "<64-hex>"}],
 "type": "xr-release-attestation-v1",
 "signature": {"alg": "minisign-ed25519", "key_id": "xr-root-1",
               "sig": "<sig over canonical(statement-without-signature)>"}}
```

Laws:
1. **Canonical bytes**: the statement is canonical JSON (sorted keys);
   the signature covers `canonical(statement \ {signature})`.
2. **Subject = digests, not promises**: every artifact appears as
   `{name, sha256}`; a tampered artifact breaks verification (one byte
   ⇒ fail, tested).
3. **Predicate pins the world**: builder id, `chromium_rev` (the DEPS
   pin), the plan pin, the SBOM digest and the evidence-bundle digest
   (null until those exist — the null is honest, not a placeholder).
4. **Signature**: minisign-ed25519 by the epoch root key. In this phase
   the pinned key is the **TEST-ONLY stub material**
   (`tools/attest-pinned-key.txt`; the banner says so) — offline
   verifiability is DEMONSTRATED with a pinned public key now, and the
   production binding is the HG-36 ceremony swapping in the HSM key.
   No crypto is invented here; the verifier is the same injected
   primitive the update core pins (interface + documented binding).
5. **Publish/external verifiability**: `--publish` requires transparency
   -log credentials/egress (HG-38) and SKIPs visibly without them;
   `--check-inclusion` (hosted lane) reports NOT-RUN with a reason until
   something has been published. The plan's "externally verifiable"
   DoD row stays BLOCKED/human-gated — never marked VERIFIED from here.
