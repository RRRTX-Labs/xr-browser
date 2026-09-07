# XR contract index — the P5 freeze (§1.11)

Pin: chromium `d04cdb24…` (152.0.7977.82). Freeze unit = per-contract v1.
Ratification is HUMAN-GATED (HG-26); nothing here is agent-ratified.

## Conventions (research-log-P5 R2/R3)

- **Module:** every interface lives in `module xr.mojom;` (file `xr-core/mojom/`).
- **Versioning:** mojom has no inline file-version field. Chromium versions at
  the symbol level with `[MinVersion=N]` and marks wire-stable types `[Stable]`.
  XR additionally stamps each file with `const int32 kContractVersion = 1;` as
  the human/CI-visible freeze unit. `[MinVersion=N]` is reserved for the
  in-place additions an approved RFC (T10) authorizes. See BLOCKED note below
  re: per-file `const` redefinition at real compile (HG-27).
- **Typed errors only:** unions over a value and an `ErrorCode` enum; never a
  `string message` + `int code` pair (mojom_lint R5).
- **Naming (§1.11 ↔ T1):** where §1.11 names an interface and T1 names a file,
  the file carries the interface with the §1.11 name. No third name.

## Mapping table (file ↔ interface ↔ §1.11 item ↔ §2.10 reserved row)

| §1.11 item | interface / schema | file | §2.10 reserved | fake | vectors/fixtures | packet | freeze |
|-----------|--------------------|------|----------------|------|------------------|--------|--------|
| EffectivePolicy | `EffectivePolicy` (schema) | `effective-policy-v1.schema.json` | fingerprint/letterbox/storage-scope | `policy_resolver.py` | `vectors/policy-resolver-v1.json` | `review/01-effective-policy-v1.md` | REVIEW-COMPLETE |
| PolicyResolver | `xr.mojom.PolicyResolver` | `xr-core/mojom/policy_resolver.mojom` | (resolver total) | `policy_resolver.py` | `vectors/policy-resolver-v1.json` | `review/02-policy-resolver-v1.md` | REVIEW-COMPLETE |
| IdentityManager | `xr.mojom.IdentityManager` | `xr-core/mojom/identity.mojom` | — | `identity.py` | `fakes/fixtures/identity-v1.json` | `review/03-identity-manager-v1.md` | REVIEW-COMPLETE |
| Shield | `xr.mojom.Shield` (+`BlockEvent`) | `xr-core/mojom/shield.mojom` | — | `shield.py` | `fakes/fixtures/shield-v1.json` | `review/04-shield-v1.md` | REVIEW-COMPLETE |
| RouteManager | `xr.mojom.RouteManager` | `xr-core/mojom/route_manager.mojom` | proxy/WG/Tor | `route_manager.py` | `vectors/route-manager-v1.json` | `review/05-route-manager-v1.md` | REVIEW-COMPLETE |
| VaultService | `xr.mojom.VaultService` | `xr-core/mojom/vault.mojom` | autofill mediation | `vault.py` | `fakes/fixtures/vault-v1.json` | `review/06-vault-service-v1.md` | REVIEW-COMPLETE |
| GuardLedger | `xr.mojom.GuardLedger` | `xr-core/mojom/guard.mojom` | update-diff/egress | `guard.py` | `fakes/fixtures/guard-v1.json` | `review/07-guard-ledger-v1.md` | REVIEW-COMPLETE |
| DownloadSafety | `xr.mojom.DownloadSafety` | `xr-core/mojom/downloads.mojom` | xr-inspect | `downloads.py` | `fakes/fixtures/downloads-v1.json` | `review/08-download-safety-v1.md` | REVIEW-COMPLETE |
| ActivityLog | `xr.mojom.ActivityLog` | `xr-core/mojom/activity_log.mojom` | accountability rows | `activity_log.py` | `fakes/fixtures/activity-log-v1.json` | `review/09-activity-log-v1.md` | REVIEW-COMPLETE |
| CommandRegistry descriptor | `CommandRegistry` (schema) | `command-descriptor-v1.md` + `command-descriptor-v1.schema.json` | — | `fakes/fixtures/command-descriptor-v1.json` | fixtures | `review/10-command-descriptor-v1.md` | REVIEW-COMPLETE |
| List-bundle manifest (signed) | manifest (schema) | `list-bundle-manifest-v1.md` + `list-bundle-manifest-v1.schema.json` | — | `fakes/fixtures/list-bundle-example.json` | signed example | `review/11-list-bundle-manifest-v1.md` | REVIEW-COMPLETE |
| Update manifest (3.1 JSON) | manifest (schema) | `update-manifest-31-json.md` + `update-manifest-31.schema.json` | — | `fakes/fixtures/update-manifest-example.json` | example | `review/12-update-manifest-v1.md` | REVIEW-COMPLETE |
| Isolation-Card strings | l10n strings | `xr-core/l10n/isolation_card.json` | — | (strings are the fixture) | isolation_card.json | `review/13-isolation-card-v1.md` | REVIEW-COMPLETE |
| Settings/theme schema | settings + theme (schema) | `settings-schema-v1.md`, `theme-tokens-v1.md`, `xr-schema-v1.md` | — | `tools/xr_schema.py` | `fakes/fixtures/settings-example.json` | `review/14-settings-theme-schema-v1.md` | REVIEW-COMPLETE |

> The §1.11 list is 14 items; the mapping above binds each to its file(s),
> fake, fixtures/vectors and review packet. `tools/contracts_manifest.py`
> enforces this table mechanically.

## Dependency-graph link-ins (§3)

P6 (policy resolver) → consumes `PolicyResolver` + `EffectivePolicy` vectors.
P7 (command registry) → `CommandRegistry` descriptor. P8 → settings/theme.
P9 → inherits `contracts/tests/` parity shape + `vectors/`. P10 → update
manifest + list-bundle. P14 → `IdentityManager`. P11–P13 → `Shield`.
P17–P19 → `RouteManager`. P21 → `GuardLedger`. P26 → `DownloadSafety`.
P27–P30 → `VaultService`. All tracks → `ActivityLog`.

## BLOCKED-TOOLING / honest limits

- Real mojom compile of the surface (bindings) is farm-gated (HG-9/HG-27).
  In particular, whether N per-file `const int32 kContractVersion` declarations
  in one `module xr.mojom` compile without a redefinition error is a
  **farm-compile question**; the freeze stamp requirement is met structurally
  now and the compile verdict is recorded BLOCKED-TOOLING (HG-27). If the farm
  reports a redefinition, the fix is a single shared const in xr_types plus a
  renamed per-file stamp — an RFC-free mechanical change (documented, not done).
- Updater manifest client acceptance → farm (P10), PENDING-VERIFY-farm.
- Isolation-Card legal review → HG-1.
