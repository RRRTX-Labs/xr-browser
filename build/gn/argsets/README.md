# XR GN argsets — public API

The XR build is parameterized by **argsets**: GN snippets under this directory
that `./scripts/build gen` merges and passes to `gn gen` as `args.gn`. GN arg names are
**public API** (Plan P2 "build flag names become public API") — P4 experiments
and P3's rebase bot depend on these names, so a rename is a breaking change
(PR + register note).

## Files

| File | Role |
|---|---|
| `xr_common.gni` | base argset, applied to every build |
| `xr_release.gn` | ship-intended builds (official tier, minimal symbols) |
| `xr_debug.gn` | developer builds (debug, DCHECKs, full symbols) |
| `xr_component.gn` | helper lanes (component build for fast iteration) |
| `flags.yaml` | the allowlist: every flag + its `read_at` citation (see below) |

## Citation discipline

Every **chromium** flag carries a `# read-at: <file:line>` citation into the
**pinned Chromium rev** (`DEPS chromium_rev`, `d04cdb24…` / 152.0.7977.82).
`flags.yaml` is the machine-checked allowlist: a flag not present there fails
`./scripts/build gen --validate`. A flag whose `read_at` has not been verified in the
pin must be marked `# PENDING-pin-verify` — and is also rejected by
`--validate` until the citation lands.

## XR-owned flags

`xr_branding` (bool) — de-Google branding on/off. Drives the Chromium
`branding` mapping to "Chromium" (never "Chrome") plus the branding patch
application (P2-T6). `xr_channel` (dev|beta|stable) — consumed by
`branding/gen_version.py` for the version string.

## Merge order

`xr_common.gni` → then the selected argset overrides. `resolve_args.py`
reports each override in `--explain` mode so no silent shadowing ever occurs.
