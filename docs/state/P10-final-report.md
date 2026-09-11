# P10 FINAL REPORT — Update, signing & release engineering (exact ①–⑫ structure)

Phase: P10 · Repos: RRRTX-Labs/xr-browser @ `b766992` + RRRTX-Labs/xr-core @ `e2566bb`
Hosted CI at the final content SHA `acbcfc6`: **governance SUCCESS**, **core-hardening SUCCESS** (7/7 jobs). Governance re-confirmed SUCCESS at `b766992` (the report/evidence commit).

---

## ① T0 debts — all four

| debt | root cause | red before | green after |
|---|---|---|---|
| **T0-a** workflow pins/permissions/timeouts | `build/workflow_lint.py` validated YAML shape but never enforced `uses:` pinning by SHA, `permissions:` presence, or `timeout-minutes:` — an unpinned action or a runaway job passed the lint | `python3 build/workflow_lint.py --root .` on a planted unpinned workflow → FAIL (transcript `evidence/P10/logs/t0a-red-before.txt`) | same command green with the planted cases now rejected (`evidence/P10/logs/t0a-green-after.txt`); enforcement + 3 negative fixtures (ids 48–50) in `tools/negatives/p10_release.sh` |
| **T0-b** drill local-mode real execution | `drill_run.sh` had no hosts-local mode: the kill matrix was farm-only (P9 deferral), and the repo-root lane additionally died on a `$0`-relative ROOT bug (`build/qa/drill` is depth 3; relative `../..` double-resolved against the caller's cwd) | lane output: `python3: can't open file '.../build/tools/kill_matrix.py'` → FAIL | `bash build/qa/drill/drill_run.sh hosts-local` → **cells executed: 21 (kill iterations: 66), cells not-run: 10 (HG-33 farm, named)** `PASS: kill-matrix`; wired into run_checks (0-executed ⇒ FAIL) |
| **T0-c** mutation+fuzz lanes for the cores | governance/core-hardening had sampled mutation lanes for 3 cores only; no freshness gate tying scores to specific xr-core bytes; no update lane | `mutation_freshness.py` → "1 stale/missing of 5" FAIL (hosted run 34604887643) | full local matrices recorded: **commands 414/414 (100%), policy 777/777 (100%), settings 485/485 (100%), themes 386/386 (100%), update 414/415 (99.76% — sole survivor `backoff.cc:26` `>`→`>=` dispositioned equivalent)** in `docs/state/mutation-scores.json` + transcripts `evidence/P10/logs/t0c-mutation-*.json`; hosted lanes all SUCCESS (mutation-commands/settings/themes/update @ acbcfc6) |
| **T0-d** 400-LOC splits | `tools/evidence_check.py` (389) and `tools/gen_registry.py` (386) sat at the ceiling; any growth broke the law | `test_file_size_law` FAIL listing the offenders | splits: `evidence_check.py` 329 + `evidence_ci.py` 78; `gen_registry.py` 294 + `gen_registry_docs.py` 124; later splits kept the law green as T1/T0-c grew files (`update_vectors_kit.py` 51, `mutation_targets.py` 78); `./scripts/build test` 590 passed/2 skipped, LOC-law suite 212 passed |

## ② Research log — `docs/state/research-log-P10.md` (9 items)

1. `//chrome/updater` at the pin — **UNVERIFIED (deferred to P11+/farm)**: the pinned checkout is farm-side; our side of the boundary is specified (render-31, README-integration).
2. Protocol 3.1 conformance edges — **server side VERIFIED live** (51-case corpus); client delta/puffin **UNVERIFIED (P11)**; ≥60% size win not measured (recorded in docs/release/handbook.md limitations).
3. Signature/epoch model — **VERIFIED as our law** (TLS-independence tested, injected verifier, key-substitution deny); exact minisign artifact bytes **UNVERIFIED (P13/HG-36)** — no crypto invented; sigstore/rekor reachability **UNVERIFIED** (HG-38).
4. Per-platform signing reality — argv contracts **VERIFIED** (stub-tested, exact flags); EV/SmartScreen/notary lead times **UNVERIFIED (HG-37 procurement)**.
5. Cohort/rollout semantics — **VERIFIED as ours** (vectors + conformance boundaries); Chromium-internal rollout metadata at the pin **UNVERIFIED (P38)**.
6. Crash-halt input — **decision VERIFIED** (no-auto-halt until P38; policy.yaml + drill cell 10); in-tree crash services at the pin **UNVERIFIED (P38)**.
7. cargo vet from std-only — **VERIFIED**: zero crates by construction (`Cargo.toml` has no `[dependencies]`; `#![forbid(unsafe_code)]`); vet lane has nothing to vet.
8. Runner capabilities — **VERIFIED by an actual run**: `cargo 1.98.1 / rustc 1.98.1` on ubuntu-latest (run 34604887643, job 103280790981; transcript `evidence/P10/logs/research8-runner-probe.txt`); **no PyYAML** on hosted python (lane pins 6.0.3); `go` UNOBSERVED (no Go surface).
9. Key custody/HSM — **UNVERIFIED (HG-36 procurement)**: ceremony runbook names YubiKey-PIV class + cloud-HSM fallback; prices/terms deliberately not asserted.

Upstream symbols our code calls: **none** — `update/core/**`, the host, and the deployable are std-only (zero Chromium includes proven by `core_hygiene_check` across 5 cores/84 files); the only live external call in P10 tooling is the P3 allowlisted chromiumdash `fetch_releases` (cited in release/notes/train-152.md, fetched 2026-09-11).

## ③ T1–T9 — files, commits, status

| task | key files | commit(s) | status |
|---|---|---|---|
| T1 verifier core | xr-core `update/core/{manifest,verifier,verify_policy,epoch,cohort,backoff,seen}.{h,cc}`, `update/host/update_host.cc`, `update/tests/` (9 suites), `fakes/update.py`, `docs/contracts/vectors/update-v1.json`, `update/README-integration.md` | xr-core `50fcb5f`, `c16c963`, `e2566bb` | **real-in-ci** (mutation-update lane >=95 SUCCESS; vectors parity lane green) |
| T2 server trio | `release/server/spec/`, `refimpl/update_server_ref.py`, `rust/` (+ `tests/conformance.rs`), `docs/contracts/server-*.schema.json`, `tools/server_size_check.py`, `tools/gen_server_spec_rs.py` | (T2 set) + `8525bf0`, `acbcfc6` | **real-in-ci** (hosted 51/51 byte-exact, run acbcfc6) |
| T3 keys/ceremony | `release/keys/`, `tools/ceremony_check.py`, `tools/secret_scan.py` | (T3 set) + `8525bf0` | **real-in-ci** (secret_scan --all 786 files clean; ceremony_check PASS) |
| T4 signing | `build/signing/linux_repo_sign.py`, `platform_argv.py`, `build/signing/tests/test_signing_p10.sh` (14 cells), `release/pkg/packaging-matrix.yaml`, `tools/packaging_matrix_check.py` | (T4 set) | **local-real** (gpg REAL in sandbox) / mac+win **runner-ready** argv contracts / certs **human-gated HG-37** |
| T5 rollout | `release/rollout/policy.yaml`, `tools/rollout_drill.py` (10/10), `release/rollback/`, `docs/release/rollback-drill.md` | (T5 set) | **local-real** / 3-OS rehearsal **farm-runbook (HG-31/35)** / auto-rollout refused until P38 (tested refusal) |
| T6 transparency | `docs/contracts/release-attestation-v1.{md,schema.json}`, `tools/attest.py` (+pinned TEST-ONLY key), `release/notes/train-152.md`, `tools/release_notes.py`, `tools/claims_lint.py` | (T6 set) | **local-real** (emit+offline-verify+tamper-refusal) / publish **not-yet (HG-38; SKIP-77 visible)** |
| T7 SBOM/licenses | `build/sbom/{license_report,sbom_gate,emit_sbom}.py`, `evidence/P10/logs/t7-license-report.txt` | (T7 set) + `fccdb2d` | **real-in-ci** (license law negative reddens) |
| T8 About | xr-core `ui/about/about.ts`, `ui/shell.ts`, `l10n/xr_strings.grdp` (+18), `commands/core/roster_v1.json` (+3); xr-browser `tools/about_state_check.py`, coverage rows, webui-e2e | xr-core `f8b4cfe`; browser (T8 set) + `a236389` | **real-in-ci** (about-state gate + roster/menu goldens green hosted) |
| T9 release gate | `tools/release_gate.py` (8 lanes), `scripts/build release`, `tools/run_checks.sh` T9 lane, negative 55, `evidence/P10/logs/t9-leak-report.txt` (30 cells, 0 leaks) | (T9 set) + `9254696` | **real-in-ci** (dev GREEN 7/7; beta/stable proven non-zero) |

Nothing incomplete is silently carried: the open items are exactly the HG rows in ⑫.

## ④ Verifier evidence (T1)

- C++ suites (xr-core `update/tests`, `-std=c++20 -Werror`, make test): manifest **29/0**, verify_policy **15/0**, monotonic **5/0**, replay **15/0**, cohort **20/0**, backoff **11/0**, update_host **16/0**, golden **224/0**, update_fuzz **3/0** — `ALL C++ UPDATE TESTS PASSED`.
- Golden vectors: **73 cases** (>=60 required) at `docs/contracts/vectors/update-v1.json`; generator `--check` regenerates **byte-identical**; byte-parity harness: **73/73 identical** across update_host (C++) and fakes/update.py (Python), **both GN flag states** (`tools/update_vectors_check.py`: "byte-identical: 73/73 cases across update_host (C++) and fakes/update.py (Python)").
- Fuzz: local campaign **600 s, 21,543,776 iters, 0 violations** (`t1-update-fuzz-600s.txt`); hosted fleet policy/commands/settings/themes 600 s each **0 violations** (run acbcfc6).
- Mutation: **99.76%** (414/415), survivor `backoff.cc:26` `>`→`>=` dispositioned equivalent (both arms accept at the cap); deny-guard mutants 35/35 killed.
- TLS-independence matrix (test_verify_policy): bad-transport+good-sig ⇒ **accept**; good-transport+bad-sig ⇒ **deny**; unknown key ⇒ **kUnknownSigningKey deny**; expired/foreign epoch ⇒ deny; downgrade/equal-version ⇒ deny; replay ⇒ deny (SeenSet insert precedes accept).

## ⑤ Server evidence (T2)

- Conformance corpus: **51 cases**, reference backend green here (`test_conformance_ref.py`), Rust deployable **byte-exact hosted**: core-hardening run acbcfc6, job server-conformance → SUCCESS (`cargo test --locked` on rustc 1.98.1; first-compile fixes documented in `research8-runner-probe.txt`).
- Statelessness/no-persist: the refimpl writes nothing (stdio-JSON only; same request twice ⇒ identical bytes asserted in the corpus; spec render-31 §stateless).
- Response size: happy envelope **1379 B raw / 435 B gzip ≤ 2048 B** (`tools/server_size_check.py`).
- Unknown-field refusal at every level + canonical 400 `{detail,error}`: corpus-covered (kUnknownField).
- Log-scrub: P9 law re-asserted — no request datum is ever logged; the server keeps no state and no logs (docs/release/PRIVACY.md + corpus case).
- `#![forbid(unsafe_code)]`, zero crates (no `[dependencies]` section), std-only.

## ⑥ Signing evidence (T4/T3/T9)

- Linux repo signing REAL (sandbox gpg 2.4.7): clearsign InRelease → verify OK → **1-byte tamper ⇒ verification FAILED** → **wrong keyring ⇒ FAIL** → detached repomd round-trip. Missing-key cells SKIP-**77** visible. 14-cell transcript: `evidence/P10/logs/t4-signing-matrix.txt`.
- macOS/Windows: argv-exact stubs (codesign/notarytool/stapler, signtool /fd SHA256 /tr /td, osslsigncode) — `platform_argv.py --print` compared semantically (shlex).
- AppImage: XRUPDMETA1 round-trip + **tampered image refused**.
- Provider guard: release-channel packaging without `XR_SIGN_PROVIDER` ⇒ exit 1 REFUSED.
- `release check`: **dev GREEN (7/7 lanes)**; **beta exits non-zero** (enumerated: XR_SIGN_PROVIDER, train attestation, train leak); **stable exits non-zero** (same law) — run_checks T9 lane quotes both `ok:` lines and fails if they ever pass.
- secret_scan `--all`: **786 files across both repos, clean**; planted-key negative reddens; ceremony_check PASS.
- Needs a real credential: HG-36 (HSM ceremony), HG-37 (Apple Developer ID/EV cert/SmartScreen) — runbooks in `release/keys/ceremony.md` + `docs/release/signing-runbook.md`.

## ⑦ Rollout & rollback (T5)

- Cohort boundaries: bucket = sha256(install_id‖0x1f‖channel)[:8] BE, in-ramp iff bucket < percent; vectors 79/41/94 + conformance `beta-boundary-49-in`/`-50-out` pin the off-by-one.
- Halt-on-unknown: **no-auto-halt until P38** (`policy.yaml crash_hook`); dev-channel-only enforcement proven (drill cell 10).
- Epoch revocation drill: **10/10 cells** (`t5-rollout-drill.txt`) — serve+accept; downgrade-refused; replay-refused; ramp 49-in/50-out; revocation via signed notice; **revocation ⇒ manual_path deny**; stale-seq ignored; auto-rollout REFUSED (until P38); dev-only hook.
- Rollback = server-side revocation + client refuse-downgrade/replay; never auto-reversion (`release/rollback/rollback.md`).

## ⑧ Transparency, SBOM, notes (T6/T7)

- Attestation: `tools/attest.py --build` on the example dir → offline `--verify` PASS (pinned TEST-ONLY key, HG-36 swaps production); **1-hex subject tamper ⇒ rc=1**; `--publish` ⇒ **SKIP 77** (HG-38 — nothing published).
- License law: `sbom_gate.py --require-licenses` — planted NOASSERTION dep ⇒ **rc=1** (negative fixture); clean tree ⇒ PASS; report covers **18 evals, 1 rejected-not-shipped (boringtun), 0 unknown**; attached-SBOM licenses are SPDX-only tokens (eval prose stripped, refresh-in-place) — `t7-license-report.txt`.
- Notes: `train-152.md` with live chromiumdash fetch_releases rows (152.0.7977.85/.84, fetched 2026-09-11); CVE table carries an **honest UNVERIFIED row** (fetch_cve_notes returns HTML — recorded, not invented); `release_notes --check` diff-clean; claims_lint PASS (no unsupported superlatives).

## ⑨ Gates & regressions

- `bash tools/run_checks.sh`: **101 PASS lanes, EXIT=0** (P9 baseline 73) — evidence/P10/logs/run_checks.txt.
- `bash tools/run_negatives.sh`: **N=55, ALL REJECTED AS EXPECTED** (was 47).
- `./scripts/build test`: **590 passed, 2 skipped** — skips are the documented optional-external-tool rows (actionlint/shellcheck absent in sandbox; SKIP policy table printed, never silent).
- `evidence_check --strict`: **8 bundles, 0 failures**.
- Prior C++ cores: commands/policy/settings/themes suites green at the pin (make test; mutation lanes SUCCESS hosted).
- npm allowlist **35 packages, 0 violations**; license_audit PASS; sbom_gate (--require-licenses) PASS; fetch allowlist untouched (fetch.py ALLOWED_HOSTS unchanged — P10 adds `release/egress-allowlist.json` as separate reviewable data + `docs/release/egress.md`/`PRIVACY.md`).
- surfaces_check 15/0; about_state_check 7/7 states (+negative reddens); claims_lint PASS; workflow_lint PASS; egress policy documented (the `egress_policy_check` lane is the release-gate egress row reading the allowlist).

## ⑩ CI + repo state

- `ls-remote`: xr-browser/main = **b7669920e** (= local HEAD `b766992`), xr-core/main = **e2566bb91** (= local HEAD `e2566bb`). Both equal; trees clean (`git status --short` = 0 both).
- DCO: every P10 commit `Signed-off-by: XR P10 Agent <p10-agent@users.noreply.github.com>` (`dco_check` PASS; 32 P10-agent commits in xr-browser's history).
- Hosted runs at final content SHA `acbcfc6`: **governance SUCCESS** (steps: Governance checks ✓, Workflow lint ✓, Negative fixtures ✓, Build-system gates ✓, Contract-freeze ✓, Mutation freshness ✓, Policy gates ✓, Treadmill ✓); **core-hardening SUCCESS** (freshness ✓, mutation-{settings,themes,commands,update} ✓, server-conformance ✓, fuzz-fleet ×4 ✓). `governance` re-confirmed SUCCESS at `b766992`.
- `nightly-rebase-build`: last run SUCCESS (P9-era head; cron-driven).
- `check-pin-alive`: PASS (DEPS `xr_core_rev = e2566bb…` reachable on origin).
- `git diff` on `docs/contracts/FROZEN.yaml` + `docs/contracts/INDEX.md`: **empty**; sha256 (head): FROZEN `0b79e43988f31df4…`, INDEX `7225489169944e38…`.
- Patch manifest: **unchanged by P10** (About page consumed no patch budget — the P7 farm-glue deferral pattern; count as at P9 close).
- `git log --oneline` (P10 window, xr-browser, oldest→newest): 1c533dd, 06d7e0f, 9d7c27c, bf494a6 (T0) · e954f98 (T1 vectors) · 9bb19c8 (T2) · T3/T4/T5/T6/T7/T8 sets · 0303d41, a236389, fccdb2d, 1e99be1, 68457a5, c73679b, a1ac989, 8525bf0, 860578d, 08a782f, 9254696, a223d8e, 8fadb0e, b7639a6, 1e769c4, 1856556, acbcfc6, **b766992** (this report). xr-core: 50fcb5f, c16c9631, f8b4cfe, e2566bb.

## ⑪ DoD 1–15 — `evidence/P10/evidence.json` (15 rows; `evidence_check --strict` PASS)

| row | status | proving artifact |
|---|---|---|
| DOD-0a workflow-pin enforcement | VERIFIED | `evidence/P10/logs/t0a-green-after.txt` (+red-before) |
| DOD-0b hosts-local drill | VERIFIED | `evidence/P10/logs/t0b-drill-hosts-local.txt` (21 cells executed) |
| DOD-0c mutation freshness | VERIFIED | `evidence/P10/logs/t0c-mutation-*.json` + `docs/state/mutation-scores.json` |
| DOD-0d 400-LOC splits | VERIFIED | `evidence/P10/logs/t0d-file-splits.txt` + `build/tests/test_file_size_law.py` green |
| DOD-1 verifier core | VERIFIED | xr-core `update/tests` (9 suites, 0 failures) + `docs/contracts/vectors/update-v1.json` + `t1-update-fuzz-600s.txt` |
| DOD-2 server trio | VERIFIED | `release/server/` + hosted run acbcfc6 (rustc 1.98.1, 51/51) + `t2-server-fuzz-600s.txt` |
| DOD-3 keys/ceremony | VERIFIED | `release/keys/` + `tools/secret_scan.py --all` (786 files clean) |
| DOD-4 signing | VERIFIED | `evidence/P10/logs/t4-signing-matrix.txt` (14 cells) |
| DOD-5 rollout | VERIFIED | `release/rollout/policy.yaml` + `t5-rollout-drill.txt` (10/10) |
| DOD-6 attestation | VERIFIED | `release/transparency/attestation-example.json` + `tools/attest.py` (tamper ⇒ FAIL) |
| DOD-7 license law | VERIFIED | `build/sbom/license_report.py` + `t7-license-report.txt` |
| DOD-8 About | VERIFIED | xr-core `ui/about/about.ts` + `tools/about_state_check.py` (7/7; negative reddens) |
| DOD-9 release gate | VERIFIED | `tools/release_gate.py` + negative 55 (beta/stable non-zero) |
| DOD-10 research log | VERIFIED | `docs/state/research-log-P10.md` (9 items) |
| DOD-11 runner probe | VERIFIED | `evidence/P10/logs/research8-runner-probe.txt` (cargo/rustc 1.98.1 observed, run 34604887643) |

## ⑫ Deviations, open RFCs, human gates, P11+ inheritance

**Deviations (each with its recorded reason):** (1) the hosted CI hardening produced 8 additional fix-forward commits (8525bf0…b766992) beyond the planned T-set cadence — every one diagnosed from the run's own logs, no fake greens; (2) `fuzz_fleet.py` gained `--only` (CI matrix mode) and FAIL-on-stderr — additive, the 600 s/target law unchanged; (3) commit `08a782f`'s message contains a harmless `$0` expansion ("absolute /bin/bash dir") — wording only, not amended (no history rewrites); (4) the commands mutation matrix was re-run at `e2566bb` (roster data change) with an unchanged mutant set (414) — the freshness law demanded the fresh transcript.
**Frozen consumption:** `FROZEN.yaml`/`INDEX.md` untouched (diff empty, hashes above); the six new P10 living contracts are registered in `docs/contracts/registry-post-freeze.md` (P10 section); frozen update-manifest schema untouched; P1–P9 evidence untouched (P10 bundle is append-only, `supersedes: evidence/P9`).
**Human gates:** HG-1 (legal briefs before any real release), **HG-36** key ceremony + HSM (runbook `release/keys/ceremony.md`), **HG-37** certificates/notarization/SmartScreen (`docs/release/signing-runbook.md`), **HG-38** update-server hosting + egress approval (`release/egress-allowlist.json` review), **HG-20** PAT revocation re-flag (user-owned; zero token occurrences in trees/history — final sweep clean), **HG-26** ratification now FIVE consumers deep (P6 policy, P7 command-descriptor, P8 settings/theme, P9 evidence format, P10 update-manifest + the six new P10 contracts) — **recommendation: ratify-or-amend in one batch before P11**, HG-31/35 (three-OS farm rows incl. the 10-cell kill matrix), HG-28 (24 h full-mutation fleet cadence), HG-34 (branch protection — now gates a release pipeline).
**Exact hand-off commands:** **P11** (list updates ride component-updater): configure the CRX/registration row in `docs/release/updater-integration.md` + `xr_updater_v0` flag flip (`xr-core/BUILD.gn`, gclient setparser `xr_updater_v0=true`) once `//chrome/updater` is checked out at the pin (research item 1). **P13** (breakage-report channel): `xr://client-status` reports to `updates.rrrtx.labs/status` (add to the egress allowlist via HG-38 review, never by editing `fetch.py`). **P16** (dev-only exit): remove the `dev-only-until-P16-exit` wall in `update/core/verify_policy.cc` + flip `release/server/spec/channels.yaml` nightly ramp — the vectors already cover both flag states. **P38** (telemetry → halt hook): implement `crash_hook` per `release/rollout/policy.yaml`'s `on_absent_input` seam; the drill's cell 10 assertion is the acceptance test. **P39** (external rebuild reconciliation): diff `docs/contracts/release-attestation-v1` subjects against independently rebuilt artifacts; `tools/attest.py --check-inclusion` is the waiting seam.
**Debt deliberately left:** delta-update size measurement (P11+, needs the pinned client); minisign exact bytes (HG-36); `go`-on-runner observation (no Go surface exists); the `/tmp` hygiene nit (pytest-of-user accumulation can fill small tmpfs — noted for long local runs).
