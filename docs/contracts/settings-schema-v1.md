# Contract: Settings schema v1 (§1.11 #14 part, §10)

- **Version:** 1. **Schema:** validated by `tools/xr_schema.py` (settings).
- **Migration note:** `xr-schema-v1.md`.

## No settings outside the schema (§10 law)

Every user-facing setting MUST have a schema entry: `key`, `type`
(bool/enum/int/string), `default` (deny-safe where security-relevant),
`attention_tier`, and `scope` (global | per-identity). A UI toggle without a
schema entry does not ship (P8 CI-check). Settings are declarative data; no
setting stores executable content.
