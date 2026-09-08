# tools/ — dependency policy (ADR-0001, Plan P1)

Rule: **at most PyYAML, jsonschema, pytest** — dev/CI-only, MIT-licensed,
pinned with SHA-256 hashes. Everything else is Python stdlib. No
runtime dependency is introduced by governance tooling.

## Pinned (tools/requirements-dev.txt, hashes verified 2026-09-07)

| Package | Version | Role | Consumed by |
|---|---|---|---|
| PyYAML | 6.0.3 | parse/emit the YAML artifacts (register, registry, allowlists, evals) | dr_parse, gen_registry, registry_lint, vocab_lint, license_audit |
| pytest | 9.0.3 | run the co-located test suites | tools/tests/* |
| iniconfig | 2.3.0 | pytest transitive | — |
| packaging | 26.2 | pytest transitive | — |
| pluggy | 1.6.0 | pytest transitive | — |
| Pygments | 2.20.0 | pytest transitive | — |

Hash source: `pypi.org/pypi/<pkg>/<ver>/json` → `urls[].digests.sha256`
(pinned artifacts: cp312/cp313 wheels for PyYAML + sdist; py3 wheels +
sdists for the pure packages). Install:
`pip install --require-hashes -r tools/requirements-dev.txt`.

## Permitted but NOT pinned

- **jsonschema** — permitted by the policy, currently pinned by nobody:
  no P1 tool consumes it. Pre-pinning an unused dependency violates the
  "no unnecessary dependency" rule; when a tool needs JSON-Schema
  validation (e.g. update-manifest profile at P10), pin it here with
  hashes in the same commit that adds the consumer.

## WebUI build toolchain (P7 — build-time ONLY, lives in xr-core)

The command-registry WebUI is built by a lock-pinned npm toolchain in
`xr-core/ui/toolchain/` (not this repo's Python tooling). Exactly **three**
packages, all **build-time** (they emit a bundle + type-check; none ships,
none runs in the browser — zero-network-at-runtime). Each has a full L9 eval
in `docs/dependencies/` and an integrity pin in the lock:

| Package | Version | License | Role | Eval |
|---|---|---|---|---|
| lit | 3.3.3 | BSD-3-Clause | WebUI component framework | `docs/dependencies/lit.yaml` |
| esbuild | 0.28.2 | MIT | deterministic bundle builder | `docs/dependencies/esbuild.yaml` |
| typescript | 5.9.3 | Apache-2.0 | `tsc --strict` gate | `docs/dependencies/typescript.yaml` |

Supply-chain posture: `npm ci --ignore-scripts` (no install scripts),
integrity-pinned lock, `npm audit` = 0 vulnerabilities (2026-09-08), and the
built bundle is re-scanned by `check-bundle.js`. Any **fourth** npm package is
a P7 stop-condition (a reviewed supply-chain edge, not an add-on). See
`docs/webui-toolchain.md`.

## Never allowed here

- Any dependency whose license is not MIT-compatible with MPL-2.0
  distribution of this repo.
- Any dependency without a pinned digest (floating versions).
- Anything that reaches the network at import/execution time beyond
  `git` subprocess calls (tools may shell out to `git` for history
  checks; they never fetch, install, or call remote services).

## Change procedure

Adding/updating a pin: one commit containing the new version + hashes
(verified against PyPI JSON), the consumer, and the tests. Dual senior
review (tools/ is S0 in CODEOWNERS).
