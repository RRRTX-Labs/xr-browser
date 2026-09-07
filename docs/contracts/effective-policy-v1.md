# Contract: EffectivePolicy v1 (§1.11 #1, §2.10 reserved fields)

- **Schema:** `effective-policy-v1.schema.json` (strict, `additionalProperties:false`).
- **Version:** 1. **Migration note:** see `xr-schema-v1.md` (forward-only chain).
- **Fixtures/vectors:** `vectors/policy-resolver-v1.json` (≥64 golden vectors).
- **Fake:** `xr-core/fakes/policy_resolver.py` (ground truth for vectors).
- **Produced by:** `xr.mojom.PolicyResolver.Resolve` (pure/total/deterministic).

## Fields (T2 list)

blocking · cosmetic · permissions · egress · fingerprint · storage-scope ·
vault-scope · process-policy · letterbox · version. Every field has a
deny-safe default; there is no "unset ⇒ allow" state.

The §2.10 reserved fields — **fingerprint**, **letterbox**, **storage-scope** —
are present from day one so the resolver is total over them even though the
subsystems that fully honor them land later (P20/P35).

## Total-function semantics (machine-checked)

The resolver is a TOTAL function. Unknown identity, unknown origin, unknown
request class, or malformed input ⇒ the fully-denying EffectivePolicy — never
an error a caller could treat as "allow". This is:

1. **stated** here and in `policy_resolver.mojom`;
2. **schema-checked**: strictness (`additionalProperties:false`) + required
   fields + enum-constrained values, via `tools/xr_schema.py`;
3. **vector-checked**: the deny rows in `vectors/policy-resolver-v1.json`
   (`unknown-identity`, `unknown-origin-scheme`, `empty-domain`,
   `unknown-request-class`, `malformed-*`, `invalid-trust`) assert the denying
   object byte-for-byte;
4. **purity-checked**: `tests/test_policy_determinism.py` monkeypatches
   `time`, `random`, and `os.environ` and asserts identical output.
