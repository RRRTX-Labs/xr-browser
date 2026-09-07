# Contributing to XR Browser (xr-browser meta repo)

Thank you. This project runs on unusually strict process — that is the
product. Read these rules before the first PR; most rejections are
preventable.

## 1. The law you're contributing under

- **Master Plan** — `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md`,
  SHA-256-pinned. It is the single source of truth and is **immutable in
  place**. You cannot "fix" it in a PR; deviations go through
  `docs/process/plan-amendment.md` (draft issue + register entry + new
  versioned file + re-pin, one reviewed commit).
- **License: MPL-2.0.** No copyleft (GPL/AGPL) code in this repo or in
  anything it links (ADR-0001, DR-04). Filter lists and similar are
  *data* with sidecar license files, never linked code.
- **DCO required.** Every commit must carry a matching
  `Signed-off-by: Your Name <your@email>` (CI: `dco_check.py`). Use
  `git commit --signoff`. Your identity must be the same person who
  authored the change.

## 2. Review classes (CODEOWNERS)

- **S0 paths** (`tools/`, `docs/register/`, `docs/registry/`,
  `docs/adr/`, `.github/workflows/`, `ci/`): **dual senior review**
  including Security. These are the guardrails; they are guarded.
- **S1 paths** (`docs/legal/`, `docs/dependencies/`): legal/owner
  review.
- Everything else: standard review.

Owner handles are placeholders until GitHub hosting lands (evidence/P1
human gate HG-3); the path classes are already authoritative.

## 3. Change disciplines (CI-enforced, fail-closed)

| You change… | CI requires |
|---|---|
| `docs/register/decisions.yaml` | `Register-Change: ADR-<nnnn>` trailer on the commit |
| `docs/registry/*` | nothing — it is generated. Re-derive with `tools/gen_registry.py --write` only after an approved plan amendment |
| the plan | never in place; `docs/process/plan-amendment.md` |
| `docs/threat-model.md` | structure preserved: T1–T11 honesty column, plan-SHA binding (`check_threat_model.py`) |
| any user-facing copy | no banned-claims vocabulary (`vocab_lint.py`); allowlist entries need written justifications |
| `LICENSE` | must stay byte-for-byte canonical MPL-2.0 (`license_audit.py`) |
| dev dependencies | `tools/requirements-dev.txt` stays hash-pinned; max PyYAML/jsonschema/pytest; new deps need a consumer in the same commit (`tools/DEPS.md`) |

## 4. Anti-fabrication (plan L5; non-negotiable)

- No stubs for later phases: P1 contains no build system, no patches,
  no product source — and your PR must not add premature scaffolding
  "for P2" either.
- No invented security claims: the threat model says what the product
  does NOT protect against; copy that overstates is a release blocker.
- No telemetry, no network calls in tooling, no "mock" security
  features. If you can't verify a fact from a primary source, record it
  UNVERIFIED with a re-verification phase — never guess.

## 5. Local loop before pushing

```sh
pip install --require-hashes -r tools/requirements-dev.txt
tools/run_checks.sh        # all 8 gates + 55+ tests
tools/run_negatives.sh     # gates must fail on bad input
```

Both must pass. CI runs the same thing (plus range-scoped DCO/trailer
checks).


## Contract amendments

After the P5 freeze, changing a frozen `xr.mojom` contract or a listed contract
doc requires an **approved RFC**: add `docs/rfcs/RFC-<n>.md` (from
`docs/rfcs/0000-template.md`, status APPROVED by a human) and carry the trailer
`Contract-Amendment: RFC-<n>` on the commit. `tools/amend_guard.py` enforces
this (warn-only before a contract is stamped in `docs/contracts/FROZEN.yaml`,
blocking after). See `docs/contracts/contract-amendment-rfc.md`.

## 6. Reporting security issues

Do not open a public issue. See `SECURITY.md` (coordinated disclosure,
90-day embargo, bounty charter v0). Intake is marked PENDING-OPS until
hosting lands — the documented fallback path is in the same file.
