# QA charter — the laws every verification surface obeys (P9-T12)

This is the contract the §11 surfaces table (`docs/qa/surfaces.yaml`) points
at. A phase that adds a check is bound by it; a check that violates it is
not a check, it is decoration.

## Law 1 — every runner must be able to fail

A runner that cannot turn red certifies nothing. Shipping "infrastructure"
that always passes is the fabrication this phase exists to prevent. Two
fixtures are mandatory per runner, and both live in the negative gate
(`tools/negatives/`, N counted at runtime — never a hand-written total):

1. **canary** — a deliberately broken input the runner MUST reject; and
2. **empty-input** — zero cases / zero rows / zero targets MUST fail, never
   pass (the "runner cannot PASS on zero cases" helper in
   `build/qa/_common.py`, imported by construction, not by convention).

A runner without both is not delivered, regardless of how much of it works.

## Law 2 — the mutation meta-check ("mutation-check the checker")

`build/qa/tools/test_checker_mutation.py` injects a defect into a runner in
a copied tree (always-true comparison, dropped cell, off-by-one threshold)
and asserts the suite turns red. Every phase reports which runners it
mutation-checked and which it did not — a partial answer is honest, a
claimed total is not.

## Law 3 — the rig-class law (perf only)

`docs/hw.md` defines three rig classes; browser-side budgets may only be
asserted on the `reference` class. A `trend`-class rig asserting a
browser-side budget is **refused** (exit 1, reason printed). Every report
names the rig class that produced it — no verdict without its rig.

## Law 4 — the waiver-with-expiry law

A waiver (visual snapshot or a11y violation) covers one concrete
`(name, hash/rule)` pair and carries an expiry. An expired waiver re-asserts:
the runner goes red until the waiver is renewed or the code fixed. Blanket
waivers are not representable.

## Law 5 — no new check without a fixture that turns it red

A phase may not add a check that has no canary fixture. The negative gate is
the proof: the check's case appears in `tools/negatives/` in the same
commits, and `run_negatives.sh` counts it.

## Law 6 — the honesty of SKIP and farm rows

Anything the sandbox cannot run (no clang, no rustc, no gn/ninja, no
browser, no VM) is a `SKIP (tool absent: X) — needed for: …` (visible, via
`build/skip_policy.py`, exit 77) or a farm row with an owner + cadence +
exact command. Never a simulated PASS. `docs/qa/surfaces.yaml` is the
inventory; `tools/surfaces_check.py` enforces that no §11 surface is
homeless and that no row claims `real-in-ci` without a resolvable run id.

## Law 7 — determinism (the frozen-clock law)

No wall-clock or hash-order dependence in any verdict. Where a timestamp
belongs in a report it comes from `--as-of`; two runs with the same
`--as-of` are byte-identical (a test proves it).

## Quarterly harness-health review (the plan's Manual row)

Every quarter, the QA owner runs:

```sh
bash tools/run_checks.sh && bash tools/run_negatives.sh
./scripts/build test
python3 tools/evidence_check.py --strict
python3 tools/surfaces_check.py --repo .
build/qa/tools/test_checker_mutation.py   # if present in the tree
```

and files a short note in `docs/state/` recording: N (negative cases),
the four C++ suite counts, the fleet timeboxes, and any runner whose canary
or mutation fixture was found stale. The review is the manual surface
(§11.14) that keeps the machine side honest.

## What P9 shipped under this charter

Every runner below has a canary **and** an empty-input fixture in
`tools/negatives/` (both trip, N counted at runtime). The mutation column
records which runners `build/qa/tools/test_checker_mutation.py` actually
inject-a-defect-into-the-runner checks — a partial answer is honest, a
claimed total is not.

| runner | canary? | empty-input? | mutation-checked? |
|---|---|---|---|
| isolation matrix | ✓ | ✓ | not yet (canary + empty-input only) |
| leaktest | ✓ (planted egress) | ✓ | not yet (self-test is its own meta-check) |
| compat corpus | ✓ (live-mode refusal) | ✓ | not yet |
| perf gate | ✓ (10% MISSED) | ✓ | ✓ (always-true budget compare) |
| visual compare | ✓ (must-flag pair) | ✓ | not yet |
| a11y (axe/AXTree/copy) | ✓ (nameless button) | ✓ | not yet |
| fuzz fleet | ✓ (min-iters floor) | ✓ | not yet |
| SAST rules | ✓ (dead rule) | ✓ | not yet |
| kill matrix | ✓ (assertion-less row) | ✓ | not yet |
| surface check | ✓ (homeless surface) | ✓ | ✓ (homeless branch deleted) |
| evidence check | ✓ (T12 amendments) | n/a (a bundle is required) | ✓ (not_done_by_design invariant removed) |
