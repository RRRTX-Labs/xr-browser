# PHASE 2 RELEASE — XR Browser (RRRTX Labs)

- **Phase:** P2 — Build system & hermetic Chromium build (Plan Stage 0)
- **Release prep date:** 2026-09-07
- **Brand:** RRRTX Labs
- **Target GitHub home:** `github.com/RRRTX-Labs/xr-browser`, `github.com/RRRTX-Labs/xr-core`
  (remotes already configured — push commands in §6)
- **Packages:** `xr-browser-phase2.zip`, `xr-core-phase2.zip` (§6)

---

## 1. Final repo state

| | xr-browser (meta) | xr-core (product) |
|---|---|---|
| Branch | `main` | `main` |
| Commits at packaging | 30 total (18 P1 + **12 P2**: `0ba6859…` → HEAD at packaging, §2) | 4 total (3 P1 + **1 P2**: `6416bf1…`) |
| License | MPL-2.0 (canonical verbatim, unchanged from P1) | same file, same hash |
| Working tree | clean (`git status` empty) | clean |
| Untracked/temp files | none (caches removed, gitignored anyway) | none |
| Secrets/credentials | **none** — scan for private keys/tokens/API keys returned nothing; only RFC 2606 placeholders (`@rrrtx.example`, `@xr/*`, `update.xr.example`) | same |
| Contents added in P2 | `DEPS` (chromium pin `d04cdb24…` = 152.0.7977.82), `build` (dispatcher), `buildsys/` (sync/preflight/net-audit, `gn/` argsets+gen+compile, `patching/` manifest applicator, `farm/` budget+ccache+runners, `toolchain/` pins+provenance, `branding/`, `signing/`, `sbom/`), `ci/build-lane.yml` + `ci/nightly-rebase-build.yml`, `docs/contracts/` (deps-pin-policy, patch-manifest-v1, sbom-v1), `BUILDING.md`, `evidence/P2/` | `patches/manifest.yaml` (schema v1) + `patches/branding/0001-brand-ui/` (0001-brand-ui.patch + patchinfo.md) |
| Scope boundary | build machinery + its checks + CI definitions + P2 evidence; **no product source** beyond the one branding patch (anti-stub rule) | patch manifest + one branding patch only |

**Pinned plan (v2):** `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` — unchanged from P1 (sha256 `02743146…65a7b`), verified by `plan_pin_check`.

## 2. Exact commit hashes

**xr-browser — P2 commits** (oldest → newest, all on `main`; every commit DCO-signed):

| # | SHA | Subject |
|---|---|---|
| T0 | `0ba6859769f81b2ca0c7db0eac02905f457b06bf` | docs(state): P2 research log + environment probe (XR-P2-T0) |
| T1 | `c2a578eb47c6ad26350877e84f611c91f888d4b9` | build(deps): DEPS pin + sync/refresh/preflight + deps-pin-policy (XR-P2-T1) |
| T2 | `d3ab1d63acdc9caed05a5d651d294d594a6194b8` | build(gn): XR argsets + resolver + gen/compile (XR-P2-T2) |
| T3 | `bb492ff2004b668d18045093e65e4988fcf2fc57` | build(patching): patch-manifest contract + xr-patch tooling (XR-P2-T3) |
| T4 | `b76a531ec3e10750d212ab5eefdd13e1d9eab62d` | build(farm): budget meter + ccache provisioning + CI lanes (XR-P2-T4) |
| T5 | `917156d351f230abf3233dbf564f83b226a9c180` | build(toolchain): pins.json + provenance verify/record (XR-P2-T5) |
| T6 | `28927eb1f3d29cfccfcb736ed9e67bd5d9ede44e` | build(branding): version gen + brand check + interim icons (XR-P2-T6) |
| T7/T8 | `91525422ae9d65c05e8405034a849ff29b10615b` | build(signing): TEST-ONLY signing scaffold (XR-P2-T7/T8) |
| T9 | `0379721e49cf9baf4d03bdbef3113a6f33d9c887` | build(sbom): CycloneDX 1.6 emitter + gate + contract (XR-P2-T9) |
| suite | `d04e12f7e4111ec332d4eb4d657f1e1e5f59bcb9` | build: ./build dispatcher + cross-tool test suite (XR-P2-T12) |
| release | `4d1c26e05b2d30bc4072af8a57e86fe433245c95` | build: P2 release fixes — capture pins, fix URLs, add build docs (XR-P2-T5/T7) |
| release | *(this commit — HEAD at packaging; `git log -1` inside the ZIP)* | release: PHASE2_RELEASE.md + P2 evidence bundle (XR-P2 release prep) |

*(The "T12" tag on the dispatcher commit is a local suite label; the plan's P2
task list is T1–T10 — the dispatcher + tests are the cross-cutting "Tests" DoD
support, not an extra task.)*

**xr-core** (oldest → newest):

| # | SHA | Subject |
|---|---|---|
| 1..3 | `0050c53…`, `22922d8…`, `6fb5411…` | P1 (unchanged) |
| 4 | `6416bf16a47f53b616d38b8cc6172633c5f3c8b9` | build(patches): branding patch 0001 + patch manifest (XR-P2-T3) |

## 3. Verification results (all executed 2026-09-07; logs in `evidence/P2/logs/`)

**Governance gate** (`tools/run_checks.sh`): all PASS — `plan_pin_check`,
`registry_lint`, `dr_parse`, `dr_parse --check-trailers`, `license_audit`,
`dco_check`, `check_threat_model`, `vocab_lint`, `owners_sync` — **55/55
tests**. Negative fixtures (`tools/run_negatives.sh`): **7/7 rejected**.

**Build-system gate** (also wired into `.github/workflows/governance.yml`):

| Command | Result |
|---|---|
| `./build test` (tools + buildsys suites) | **90/90 passed** |
| `python3 buildsys/toolchain/provenance.py --verify` | PASS (clang sha captured, `pending_capture: false`) |
| `./build brand-check --scan` | PASS (0 hits over buildsys/ci/DEPS/.github) |
| `python3 buildsys/gn/resolve_args.py --validate` | PASS (all argsets allowlisted) |
| `./build budget --json` | 1/150 patches, no overage |
| `./build version --json` | `152.0.7977.82` (dev) |
| `./build sbom --fixture` + `./build sbom-gate` | SBOM validates against vendored CycloneDX 1.6 schema |

**Mock pipeline** (no checkout; `XR_ALLOW_MOCK=1 ./build --mock …`):
`sync → gen → compile → sbom → sign` all PASS with `MOCK MODE — not a build`
on every line.

**Real patch roundtrip** (`evidence/P2/logs/patch-roundtrip.txt`): the xr-core
branding patch `git apply --check`-ed cleanly and applied/verified/reverted
via `xr-patch` against the **actual pinned Chromium files**
(`chrome/app/theme/chromium/BRANDING`, `chrome/app/chromium_strings.grd`,
fetched at `d04cdb24…`); post-revert diff == pinned pre-image.

**Toolchain capture** (`provenance.py --record`, executed): clang Linux
artifact downloaded from the pinned URL and hashed to
`e22e06c0…c98c42`; amd64 sysroot re-fetched at its content-addressed URL and
re-hashed to match the pinned `52d61d44…652e1d`. No digest is typed from
memory.

**Preflight (behavioral gate):** on this sandbox `./build preflight` correctly
**REFUSES** (2 vCPU / 2.08 GB RAM / 21.2 GB free vs ~240 GB estimate) rather
than simulating checkout state — the P2-T1 gate working as designed, and the
reason a real `sync`+`compile` could not run here.

## 4. Important fixes in this pass

| # | Fix |
|---|---|
| F1 | **clang URL extension:** `pins.json` recorded `….tar.xz` wrongly as `….tgz` (the `.tgz` 404s). Corrected to `.tar.xz` per pinned `update.py:226` (`cds_file = "%s-%s.tar.xz"`). |
| F2 | **Sysroot URL scheme:** `provenance.py --record` hardcoded a `…/toolchain/<hash>/…` bucket that 404s. Pinned `install-sysroot.py` shows the scheme is content-addressed (`url = URL + '/' + Sha256Sum`); fixed, added `sysroot_url_base` to `pins.json`. |
| F3 | **PENDING-CAPTURE cleared:** `clang.linux_artifact_sha256` captured from the fetched artifact (`e22e06c0…c98c42`); amd64 sysroot digest re-verified against the pinned tree. |
| F4 | **brand-check scan hygiene:** `--scan` now skips `tests/` (negative fixtures legitimately carry deny-strings) and `__pycache__`; previously the tool tripped on its own test corpus. |
| F5 | **Stale status docs:** README ("P2 has not started"), `repo-map.md`, `ci/README.md` updated to the real P2 state — build system implemented, not stubbed. |
| F6 | **BUILDING.md** added (plan T7 "build docs exact enough for external rebuild") — the missing P2 artifact. |
| F7 | **Research log:** R5–R14 marked consumed by their artifacts; R15 (clang capture) + R16 (content-addressed sysroot) recorded with quotes. |
| F8 | **CI:** added the P2 build-system gate step to `governance.yml`. |

## 5. Known limitations & human gates

**DoD (plan P2):**

| DoD | Status |
|---|---|
| 3-OS builds green nightly for 2 consecutive weeks | **HUMAN-GATED** — needs the real build farm (HG-9); `ci/nightly-rebase-build.yml` defines the matrix |
| External-rebuild proof filed | **HUMAN-GATED** — `BUILDING.md` written + mock-verified; an outside contributor must execute it and record time-to-first-build |
| SBOM published on dev channel | **TOOL-READY** — emitter + gate verified; publication needs a real build + dev-channel release |

**Gates:**

| Gate | What must happen | Owner (placeholder) |
|---|---|---|
| HG-9 | Build-farm bring-up + runner registration (Linux/mac bare-metal, Win VMs) | RRRTX-OPS-02 |
| HG-11 | Remote ccache endpoint sign-off (template only today) | RRRTX-OPS-02 |
| P10 | Real code-signing certs (`sign_artifact.py` is test-scaffold, dev/nightly-test only) | RRRTX-PLATFORM-LEAD |
| DR-14 / LG-3 | Widevine CDM verdict stays open — `enable_widevine=false` is the committed default; flipping it requires a counsel verdict + register change | RRRTX-LEGAL-01 |

**Not done (by design, recorded):**

- Real `./build sync` + `./build compile` — this sandbox is under-provisioned
  and `preflight` refuses it; runs on the HG-9 farm.
- Component-updater *positive* endpoint rewrite (plan T2's "endpoints → XR dev
  URL") — not a GN arg; the defensive deny-scan (`brand-check --scan`) is in
  place, the positive rewrite lands with the updater work (P10) or a dedicated
  de-Google patch.
- Bit-stability of two same-input builds — needs real builds (R4: chromium-wide
  determinism is never promised).

## 6. Packages & verification commands

| Package | Contents |
|---|---|
| `xr-browser-phase2.zip` | complete `xr-browser` repo at the release HEAD (§2), **including `.git`** (full history + DCO), no untracked files |
| `xr-core-phase2.zip` | complete `xr-core` repo at `6416bf1…`, including `.git`, no untracked files |

Reproducible verification (any machine with git + Python 3.12):

```sh
unzip xr-browser-phase2.zip && unzip xr-core-phase2.zip

# integrity
git -C xr-browser log --oneline -3     # top = PHASE2_RELEASE.md commit (HEAD at packaging)
git -C xr-core    log --oneline -3     # top = 6416bf1 (branding patch + manifest)
git -C xr-browser status --short       # (empty)
git -C xr-core    status --short       # (empty)

# governance + build gates in the extracted meta repo
cd xr-browser
pip install --require-hashes -r tools/requirements-dev.txt
tools/run_checks.sh                    # 9 gates + 55 tests — "ALL GOVERNANCE CHECKS PASSED"
tools/run_negatives.sh                 # "ALL NEGATIVE CASES REJECTED AS EXPECTED"
./build test                           # 90 passed
python3 buildsys/toolchain/provenance.py --verify   # pass, pending_capture=false
./build brand-check --scan             # pass (0 hits)
python3 buildsys/gn/resolve_args.py --validate      # pass
```

### Git Bash — push commands (run from a machine with push access)

Your remotes already point at the real org (no placeholder to replace):

```bash
# ---- xr-browser ----
cd /path/to/xr-browser
git status                                   # expect: clean, "up to date" only if already pushed
git remote -v                                # origin https://github.com/RRRTX-Labs/xr-browser.git
git branch --show-current                    # main
git log --oneline -3                         # top = 4d1c26e
git push origin main                         # pushes the 11 P2 commits

# ---- xr-core ----
cd /path/to/xr-core
git status
git remote -v                                # origin https://github.com/RRRTX-Labs/xr-core.git
git branch --show-current                    # main
git log --oneline -2                         # top = 6416bf1
git push origin main                         # pushes the 1 P2 commit

# ---- verify after push ----
git -C /path/to/xr-browser fetch origin && git -C /path/to/xr-browser status -sb   # "up to date with origin/main"
git -C /path/to/xr-core    fetch origin && git -C /path/to/xr-core    status -sb
```

No `git add`/`git commit` is needed — everything is committed with DCO
sign-off; if `git status` shows anything untracked/modified on your machine,
do **not** commit it without review (the ZIPs are the clean source of truth).
