# Contract — build-time SBOM (v1)

- **Status:** PUBLISHED (P2-T9). Consumed by the release pipeline (P10) and
  the SBOM gate (`buildsys/sbom/sbom_gate.py`). Schema: **CycloneDX JSON 1.6**
  (vendored `buildsys/sbom/cyclonedx-schema-1.6.json`, Apache-2.0 data).

## 1. Shape

`buildsys/sbom/emit_sbom.py` emits a CycloneDX 1.6 document:

- `bomFormat: CycloneDX`, `specVersion: "1.6"`.
- `serialNumber`: deterministic `urn:uuid` (uuid5 over the sorted component
  list — no timestamp; SOURCE_DATE_EPOCH-free by construction).
- `metadata.component`: the XR build (name `xr-browser`, version from
  `gen_version.py`, properties: chromium pin, argset, channel).
- `components[]`: one entry per `gn desc --libs` target + per `third_party/*`
  DEP entry + (optional, empty-tolerant) cargo crates.

## 2. Honesty rules (L5)

- License fields are **`NOASSERTION` unless known**. P2 does not guess licenses;
  the full dep-graph license/advisory resolution lands in **P9-T9** (the same
  scope boundary as `tools/license_audit.py`, which is header-level). A vendor
  `LICENSE` file's existence is recorded; its SPDX id is asserted only where a
  pinned eval already states it.
- `cargo metadata` is **optional and empty-tolerant**: today there are no Rust
  crates in the build (helpers land P4+); the generator must accept an empty
  input and emit zero cargo components, not error.

## 3. Gate

`sbom_gate.py` validates (stdlib, no jsonschema dep): JSON wellformedness,
top-level `bomFormat`/`specVersion` required by the vendored schema, component
`type`/`name` presence, `serialNumber` presence. The vendored schema is the
reference for field assertions.
