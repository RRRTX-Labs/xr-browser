# tools/ — governance tooling (S0)

Typed Python 3.12+ standard-library-first tools that make the plan's
governance rules machine-checkable. Every tool:

- `--help` and `--json` (machine-parseable output),
- exits `0` = pass, `1` = fail (fail-closed), `2` = usage error,
- has co-located tests in `tools/tests/`.

Dependency policy: `tools/DEPS.md` (max PyYAML/jsonschema/pytest,
hash-pinned; stdlib otherwise).

| Tool | Enforces | Plan anchor |
|---|---|---|
| `plan_pin_check.py` | committed Master Plan == SHA-256 pin | §0.4 (single source of truth), P1-T11 |
| `registry_lint.py` | feature registry == plan §2 (no feature outside it; no drift) | §2 preamble, P1-T10 |
| `gen_registry.py` | derives/rewrites `docs/registry/*` from the pinned plan | §2, P1-T10 |
| `dr_parse.py` | Decision Register schema (DR-01..30) + `Register-Change: ADR-<nnnn>` trailers | §14 (L-law), ADR-0002, P1-T9 |
| `license_audit.py` | canonical MPL-2.0 + no GPL/AGPL code (header/inventory level — full dep-graph is P9-T9) | §1.12-4, DR-04, ADR-0001 |
| `dco_check.py` | every commit carries a matching `Signed-off-by` | MPL-2.0 + DCO (P1-T1) |
| `check_threat_model.py` | threat-model v0 structure: plan binding, T1–T11 honesty column, invariants, stated out-of-scope | §9.1 |
| `vocab_lint.py` | banned-claims vocabulary (§0.3/§1.12-9/§9.11); §1.12-11 intent rule recorded as human-enforced | §9.11 |
| `owners_sync.py` | CODEOWNERS/OWNERS in sync with `docs/process/s0-paths.yaml` | P1-T7 |

## Running

```sh
# full gate (what CI runs), optionally over a git range:
tools/run_checks.sh [git-range]

# proof that the gates fail on bad input (Plan P1 "Tests"):
tools/run_negatives.sh

# tests only:
python3 -m pytest tools/tests/ -q
```

CI definition: `.github/workflows/governance.yml` (actions pinned by
full SHA; Python 3.12; hash-pinned dev deps). Until the repo has a
GitHub remote, the local runs above are the executed gate and their
logs live in `evidence/P1/`.

## Governance notes

- `docs/state/vocab-allowlist.yaml` (line-precise) and
  `docs/state/license-allowlist.yaml` (path-level) are reviewed
  data: every entry carries a written justification; adding an entry
  is a governance act, not a maintenance chore.
- `tools/tests/fixtures/` is the negative test corpus: it
  intentionally contains content the linters must reject, and is
  excluded from their scans (a scanner does not scan its own corpus).
- Tools are header/inventory-level checkers by design (L5, no
  overclaiming): `license_audit.py` is not a dependency-graph scanner
  (that is P9-T9), and `vocab_lint.py` does not claim to catch intent
  claims in prose (human copy review, §1.12-11).
