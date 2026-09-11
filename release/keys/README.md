# release/keys/ — the honest state: no real keys exist

**No real keys exist in this repository, and their absence is the honest
state (ADR-0004).** Creating the root key is a human ceremony with a
cost — it is human gate **HG-36** (key ceremony + HSM custody; see
`docs/state/research-log-P10.md` item 9 for the recorded device costs and
terms). The tooling in this repo *refuses* to generate a key marked
`release`; test/CI runs use the TEST-ONLY stub scheme documented in
`xr-core/update/README-integration.md` and banner every accept with
`test-only: …`.

What lives here:

| File | What it is |
|------|------------|
| `root.example.pub` | the SHAPE of the offline root public key (an EXAMPLE — the placeholder text is explicit) |
| `platform.example.pub` | the SHAPE of a per-platform signing public key |
| `key-hierarchy.md` | offline root → per-platform signing keys → artifacts; HSM custody for the stable key; **rotation runbook**; **epoch revocation runbook** incl. the forced manual path |
| `ceremony.md` | the two-person, air-gapped key ceremony, step by step, every step naming its command and its evidence artifact |

`tools/ceremony_check.py` enforces the sections above;
`tools/secret_scan.py --all` proves no private material exists in either
repo. When HG-36 executes, its artifacts (public keys ONLY, fingerprints,
witness signatures) are appended here in NEW commits — private material
never enters git, at ceremony time or ever.
