# Review packet: EffectivePolicy v1 (§1.11)

- **Contract id:** effective-policy  **Version:** 1  **Freeze status:** REVIEW-COMPLETE
- **Ratification:** PENDING (HG-26; human sign-off below is pending)

## Interface inventory
Schema `effective-policy-v1.schema.json`; produced by PolicyResolver.Resolve.

## Files shipped
effective-policy-v1.schema.json, effective-policy-v1.md, vectors/policy-resolver-v1.json

## §7.2 import-law compatibility check
- Fake imports: stdlib + `_base` only (legal-only). No `//xr/a`-style
  cross-boundary imports; no reflection; no temporary direct includes.
- mojom imports: `xr_types.mojom` only (leaf surface; //xr/mojom imported BY
  others, not the reverse). PASS (mechanical: mojom_lint + contracts_manifest).

## Threat-model invariants linked
L15/L16: total resolver, deny-default; §2.10 reserved fields present.

## Checklist (structure enforced by freeze_check.py; sign-off = human)
- [ ] narrow surface — sign-off: __PENDING (human)__
- [ ] typed errors — sign-off: __PENDING (human)__
- [ ] no generic exec — sign-off: __PENDING (human)__
- [ ] fuzz target required before integration — target: `fuzz_effective_policy` (P9; declaration only) — sign-off: __PENDING (human)__

## Open questions for the S0 humans
- Confirm the deny-default surface matches the intended UX (§10).
- Confirm HG-26 ratification once bindings compile at farm (HG-27).
