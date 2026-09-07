# Contract: List-bundle manifest v1 (signed) (§1.11 #11)

- **Schema:** `list-bundle-manifest-v1.schema.json`. **Version:** 1.
- **Migration note:** `xr-schema-v1.md`. **Example:** `fakes/fixtures/list-bundle-example.json` (+ `.minisig` when minisign is present).
- **Fake:** the example manifest itself is the consumption fixture.

## Envelope (research R4)

A JSON manifest signed with a **minisign detached signature** (Ed25519) over
the canonical (sorted-key) bytes. minisign is already the P2/P3 scaffold signer
(`build/signing/`), so the CI signs the example when present and emits a visible
SKIP when absent (skip-policy law).

Fields: `schema_version`, `bundle_id`, `created_epoch`, `lists[]`
(`{name, sha256, rules}`), `key_pin[]` (trusted Ed25519 public keys), and a
sibling `<file>.minisig`.

## Security

- **Compromise ⇒ T10 remote-behavior-control** threat row: a forged bundle can
  change what the browser blocks/allows remotely. Mitigation: `key_pin[]`
  allowlist + detached-signature verification before use.
- **Delta / fail-closed:** delta rules MUST define "fail closed to last-known-
  good" — if no valid signed bundle verifies, the client keeps the last verified
  bundle (the absent-valid-bundle state is representable via
  `last_known_good_bundle_id`), never an empty/unsigned list.
