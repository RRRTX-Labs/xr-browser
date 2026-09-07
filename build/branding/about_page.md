# About-page inputs (P2-T6)

Inputs for the `chrome://about`/about-page override, applied via the branding
patch machinery (xr-core `patches/branding/`). The values below are fed to the
build by `gen_version.py` (version/channel) and the strings overrides — the
actual GRD wiring lands with the strings-override patch set in P6-T6; P2 ships
the **inputs and the plumbing** (applicator + version builder), not the full
about-page rewrite.

| Field | Value | Source |
|---|---|---|
| Product name | XR Browser | `patches/branding/0001-brand-ui` (BRANDING + IDS_PRODUCT_NAME) |
| Version | `{milestone}.{build}` | `gen_version.py` (DEPS chromium_version) |
| Channel | dev / beta / stable | `XR_CHANNEL` (gen_version.py) |
| Update endpoint | `https://update.xr.example/` (RFC 2606) | gen_version.py — PENDING-OPS until P10 |
| Copyright | `Copyright @LASTCHANGE_YEAR@ RRRTX Labs. All rights reserved.` | BRANDING patch |

Scope honesty: the browser about-page copy that reads these inputs is P6;
today the inputs are produced and linted, not rendered.
