# permission-audit-event-v1

- **Status:** POST-FREEZE, LIVING. Registered in `registry-post-freeze.md`. NOT in `FROZEN.yaml` (its bytes are untouched). Not ratified (`ratified:` is never written). Decision record: ADR-0051 (DRAFT).
- **Phase:** P15-T4.
- **Schema:** `permission-audit-event-v1.schema.json` (strict subset; `additionalProperties: false`).
- **Golden:** `tests/golden-permission-audit-event.jsonl` (JSON Lines, one canonical row per line; 9 rows covering all three event classes).
- **Generator (golden source):** `xr-core/permissions/core/audit.cc` (`AuditRowJson`). The C++ test regenerates every golden line byte-for-byte (`xr-core/permissions/tests/test_audit.cc`).

## What one row means

One row per permission mutation, and no row for a no-op. A row is structured data, and it is also the source of a frozen `ActivityRow` (kind = kPermission) for the activity feed. The frozen `ActivityRow` is reused unchanged.

## Fields (all required; no others exist)

| Field | Type | Rule |
|---|---|---|
| `contract` | const | `"permission-audit-event"` |
| `contract_version` | const | `1` |
| `event` | enum | `grant` (a widening, or a temporary grant issued), `revoke` (a narrowing or a clear), `expiry` (a temporary grant ended by time, use, or session end) |
| `identity` | string | opaque identity value (`xr:<uuid>`) |
| `capability` | enum | `geolocation`, `camera`, `microphone`, `notifications` (the frozen four) |
| `origin` | string | a bare registrable domain, or `""` for identity-wide rows. Anything else is refused by the generator and by the contract check |
| `scope` | enum | `once`, `session`, `7d`, `identity_default`, `identity_deny_list` |
| `ts_millis` | integer | caller-supplied clock. The core reads no clock |
| `ttl_millis` | integer | `604800000` for 7d, otherwise `0` (no time bound). An expiry is `ts_millis + ttl_millis`, never a formatted date |
| `reason` | enum | `user-grant`, `user-default`, `ttl`, `used`, `session_end`, `revoke_site`, `revoke_all`, `fortress-deny-list` |
| `deciding_layer` | enum | `identity_overlay` or `global_fallback`: which layer decides for the identity AFTER the row's change |
| `determinism_note` | const | the fixed sentence in the schema. It says that identical inputs give identical bytes |

## Absence laws

- No usage, quota, active-count, or "in use" field exists. The schema has no property for one, so a planted field is rejected (`tools/permission_contract_check.py --fixture usage` must redden).
- No free-text origin. A full origin (scheme, path, query, port, userinfo, uppercase) is refused, never truncated (`--fixture origin` must redden; `RedactOrigin` is tested over 14 refusal shapes).

## ActivityRow mapping (frozen; unchanged)

`{ts_millis, kind: "kPermission", identity, summary}`. `summary` is an English default sentence (for example, "Allowed camera for example.com (once)"). Localization goes through the l10n pipeline when the UI half lands (deferred).

## Does NOT prove

- The row is delivered to the user, rendered, or read. Those are UI and runtime facts (NOT-RUN in P15; see the research log).
- The store is authentic. The store integrity law defends against corruption, not a hostile local writer (ADR-0051).
