# tools/tests/fixtures/ — negative test corpus

Files in this directory **intentionally contain content that the
governance linters must reject** (copyleft license headers, unsigned
commit setups, …). They exist to prove the detectors fail correctly —
Plan P1 DoD: "license-scan fails on an injected GPL sample".

Consequences, enforced:

- `tools/license_audit.py` excludes `tools/tests/fixtures/` from its
  marker scan (a scanner does not scan its own negative corpus).
- Nothing outside this directory may contain banned license markers in
  code paths; that is what the gate is for.
- These files must never be imported, shipped, or copied into build
  trees.
