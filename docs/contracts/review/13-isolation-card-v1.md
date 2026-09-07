# Review packet: Isolation-Card disclosure strings v1 (§1.11)

- **Contract id:** isolation-card  **Version:** 1  **Freeze status:** REVIEW-COMPLETE
- **Ratification:** PENDING (HG-26; human sign-off below is pending)

## Interface inventory
L5: measured facts not promises; legal PENDING-HG-1; vocab-lint clean.

## Files shipped


## §7.2 import-law compatibility check
- Fake imports: stdlib + `_base` only (legal-only). No `//xr/a`-style
  cross-boundary imports; no reflection; no temporary direct includes.
- mojom imports: `xr_types.mojom` only (leaf surface; //xr/mojom imported BY
  others, not the reverse). PASS (mechanical: mojom_lint + contracts_manifest).

## Threat-model invariants linked
xr-core/l10n/isolation_card.json

## Checklist (structure enforced by freeze_check.py; sign-off = human)
- [ ] narrow surface — sign-off: __PENDING (human)__
- [ ] typed errors — sign-off: __PENDING (human)__
- [ ] no generic exec — sign-off: __PENDING (human)__
- [ ] fuzz target required before integration — target: `fuzz_isolation_card` (P9; declaration only) — sign-off: __PENDING (human)__

## Open questions for the S0 humans
- Confirm the deny-default surface matches the intended UX (§10).
- Confirm HG-26 ratification once bindings compile at farm (HG-27).

## Migration note
Isolation-Card strings are versioned by `contract_version` in
`xr-core/l10n/isolation_card.json`; string changes follow the forward-only
chain in `docs/contracts/xr-schema-v1.md`. New locales add sibling keys.
