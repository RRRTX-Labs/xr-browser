# Repository map (P1 state)

Plan §7.1 topology: **two repos + helpers**, deliberately not a sprawl.
This map records what exists at P1 close and where each planned surface
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
| `.github/workflows/governance.yml` | ✅ | CI definition (actions pinned by full SHA) |
| `evidence/P1/` | ✅ | evidence.json, human-gates.md, logs/, research-log-links.txt, registry-recount.md |
| `build/`, `ci/` | 📋 planned P2/P3 | `ci/` has a README only; build system arrives with P2 (hermetic Chromium build) |
| `docs/contracts/` | 📋 planned P5 | contract docs (IDLs land in xr-core `//xr/mojom`) |

## xr-core (product — `//xr` inside the overlay; MPL-2.0)

| Path | Status at P1 | Contents |
|---|---|---|
| `LICENSE`, `README.md`, `CONTRIBUTING.md`, `.gitignore`, `.clang-format` | ✅ | repo root artifacts |
| `CODEOWNERS`, `OWNERS` | ✅ | S0 path protection (placeholder handles until HG-3) |
| `mojom/`, `policy/`, `identity/`, `net/`, `vault/`, `extensions/` | 📋 planned | S0 product surfaces — **do not create stubs now** (P4/P5+; anti-stub rule, plan §0.4/L5). `mojom/` freezes at P5. |
| `patches/`, `manifest.yaml` | 📋 planned P2 | patch-manifest format v1 lands with P2-T3 |

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
