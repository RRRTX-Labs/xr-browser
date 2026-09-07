# Review packet: xr.mojom.VaultService: Unlock/Lock/ListForOrigin/GetField/PutItem/Totp v1 (§1.11)

- **Contract id:** vault-service  **Version:** 1  **Freeze status:** REVIEW-COMPLETE
- **Ratification:** PENDING (HG-26; human sign-off below is pending)

## Interface inventory
L16: no export/GetDatabase surface (absence-is-contract, mojom_lint R4).

## Files shipped


## §7.2 import-law compatibility check
- Fake imports: stdlib + `_base` only (legal-only). No `//xr/a`-style
  cross-boundary imports; no reflection; no temporary direct includes.
- mojom imports: `xr_types.mojom` only (leaf surface; //xr/mojom imported BY
  others, not the reverse). PASS (mechanical: mojom_lint + contracts_manifest).

## Threat-model invariants linked
xr-core/mojom/vault.mojom, fakes/vault.py

## Checklist (structure enforced by freeze_check.py; sign-off = human)
- [ ] narrow surface — sign-off: __PENDING (human)__
- [ ] typed errors — sign-off: __PENDING (human)__
- [ ] no generic exec — sign-off: __PENDING (human)__
- [ ] fuzz target required before integration — target: `fuzz_vault_service` (P9; declaration only) — sign-off: __PENDING (human)__

## Open questions for the S0 humans
- Confirm the deny-default surface matches the intended UX (§10).
- Confirm HG-26 ratification once bindings compile at farm (HG-27).
