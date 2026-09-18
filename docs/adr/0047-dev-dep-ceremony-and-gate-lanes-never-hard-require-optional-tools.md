# ADR-0047: a dev-dependency addition requires ADR-0001's ceremony, and a gate lane must never hard-require an optional tool

- **Status:** PROPOSED (drafted by the P12-CLOSE coding agent; ratification
  rides HG-26's queue — agents draft, humans decide, L24)
- **Date:** 2026-09-18
- **Deciders (humans):** Platform lead + Security lead (supply chain +
  gate-correctness are S0-adjacent, L13 dual review)
- **Plan anchor:** ADR-0001 (the three-dep cap), Plan §1.5/L9 (no dependency
  without an evaluation), P12-T0-a (date invariance), the skip-policy law
  L6 (build/skip_policy.py)

## Context

P12-T0-a added `libfaketime==3.0.1` to `tools/requirements-dev.txt` with two
CORRECT sha256 hashes. That addition broke the hosted governance gate in
**two independent directions**, neither of which the agent's own sandbox
could observe (the package had been hand-installed there):

1. **The closure violation.** `libfaketime` declares
   `Requires-Dist: python-dateutil>=1.3, pytz`. In `--require-hashes` mode pip
   requires every marker-free transitive to be pinned AND hashed. Neither
   `python-dateutil` nor `pytz` was in the file, so
   `pip install --require-hashes -r tools/requirements-dev.txt` hard-errored:
   `ERROR: In --require-hashes mode, all requirements must have their versions
   pinned with ==. These do not: python-dateutil>=1.3 ...`. That is precisely
   the failing hosted step on pushes `344def9a8` … `0c35cbb8c`.
2. **The lane-cap violation.** `tools/run_checks.sh` invoked
   `tools/date_invariance_check.py --require-ambient-probe`. On any machine
   lacking `libfaketime.so.1` the whole gate exited 1 at lane 109 — 27
   downstream verdicts never ran (`set -euo pipefail` aborts at first FAIL).
   A principled refusal ("certifies less than the gate claims") that is
   nevertheless unrunnable on a clean clone.

Neither half left a trace of its own failure mode: there was no check that
"the file's closure is complete under --require-hashes", and no rule that "a
gate lane must not hard-depend on an optional tool". The environment coupling
was the defect's carrier.

## Decision

1. **A dev-dependency addition is a ceremony event.** ADR-0001's cap is the
   registered policy — "at most PyYAML, jsonschema, pytest" plus their
   hash-pinned transitives. Adding a fourth (or any transitive) pins it AND
   hashes every marker-free requirement it pulls, and is recorded in a
   `docs/adr/` note naming which consumer justifies it. The additions that
   broke P12 (libfaketime) are reverted; the probe becomes an optional
   external helper tool.
2. **`tools/dev_deps_closure_check.py` exists and is gated.** It parses
   `tools/requirements-dev.txt`, resolves each pinned distribution's declared
   requirements (from committed PyPI metadata in
   `tools/fixtures/dev-deps-closure.json` — the fixture route, so the gate is
   offline), and FAILs on any marker-free, extra-free requirement that is
   absent from the file or lacks a hash. It runs in `run_checks.sh` and has
   two registered negatives. The refresh ceremony (`--check-diff-clean` /
   `--fetch-write`) fetches `https://pypi.org/pypi/<pkg>/<ver>/json` THROUGH
   the chokepoint `build/upstream/fetch.py`; `pypi.org` joins `ALLOWED_HOSTS`
   for pinned release-METADATA JSON only — `files.pythonhosted.org` and the
   simple index stay off the list, and no wheel/sdist may ever be fetched by
   a tool.
3. **A gate lane must never hard-require an optional tool** (the SKIP law).
   The ambient-clock probe moves to the repo's established mechanism for
   exactly this class (minisign/actionlint): an optional external tool
   documented in `docs/dependencies/helper-tools.yaml`, installed by
   `apt-get install -y faketime` in the "Install optional helper tools" CI
   step. `date_invariance_check`'s behaviour becomes:
   - **default path** (run_checks.sh): the deterministic `--as-of` pair is
     the verdict; the ambient half runs as a strengthening lane when
     `faketime` is present and reports UNAVAILABLE (visibly, in the PASS
     line) when absent — never a silent pass, never a fabricated probe.
   - **strict path** (`--require-ambient-probe`): passed ONLY by the
     scheduled governance lane that installed the tool. On a host that
     demands the probe without the tool, the run FAILS (it would certify
     less than it claims) — the fixture proves this red. No default gate
     path ever carries the flag.
4. **`run_checks.sh` gains a `--keep-going` mode** (its bodies move to
   `tools/checks/gate_runner.sh` under the ≤380 touched-file law): a broken
   optional dependency must never silently conceal downstream verdicts
   again — the runner reports every failing lane in one pass and exits 1
   with the count.

## Why libfaketime is a helper tool, not a pip pin

P12's own brief recorded the asymmetry honestly: the green 136-PASS was real
**in a sandbox where libfaketime had been hand-installed**, and an
environment no one can reproduce is not evidence. `libfaketime` is a
test-only preload library (a compiled `.so`), not a Python dependency of any
gate verdict; the apt `faketime` package is the OS-level owner of that
library, already pinned by the distribution, and survives the
`--require-hashes` discipline by living entirely outside it — the
`minisign`/`actionlint` precedent, byte for byte.

## Consequences

- `tools/requirements-dev.txt` returns to ADR-0001's capped set (pytest,
  PyYAML + 4 hashed transitives); the closure gate proves it stays complete.
- `faketime` enters `docs/dependencies/helper-tools.yaml` +
  `build/skip_policy.py` (in-sync, test-pinned); `date_invariance_check`
  keeps both tiers and its freshness law; the ambient half is a
  strengthening lane, not a gate requirement.
- Hosted governance installs minisign + faketime + actionlint in one step
  and adds a strict-probe step that first proves `faketime` displaces a
  child clock (a probe that cannot prove its own displacement is a dead
  probe, never a proof).
- `ALLOWED_HOSTS` grows by one metadata-only host (`pypi.org`) under the
  ADR-0044 ceremony shape; the checker's second lock mirrors it in the same
  commit set.
- Precedent: any future dev-dep change is a ceremony event (closure pin +
  fixture diff-clean + this ADR's record); any future optional-tool lane
  inherits the SKIP-vs-strict split instead of hand-rolling one.

## Reversal

Reopen if the repo ever needs a dev dependency whose distribution ships no
apt/system equivalent and whose transitive closure genuinely cannot be
hash-pinned (the closure gate would encode the exact blocker); the decision
point is then whether to extend the ceremony, not to exempt the file. Per
ADR-0002, reopening needs new written evidence and a new ADR.
