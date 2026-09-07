# Repository map (P2 state, with P3/P4 deltas appended below)

Plan §7.1 topology: **two repos + helpers**, deliberately not a sprawl.
This map records what exists at P2 close and where each planned surface
will land, so nobody builds in the wrong place.

## xr-browser (this repo — meta: build, release, governance)

| Path | Status at P1 | Contents |
|---|---|---|
| `LICENSE`, `README.md`, `CONTRIBUTING.md`, `.gitignore`, `.editorconfig` | ✅ committed | repo root artifacts (MPL-2.0) |
| `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` | ✅ pinned | the plan, SHA-256-pinned (`docs/master-plan.sha256`) |
| `docs/adr/` | ✅ | template, 0001 (topology/licensing), 0002 (register procedure), RESERVED.md |
| `docs/register/decisions.yaml` | ✅ | DR-01..DR-30, machine-checked (`tools/dr_parse.py`) |
| `docs/registry/` | ✅ | features.yaml (122 rows), reserved-interfaces.yaml (6), COUNTS.json — generated from the plan |
| `docs/legal/` | ✅ | LG-1/LG-2/LG-3 briefs (DRAFT-FOR-COUNSEL, verdicts blank) |
| `docs/dependencies/` | ✅ | L9 eval template + 12 evals for every §8 INTEGRATE row |
| `docs/threat-model.md` | ✅ | v0, structural-gated (`tools/check_threat_model.py`) |
| `docs/limitations.md` | ✅ | published-limitations surface (Isolation Card source) |
| `docs/process/` | ✅ | ADR procedure, disclosure, bounty v0, plan-amendment, s0-paths (S0/S1 source of truth) |
| `docs/state/` | ✅ | repo-map (this file), assumptions, research-log-P1, allowlists |
| `tools/` | ✅ | the 9 governance tools + tests + negative corpus + run scripts + DEPS.md |
| `.github/workflows/governance.yml` | ✅ → P4 patched | CI definition (actions pinned by full SHA); P4-T0.1 fixed the 404 clone URL and installed `minisign` |
| `evidence/P1/` | ✅ | evidence.json, human-gates.md, logs/, research-log-links.txt, registry-recount.md |
| `build` | ✅ P2 → P4 `spike` | the `./build` entrypoint dispatcher (sync/gen/compile/patch/sbom/brand-check/sign/budget/test/**spike**) |
| `build/` | ✅ P2 | `_common.py` (tool contract), `sync.py`, `preflight.py`, `net-audit.md`, `gn/` (argsets + resolve + gen/compile), `patching/` (manifest applicator), `farm/` (budget/ccache/runners), `toolchain/` (pins + provenance), `branding/` (version/brand-check/icons), `signing/` (test scaffold), `sbom/` (emit/gate/schema), tests |
| `ci/` | ✅ P2 | README + `build-lane.yml` (PR compile lane) + `nightly-rebase-build.yml` (3-OS matrix definition; not yet running — HG-9) |
| `docs/contracts/` | ✅ P2/P4 | `deps-pin-policy.md`, `patch-manifest-v1.md`, `sbom-v1.md`, `evidence-bundle-v1.md`, **`spike-result-v1.md`** (P4; the spike-result row shape shared with the future isolation matrix; the P5 IDL contracts will join later) |
| `docs/spike-identity/` | ✅ P4 | `measured-shared-state.md` (23 citation-verified rows), `papercut-census.md` (15 rows), `probe-matrix.md` (probes ↔ adversaries ↔ future iso-matrix ids), `fallback-design.md` (BrowserContext fallback + P14 registry impact) |

## xr-core (product — `//xr` inside the overlay; MPL-2.0)

| Path | Status at P1 | Contents |
|---|---|---|
| `LICENSE`, `README.md`, `CONTRIBUTING.md`, `.gitignore`, `.clang-format` | ✅ | repo root artifacts |
| `CODEOWNERS`, `OWNERS` | ✅ | S0 path protection (placeholder handles until HG-3) |
| `mojom/`, `policy/`, `identity/`, `net/`, `vault/`, `extensions/` | 📋 planned | S0 product surfaces — **do not create stubs now** (P4/P5+; anti-stub rule, plan §0.4/L5). `mojom/` freezes at P5. `policy/` landed at P6 (resolver core); the rest stay planned. |
| `patches/` | ✅ P2 | `manifest.yaml` (schema v1) + `branding/0001-brand-ui/` (patch + patchinfo) |

## Helpers (not yet created)

- `xr-fakes` fixtures live inside xr-core (`//xr/fakes/`) per plan §7.1 — no separate repo.
- Build-farm artifacts (P2) and the update server (P10) are ops infrastructure, not repos.

## Guardrail summary (what CI enforces today)

| Gate | Tool | Protects |
|---|---|---|
| Plan integrity | `plan_pin_check.py` | the single source of truth |
| Registry integrity | `registry_lint.py` | "no feature exists outside the registry" |
| Register integrity | `dr_parse.py` (+trailers) | DR-xx schema + change discipline |
| License integrity | `license_audit.py` | canonical MPL-2.0 + no copyleft code |
| Contribution integrity | `dco_check.py` | DCO signoff |
| Threat-model integrity | `check_threat_model.py` | T1–T11 honesty column, plan binding |
| Claims discipline | `vocab_lint.py` | banned-claims vocabulary (§0.3/§9.11) |
| Ownership sync | `owners_sync.py` | CODEOWNERS/OWNERS ↔ s0-paths.yaml |
| Negative proof | `run_negatives.sh` | the gates themselves |


## P4 delta — new and changed paths

### xr-browser (meta)

| Path | Change | Contents |
|---|---|---|
| `docs/adr/0042-identity-seam.md` | ✅ new, **PROPOSED** | the identity-seam ADR: decision, 7 falsification triggers F1–F7, patch-estimate table vs §1.2 caps, 9 attacker-observable rows, contingency clause, P5 drafting notes. Ratification is HG-23. |
| `docs/adr/RESERVED.md` | ✏️ edited | row 0042 flipped RESERVED → IN USE (number never reused) |
| `docs/adr/draft-issue-0002-p3-deviations.md` | ✏️ edited | §5 dispositions filled: all three deviations ACCEPTED |
| `docs/spike-identity/measured-shared-state.md` | ✅ new | 23 rows S-01..S-23 (what stays shared cross-profile) + 9 rows P-1..P-9 (what the seam partitions). Every row carries file:line + a quote re-verified at `d04cdb24…` by `citation_audit.py` (23/23 PASS). Runtime column is PENDING-FARM throughout. |
| `docs/spike-identity/papercut-census.md` | ✅ new | 15 rows C-01..C-15 covering all 13 Plan-named surfaces + session restore + extension messaging; 9 columns enforced by `census_lint.py` |
| `docs/spike-identity/probe-matrix.md` | ✅ new | 18 probes ↔ adversary (T2/T3/T4/T5) ↔ future §11.4 row ids ISO-01..ISO-13, ISO-BUILD-01..04. Every runtime row is PENDING-FARM. |
| `docs/spike-identity/fallback-design.md` | ✅ new | if F1/F2/F3 fire: BrowserContext-per-identity model, per-row impact for all 6 P14 registry rows, window-per-context UX cost, trigger sequence, and an explicit "what it does NOT solve" |
| `docs/threat-model.md` | ✏️ appended | "P4 identity-seam findings" table TM-P4-1..TM-P4-9 (7 × S1, 2 × S2) + a scope statement: identity partitions are a *storage and process* boundary, not a full-profile boundary |
| `docs/limitations.md` | ✏️ appended | "Measured cross-profile-shared disclosure (P4)": what the seam partitions vs what still leaks (Profile services, favicon cache, DNS, GPU, clipboard) |
| `docs/state/research-log-P4.md` | ✅ new | R1–R9 (pin; §1.4's symbol is wrong; `UrlInfo` is content-private; `CreateForFixedStoragePartition` is public; the CHECK-enforced invariant; per-partition network contexts; DNS QUALIFIED; OTR forces in-memory; the empty-domain trap; `navigator.cc:479`; hosted-CI root causes) + an explicit UNVERIFIED list |
| `build/spike/` | ✅ new | `spike.py` (CLI: `genpatch \| citation-audit \| census-lint \| probe`), `genpatch.py` (real pinned round-trip + `content/**` never-list), `citation_audit.py`, `census_lint.py`, `fsdiff.py` (sha256 manifests), `cdp.py` (stdlib RFC 6455 + CDP shim, loopback-only), `probe_driver.py` (offline lane today, farm lane wired), `tests/` (29 tests) |
| `build/patching/apply.py` | ✏️ extended | `lint_candidate_dirs()`: any patch dir outside `spike/` must be in the manifest; any dir inside `spike/` must carry `manifest-entry: NOT-YET`. `lint` gained `--xr-core`. |
| `build/skip_policy.py` | ✅ new (P4-T0.3) | the manifest of optional external tools; drives the conftest banner + summary so an absent tool prints `SKIP (tool absent: X)` |
| `evidence/P4/` | ✅ new | evidence.json (15 DoD rows, `--strict` valid), human-gates.md (HG-20..HG-24 + HG-P4-PUSH), logs/ (fresh-clone tests, genpatch round-trip, citation audit, gates, hosted-runs-before, no-token scan) |
| `evidence/P3/` | ✏️ retrofitted | brought up to `evidence-bundle-v1`: source labels, verdict vocabulary, 12 DoD rows with resolvable artifact paths, human-gates.md |
| `tools/run_checks.sh` | ✏️ extended | P4 gates: evidence bundles (incl. `--strict --only P3,P4`), citation-audit, census-lint, `probe --offline`, `sync.py check-pin-alive`, candidate patch lint |
| `tools/run_negatives.sh` | ✏️ extended | 10 → 14 cases (unmanifested patch dir; spike patch without `manifest-entry: NOT-YET`; census with a missing named surface; genpatch targeting `content/**`; strict evidence row citing a missing artifact) |

### xr-core (product)

| Path | Change | Contents |
|---|---|---|
| `patches/` | ✅ new | the `patches/` root + `manifest.yaml` (v1, `apply.py`-consumed) |
| `patches/0042-seam-hook/` | ✅ new | `0042-seam-hook.patch` (19214 B, sha256 `cf0b020f…`) + `patchinfo.md` carrying `manifest-entry: NOT-YET`. Deliberately **absent** from `manifest.yaml`; the candidate lint is what stops it being applied silently. |
| `spike/identity_seam/` | ✅ new | `xr_identity.h/.cc` (identity helper), `xr_seam_override.h/.cc` (inherits `ContentBrowserClient`, overrides `GetStoragePartitionConfigForSite`), `BUILD.gn`, `README.md`, `probes/` (5 browsertests, 477 LOC). **Uncompiled** — no Chromium checkout here (HG-9). |
| `BUILD.gn` | ✅ new | `//xr:xr_all` group, the P4 mount point |
| `scripts/mount.md` | ✅ new | D-B: how the mount point is consumed |

### Gates added in P4

| Gate | Tool | Protects |
|---|---|---|
| Citation honesty | `build/spike/citation_audit.py` | every `file:line` in the measured table still says what we claim, at the pin |
| Census completeness | `build/spike/census_lint.py` | all Plan-named surfaces present, 9 columns populated |
| Candidate-patch ledger | `build/patching/apply.py --xr-core` | no patch applies unless it is in the manifest or explicitly marked NOT-YET |
| Spike probe driver | `build/spike/probe_driver.py --offline` | the static + fixture lanes; the farm lane refuses to fabricate |
| SKIP visibility | `build/skip_policy.py` | an absent external tool is never a silent pass |
| Cross-repo pin | `build/sync.py check-pin-alive` | the DEPS `xr_core_rev` still resolves on origin |

## P5 — contract freeze (§1.11)

### xr-browser

| Path | Change | Contents |
|---|---|---|
| `docs/contracts/INDEX.md` | ✅ new | §1.11↔file↔interface↔§2.10 mapping table + conventions + freeze states |
| `docs/contracts/effective-policy-v1.{schema.json,md}` | ✅ new | EffectivePolicy v1 (strict, deny-default, total) |
| `docs/contracts/{list-bundle-manifest,command-descriptor,update-manifest-31-json,xr-schema-v1,settings-schema-v1,theme-tokens-v1,contract-amendment-rfc}-v1.md` | ✅ new | per-contract docs |
| `docs/contracts/*.schema.json` | ✅ new | strict hand-rolled schemas (command/list-bundle/update-manifest) |
| `docs/contracts/vectors/` | ✅ new | `policy-resolver-v1.json` (66 golden vectors), `route-manager-v1.json` (9) |
| `docs/contracts/review/01..14-*-v1.md` | ✅ new | 14 review packets (import-law, threat links, human sign-off pending) |
| `docs/contracts/tests/` | ✅ new | determinism, all-interface parity, update-manifest conformance |
| `docs/contracts/FROZEN.yaml` | ✅ new | freeze register — 14 rows REVIEW-COMPLETE, ratified PENDING (HG-26) |
| `docs/rfcs/{0000-template.md}` | ✅ new | contract-amendment RFC template + procedure |
| `tools/{mojom_lint,contracts_manifest,vectors_check,freeze_check,amend_guard,xr_schema,xrctl}.py` | ✅ new | P5 gates + dev CLI (all <400 LOC, stdlib, --json) |
| `tools/tests/{test_p5_contract_tools,test_amend_guard}.py` | ✅ new | unit + synthetic-repo negative proofs |
| `tools/tests/fixtures/mojom/*.mojom` | ✅ new | 9 negative fixtures (one per lint rule) |
| `build/contracts.py` | ✅ new | `./scripts/build contracts manifest\|lint\|vectors\|freeze\|all` |
| `tools/run_checks.sh`, `tools/run_negatives.sh`, `.github/workflows/governance.yml`, `scripts/build` | ✏️ edit | P5 gates + 5 new negatives wired |
| `DEPS` | ✏️ edit | `xr_core_rev` pair-bump to the P5 contract-freeze commit; header lineage note |
| `docs/{limitations.md,threat-model.md}`, `CONTRIBUTING.md` | ✏️ edit | resolver-total row; contract-enforcement links; amendment-RFC line |

### xr-core

| Path | Change | Contents |
|---|---|---|
| `mojom/` | ✅ new | 10 `.mojom` files (module xr.mojom) + `BUILD.gn` (bindings farm-gated) |
| `fakes/` | ✅ new | 8 behavioral fakes + `_base.py` + `README.md` (stdio JSON protocol) |
| `fakes/fixtures/` | ✅ new | per-contract fixture sets + example manifests |
| `l10n/isolation_card.json` | ✅ new | contract #14: measured disclosure strings, evidence-mapped, legal PENDING-HG-1 |

## P6 — policy resolver v1 (§637)

### xr-browser

| Path | Change | Contents |
|---|---|---|
| `tools/mode_lint.py` | ✅ new | L3 one-brain ban (mode logic only in the resolver) + L13 intent headers; negative corpus; `--json` |
| `tools/mutation_test.py` | ✅ new | operator-based mutant generation over the C++ core; score ≥90% + deny-guard 100% gates; survivor ±diffs; pid-unique scratch; `--sample/--seed/--timebox` |
| `tools/policy_fuzz.py` | ✅ new | determinism + envelope + enum invariants; corruption corpus (truncate/flip/dup-key/deep/oversize/garbage/NUL); >60KB + NUL via stdin; `--timebox 600` CI lane (24h = HG-28) |
| `tools/xrctl_policy.py` | ✅ new | `xrctl policy resolve\|dump\|watch\|snapshot-stats` (`--backend fake\|cpp`); wired into `tools/xrctl.py` |
| `tools/vectors_to_md.py` | ✅ new | generates `docs/contracts/policy.md` from the 66 vectors; `--check` = CI law (no hand drift) |
| `tools/tests/test_p6_policy_tools.py` | ✅ new | 14 tests: mode_lint ±fixtures, full parity matrix both backends, layer probes, budget, absence laws, smokes |
| `docs/contracts/policy.md` | ✅ new (generated) | the resolver dial table + precedence ladder + golden-vector table; regenerate, never hand-edit |
| `docs/contracts/policy-change-event-v1.{schema.json,md}` | ✅ new | contract #15; deltas/summary/undo, no score/risk/grade (absence-linted), no auto-reload |
| `docs/contracts/tests/golden-policy-change-event.json` | ✅ new | generator-byte-verified golden event |
| `tools/run_checks.sh`, `tools/run_negatives.sh`, `.github/workflows/governance.yml` | ✏️ edit | P6 gates + 5 new negatives + CI lanes (mutation sample, fuzz timebox, bench record) |
| `docs/{limitations.md,process/s0-paths.yaml}`, `docs/state/research-log-P6.md` | ✏️ edit / new | P6 limitation rows; evidence trail |

### xr-core

| Path | Change | Contents |
|---|---|---|
| `policy/core/` | ✅ new | json/json_parse/sha256/effective_policy/resolve/resolve_io/cache/snapshot/store/events/service (+service_mojom.h) — std-C++20, no Chromium includes, `-Wall -Wextra -Werror`, all <400 LOC |
| `policy/enterprise/managed_source.{h,cc}` | ✅ new | file-based managed source; minisign-verified ⇒ enforced, else IGNORED + ledger row |
| `policy/host/policy_host.cc` | ✅ new | stdio binary: `resolve\|snapshot\|watch\|dump` (same protocol xrctl speaks) |
| `policy/bench/bench_main.cc` | ✅ new | p50/p99/p99.9, 10⁵ ops, warmup excluded, canonical JSON + verdicts |
| `policy/tests/` | ✅ new | 10 suites, 1.23M checks: vectors parity, resolve, purity, cache TOCTOU, snapshot, store migration, events goldens, enterprise signed-path, json edge corpus, service integration |
| `policy/BUILD.gn`, `policy/README.md`, `policy/mode_lint.cfg` | ✅ new | policy_core std-only / enterprise / host targets; L3+L13 config |
