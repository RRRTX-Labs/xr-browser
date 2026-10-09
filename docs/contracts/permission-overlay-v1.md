# permission-overlay-v1 (the resolver input seam)

- **Status:** POST-FREEZE, LIVING. An additive input to `policy-resolver-v1`. The frozen `ResolveRequest` wire shape and the 66 frozen vectors are UNCHANGED. Decision record: ADR-0051 (DRAFT).
- **Phase:** P15-T1 (carrier), with T3/T5/T6 semantics.
- **Vectors:** `vectors/permission-overlay-v1.json` (33 literal resolver requests; `expected` carries the four frozen `PermissionState` fields only). The frozen file `vectors/policy-resolver-v1.json` is byte-pinned and not edited.
- **Producer:** `xr-core/permissions/core/store.cc` (`ProjectViewJson`). **Consumer:** `xr-core/policy/core/resolve.cc` (`ApplyPermissionOverlay`) and `resolve_io.cc` (`ParsePermissionOverlay`, strict).

## Shape

The request carries an optional `permission_overlay` object. Only these keys are allowed (any other key is a defect):

- `contract_version`: optional, `1`.
- `corrupt`: optional boolean. `true` is how a host reports a store it could not read.
- `denied_identities`: array of identity strings. The Fortress deny-list (host data).
- `defaults`: array of `{identity, capability, state}`. `state` is `kDeny`, `kAsk` or `kAllow`. A duplicate `(identity, capability)` is a defect.
- `grants`: array of temporary grants. Each has `identity`, `domain`, `capability`, `scope`, and exactly the field its scope admits: `once` takes `remaining_uses`; `session` takes `session_id`; `7d` takes `expires_at`.

## Semantics (fail-closed)

- **Absent** `permission_overlay`: inert. The tier table decides.
- **Present but malformed**, including an explicit `null`: the whole overlay is corrupt, and all four permissions deny for every identity. Nothing is partially applied.
- **Corrupt** (flag or defect): all four deny for every identity.
- **Denied identity:** all four deny. This is final, and nothing after it can widen.
- **Default:** sets the state for one capability, overriding the tier for that identity only.
- **Active grant:** widens `(identity, domain, capability)` to `kAllow`. A `7d` grant is active while `expires_at > now_ms` (fail-closed at equality). A `session` grant is active while its id equals the request's `session_id`. A `once` grant is active while `remaining_uses > 0`. An unknown scope never widens.

## Does NOT prove

- Duplicate JSON keys inside a *request* object are not detectable: the shared parser keeps the last one. Persisted documents are protected by the store's canonical round-trip instead (`permission-store`, internal to the permissions core).
- The Panel, the settings section, or live propagation to open tabs (all deferred in P15).
