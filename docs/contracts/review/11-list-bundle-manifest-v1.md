# Review packet: List-bundle manifest (signed) v1 (§1.11)

- **Contract id:** list-bundle-manifest  **Version:** 1  **Freeze status:** REVIEW-COMPLETE
- **Ratification:** PENDING (HG-26; human sign-off below is pending)

## Interface inventory
compromise => T10 remote-behavior-control; key-pin + fail-closed-to-LKG.

## Files shipped


## §7.2 import-law compatibility check
- Fake imports: stdlib + `_base` only (legal-only). No `//xr/a`-style
  cross-boundary imports; no reflection; no temporary direct includes.
- mojom imports: `xr_types.mojom` only (leaf surface; //xr/mojom imported BY
  others, not the reverse). PASS (mechanical: mojom_lint + contracts_manifest).

## Threat-model invariants linked
list-bundle-manifest-v1.md, list-bundle-manifest-v1.schema.json

## Checklist (structure enforced by freeze_check.py; sign-off = human)
- [ ] narrow surface — sign-off: __PENDING (human)__
- [ ] typed errors — sign-off: __PENDING (human)__
- [ ] no generic exec — sign-off: __PENDING (human)__
- [ ] fuzz target required before integration — target: `fuzz_list_bundle_manifest` (P9; declaration only) — sign-off: __PENDING (human)__

## Open questions for the S0 humans
- Confirm the deny-default surface matches the intended UX (§10).
- Confirm HG-26 ratification once bindings compile at farm (HG-27).
