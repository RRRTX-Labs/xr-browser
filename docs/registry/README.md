# Feature Registry (derived from the pinned Master Plan)

The plan's §2 is the feature registry — "no feature exists outside it"
(plan §2 preamble). These files make that statement machine-checkable.

| File | Contents |
|---|---|
| `features.yaml` | One entry per table row of plan §2.1–§2.9 (122 rows: 100 active, 3 deferred, 19 dropped). IDs `F-001`…`F-122` in plan order; `plan_line` gives the exact source line. |
| `reserved-interfaces.yaml` | The §2.10 reserved interfaces (6), frozen at P5, with the no-parallel-paths rule verbatim. |
| `COUNTS.json` | Section/status/criticality/security/decision counts, recomputed from the plan on every check. |

**Provenance and maintenance**

- All three files are *generated*: `tools/gen_registry.py --write`
  (run only after an approved plan amendment — see
  `docs/process/plan-amendment.md`).
- CI runs `tools/registry_lint.py`: it re-derives everything from the
  pinned plan and fails on any drift — in the plan, in the registry, or
  in the counts.
- Raw fields (`feature`, `decision_raw`, `dep_raw`, `phases_raw`,
  `risk`, `proof`) are verbatim plan text; "—" in the plan is stored as
  YAML `null`.
- DROP rows are kept deliberately: they are binding "do not build"
  decisions (the anti-resurrection record), not deletions.

Note on sizing: earlier planning estimates said "~115 rows"; the pinned
plan's §2.1–§2.9 tables contain **122** rows (counted line-by-line,
evidence in `evidence/P1/registry-recount.md`). All rows are present —
the registry never drops a plan row to fit an estimate.
