# Building XR Browser (P2 — hermetic Chromium build)

This is the external-rebuild document (Plan P2-T7: "build docs exact enough
for external rebuild"). It describes how to reproduce an XR build from the
pinned sources using the `./build` entrypoint. All build tooling lives in
`build/`; every tool is stdlib-first (the only dev dependencies are the
governance suite's PyYAML/jsonschema/pytest, hash-pinned).

> **Honesty:** the pipeline below is implemented and mock-verified end-to-end.
> The *actual* three-OS build has not run on real CI hardware yet — that is a
> human-gated P2 DoD item (HG-9, below), not something this document pretends
> has happened.

## 1. The build in one paragraph

`./scripts/build sync` creates a pinned Chromium checkout with `xr-core` mounted at
`src/xr` (the Brave overlay pattern). `./scripts/build gen` merges the XR GN argsets
and runs `gn gen`. `./scripts/build compile` runs `ninja` on `//xr:xr_all`. After
`sync`, the build performs **no network access** (checkable property, see
`build/net-audit.md`). Every tool exits `0` pass / `1` fail / `2` usage and
supports `--json` (`build/_common.py` is the shared contract).

## 2. Prerequisites

| Need | Requirement | Check |
|---|---|---|
| OS | Linux (primary), macOS, Windows | `uname` |
| Disk | ≥ 2× the estimated checkout+build size | `./scripts/build preflight` refuses under-provisioned hosts |
| RAM / CPUs | probed, not hard-gated (recorded only) | `./scripts/build preflight` |
| Python | 3.12 (stdlib-only for build tools) | `python3 --version` |
| depot_tools | fetched at runtime (BSD-3), never vendored | `./scripts/build sync` does it |
| ccache | optional but recommended (50G default) | `build/farm/ccache-setup.sh` |

`./scripts/build preflight` is the first real gate: it refuses hosts that cannot hold
the checkout rather than simulating state.

## 3. Quick start

```sh
./scripts/build preflight                      # refuse under-provisioned hosts
./scripts/build sync                           # pinned checkout + xr-core mount at src/xr
./scripts/build gen    --argset xr_release.gn  # merge argsets + gn gen out/xr_release
./scripts/build compile                        # ninja -C out/xr_release //xr:xr_all
./scripts/build sbom                           # emit the CycloneDX 1.6 SBOM for the build
./scripts/build brand-check --scan             # endpoint-deny scan over the build surface
```

The checkout is created at the repo default (see `./scripts/build sync --help`); pass
`--checkout <path>` to any tool to point at a non-default location.

## 4. Subcommand reference

| Command | What it does |
|---|---|
| `./scripts/build sync` | create/verify the pinned checkout (Chromium at `DEPS chromium_rev`, xr-core at `src/xr`), write `.xr/egress.json` |
| `./scripts/build refresh --to <sha>` | create a pin-refresh branch + PR body; **never pushes** |
| `./scripts/build preflight` | disk/RAM/nproc probe + refusal threshold |
| `./scripts/build gen --argset <name>` | resolve argsets (allowlist-checked) + `gn gen` |
| `./scripts/build compile [--target //xr:xr_all]` | `ninja` a target |
| `./scripts/build patch apply\|verify\|revert\|lint` | patch-manifest applicator (see `build/patching/`) |
| `./scripts/build sbom` | emit CycloneDX 1.6 SBOM (`build/sbom/`) |
| `./scripts/build sbom-gate` | validate an SBOM against the vendored schema |
| `./scripts/build brand-check` | `--binary` brand-leak check, `--scan` endpoint-deny |
| `./scripts/build version` | build the version string (from DEPS) |
| `./scripts/build sign` | TEST-ONLY signing scaffold (dev/nightly-test only until P10) |
| `./scripts/build budget` | patch-budget meter (report-only this phase) |
| `./scripts/build test` | run the full build-system test suite |

## 5. Mock mode

Everything except `sync`'s real gclient run can be dry-run without a checkout:

```sh
XR_ALLOW_MOCK=1 ./scripts/build --mock sync --checkout /tmp/x
XR_ALLOW_MOCK=1 ./scripts/build --mock gen  --checkout /tmp/x
XR_ALLOW_MOCK=1 ./scripts/build --mock compile --checkout /tmp/x
```

Every line is prefixed `MOCK MODE — not a build`. Mock output is **never**
build evidence.

## 6. GN argsets (public API)

`build/gn/argsets/` — `xr_common.gni` (base) merged with
`xr_release.gn` | `xr_debug.gn` | `xr_component.gn`. Every flag is
allowlist-checked against `flags.yaml`; a flag absent from the allowlist
fails `./scripts/build gen`. The de-Google posture is the argset default:
`google_api_key=""`, `safe_browsing_mode=0`, `enable_widevine=false`
(DR-14 OPEN / LG-3), `xr_branding=true`. GN arg names are public API
(renames are breaking changes).

## 7. Reproducibility & provenance

- **Toolchain pins:** `build/toolchain/pins.json` — clang
  `llvmorg-23-init-19482-g53d18800-1` (linux artifact sha256
  `e22e06c0…c98c42`), nine sysroot sha256 digests (content-addressed, verified
  against the pinned tree), Mac SDK 26.5 (25F70), Windows SDK 10.0.26100.0.
  Verify with `python3 build/toolchain/provenance.py --verify`.
- **Zero egress:** `build/net-audit.md` defines the checkable rule and the
  strace/dtrace/Sysmon verification procedure (human-run on the build hosts).
- **De-branding:** `./scripts/build brand-check --binary <artifact>` scans for Google
  brand strings and missing XR marks; `--scan` enforces the endpoint deny-list
  over `build/`, `ci/`, `DEPS`, `.github/workflows`.
- **SBOM:** `./scripts/build sbom` emits CycloneDX 1.6 (`docs/contracts/sbom-v1.md`);
  `./scripts/build sbom-gate` validates it.

## 8. What is NOT in this phase (human gates)

| Gate | What must happen |
|---|---|
| HG-9 | Real build farm bring-up (Linux/mac bare-metal, Win VMs) + runner registration |
| P2 DoD | 3-OS builds green nightly for 2 consecutive weeks |
| P2 DoD | External-rebuild proof: a contributor outside RRRTX reproduces a nightly per this doc |
| P10 | Real code-signing (current `sign_artifact.py` is test-cert scaffold, dev channel only) |
| HG-11 | Remote ccache endpoint sign-off (template only today) |
