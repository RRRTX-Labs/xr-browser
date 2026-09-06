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

## R5..R14 — PENDING (logged as each deliverable is built)

| Key | Research item | Planned primary source (URL) | Status |
|---|---|---|---|
| R5  | #1 depot_tools/gclient usage + DEPS format + `gclient sync --revision` | chromium.googlesource.com/chromium/src/+/main/docs/linux_build_instructions.md, docs/DEPS_file.md | PENDING |
| R6  | #3 GN args existence in pinned rev (every argset flag cited to file:line) | source.chromium.org `build/config/…BUILD.gn` at pinned SHA | PENDING |
| R7  | #4 Brave overlay precedent (mount mechanics, `.gn` secondary root) | github.com/brave/brave-core (README, `brave/.gn`, `brave/DEPS`) | PENDING |
| R8  | #5 caching: ccache vs sccache + `cc_wrapper`/reclient | chromium docs/rbe.md, build/README.md; ccache.dev / github.com/mozilla/sccache | PENDING |
| R9  | #6 toolchain pins (clang version, sysroots, SDK policy) | tools/clang/scripts/update.py --print-version; build/linux/*sysroot*; build/toolchain/win/toolchain.py | PENDING |
| R10 | #7 SBOM CycloneDX 1.6 schema + `gn desc` semantics | cyclonedx.org/schema/bom-1.6.schema.json | PENDING |
| R11 | #8 branding/de-branding (GRD structure, PRODUCT_NAME mechanics) | chromium.org For Developers licensing; pinned rev chrome/app/* | PENDING |
| R12 | #9 signing scaffold: minisign vs sigstore/cosign choice | jedisct1/minisign; docs.sigstore.dev | PENDING → ADR-0004 |
| R13 | #10 GitHub Actions self-hosted runner docs + pinned action SHAs | docs.github.com actions/hosting-and-maintaining | PENDING |
| R14 | #2 live pinned-versions follow-up (next stable refresh date) | chromiumdash.appspot.com/releases | PENDING |
