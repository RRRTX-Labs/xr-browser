# strings_overrides — GRD patch inputs (P2-T6)

The GRD string overrides are applied through the patch-manifest machinery
(xr-core `patches/branding/`), not by copying GRD files here. The seed patch
`0001-brand-ui` overrides `chrome/app/chromium_strings.grd`
(IDS_PRODUCT_NAME / IDS_SHORT_PRODUCT_NAME) and
`chrome/app/theme/chromium/BRANDING`.

This directory is reserved for the **input data** the fuller P6 de-branding
pipeline consumes (per-milestone string dumps that seed regenerated patches).
It is empty by design in P2 — adding files here before P6 would be a stub
(anti-fabrication rule).
