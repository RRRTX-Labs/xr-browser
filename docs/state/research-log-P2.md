# Research log — P2 (build system & hermetic Chromium build)

Every entry records **URL + date + verbatim quote**. Anything unreachable or
unverifiable is marked **UNVERIFIED** — never guessed (Plan L24, L5).
Research baseline date: **2026-09-07** (Asia/Karachi).

Items below are keyed R1..R14; the mapping to the phase's "RESEARCH REQUIRED"
list is noted. Entries still in flight are marked PENDING and get their
quote logged the moment the deliverable that consumes them is built.

---

## R1 — Chromium stable pin (VERIFIED, live)  — research item #2

**URL:** `https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Linux&num=3`
**Date:** 2026-09-07

**Quote (top result):**
```json
{"channel":"Stable","chromium_main_branch_position":1669021,
 "hashes":{"angle":"7df613367a1d4ca9aea9ece344d4580d32d132a9",
           "chromium":"d04cdb24d67b081f6cf80200ffc5233f44b61109",
           "dawn":"ab8827bc57b176eeaa89f71324130c02d4d41145",
           "devtools":"04db1f5240b636511ec4e9058a78f8274a7f65ee",
           "pdfium":"8f3e90282ef137adf7d380079c3178b24407104a",
           "skia":"0873ec164a06966b90ae0d43ef783cfb180084ae",
           "v8":"4323497a6a73839e6d5260f6acd7ec0212cb3321",
           "webrtc":"6f37672d358475cd17544121a12494da454d85fb"},
 "milestone":152,"platform":"Linux","previous_version":"152.0.7977.75",
 "version":"152.0.7977.82"}
```

**Cross-check (tag → git SHA), URL:**
`https://chromium.googlesource.com/chromium/src/+/refs/tags/152.0.7977.82?format=JSON`
**Quote:** `"commit": "d04cdb24d67b081f6cf80200ffc5233f44b61109"` (committer
`Chromium LUCI CQ`, Wed Sep 02 20:40:03 2026).

**PIN (single source of truth → `DEPS`):**
- milestone **152**, version **152.0.7977.82**, branch position 1669021
- chromium git SHA **`d04cdb24d67b081f6cf80200ffc5233f44b61109`**
- sub-revs (v8/skia/webrtc/angle/dawn/pdfium/devtools) are informational
  only — the chosen Chromium DEPS already pins them; we do **not** re-pin
  inside pins (Plan R2 note).

## R2 — depot_tools HEAD observed (live)  — research item #1 (support)

**URL:** `https://chromium.googlesource.com/chromium/tools/depot_tools.git`
**Date:** 2026-09-07
**Quote:** `git ls-remote HEAD → 81577f19a8497ba7e41afac322e8f03553a863ec`
(depot_tools is fetched at runtime, not vendored; BSD-3 → mini-eval
`docs/dependencies/depot-tools.yaml`).

## R3 — xr-core availability  — T0 gate

**URL:** `https://api.github.com/repos/RRRTX-Labs/xr-core`
**Date:** 2026-09-07
**Quote:** `{"message": "Not Found", "status": "404"}`
**URL:** `https://api.github.com/orgs/RRRTX-Labs/repos?per_page=100`
**Quote:** only `xr-browser` listed (private=false); no `xr-core`.
**Verdict:** **UNVERIFIED / UNAVAILABLE** from this environment. The repo
exists in the operator's hands (`xr-core-phase1.zip`, HEAD `6fb5411b…`). T0
is blocked until it is provided (stop condition per Failure #1).

## R4 — Environment capability probe  — verification-plan input

See `evidence/P2/env-probe.txt` (raw). Summary: 2 vCPU / 1.9 GiB RAM /
20 GB free disk → L2+ infeasible; L1 is the honest ceiling for this workspace.

## R5..R14 — RESOLVED (consumed by the deliverables they fed)

Each research item below was consumed by a built P2 artifact (committed
2026-09-07). Primary-source quotes are cited inside the consuming artifact's
own README/citations; only the items with a verbatim quote captured this
session (R15/R16) are quoted in full here.

| Key | Research item | Consumed by |
|---|---|---|
| R5  | gclient/DEPS format + `--revision` sync | `buildsys/sync.py` (gclient synthesis) + `docs/contracts/deps-pin-policy.md` + `docs/dependencies/depot-tools.yaml` |
| R6  | GN args existence in pinned rev | `buildsys/gn/argsets/flags.yaml` (`read_at` citations per flag) |
| R7  | Brave overlay mount precedent | `buildsys/sync.py` (xr-core mount at `src/xr` via `custom_deps`) |
| R8  | ccache vs sccache choice | `buildsys/farm/caching.md` (ADR-0005: ccache local-first, remote human-gated) |
| R9  | toolchain pins (clang/sysroot/SDK) | `buildsys/toolchain/pins.json` + `provenance.py` |
| R10 | CycloneDX 1.6 schema | `buildsys/sbom/cyclonedx-schema-1.6.json` (vendored) + `docs/contracts/sbom-v1.md` |
| R11 | branding/de-branding mechanics | `buildsys/branding/` + xr-core `patches/branding/0001-brand-ui/` |
| R12 | signing scaffold choice (minisign) | `buildsys/signing/README.md` (ADR-0004 context) |
| R13 | GHA self-hosted runners + pinned SHAs | `docs/process/pinned-actions.md` + `ci/*.yml` |
| R14 | live pinned-versions follow-up | recurring — next stable refresh date is the P3 refresh lane's job |

## R15 — clang Linux artifact URL + digest capture (VERIFIED, live)

**Source:** `tools/clang/scripts/update.py` at the pin (`d04cdb24…`), line 226.
**URL:** `https://commondatastorage.googleapis.com/chromium-browser-clang/Linux_x64/clang-llvmorg-23-init-19482-g53d18800-1.tar.xz`
**Date:** 2026-09-07
**Quote:** `cds_file = "%s-%s.tar.xz" % (package_file, version)` (so the
extension is `.tar.xz`, not `.tgz` — the earlier `.tgz` guess 404s).
**Capture:** `provenance.py --record` downloaded the tarball and recorded
sha256 `e22e06c05fe1657f48f988b15804b8226e691addb00abba5b984a5c99ac98c42`
into `pins.json` (`linux_artifact_sha256`; `PENDING-CAPTURE` cleared).

## R16 — sysroot download is content-addressed (VERIFIED, live)

**Source:** `build/linux/sysroot_scripts/install-sysroot.py` at the pin.
**Date:** 2026-09-07
**Quote:** `url = "%s/%s" % (url_prefix, tarball_sha256sum)` — i.e. the
sysroot tarball URL is `https://commondatastorage.googleapis.com/chrome-linux-sysroot/<sha256>`,
not a `…/toolchain/<hash>/…` path.
**Verification:** the amd64 sysroot was fetched at that content-addressed URL
and re-hashed to `52d61d44…652e1d`, matching the pinned `sysroots.json`
digest (`sysroot_amd64_verified: true`). `provenance.py --record` previously
hardcoded an invalid `toolchain/2a2ea4ce…` bucket (404) — fixed to the
content-addressed scheme.
