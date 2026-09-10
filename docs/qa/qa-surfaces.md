# QA surfaces — the §11 inventory (P9-T12)

`docs/qa/surfaces.yaml` is the §11 surface inventory as data: all 15
surfaces (11.1 unit → 11.15 evidence standard), each with a **home** (a tool
that runs in this repo, a farm row, a named+staffed+scheduled human surface,
or a not_yet row owned by a phase) and a **machine-side green** clause.

`tools/surfaces_check.py` is the completeness gate:

- every §11 id present (11.1..11.15);
- every surface homed (a "§11 surface without a home" is the plan's
  stop-condition — the gate turns red);
- every listed tool path resolves;
- every manual row has an owner + cadence;
- zero surfaces is red (empty-run law).

## How the 15 surfaces map to this repo

| §11 | surface | in-repo home | farm |
|---|---|---|---|
| 11.1 | unit | `tools/run_checks.sh` (pytest) + core Makefiles | — |
| 11.2 | browser tests | `tools/browser_test_lint.py` | HG-31 |
| 11.3 | E2E | `tools/xrctl.py` | HG-31 |
| 11.4 | isolation matrix | `tools/isolation_matrix.py` | HG-31 |
| 11.5 | vault suite | not_yet (P28) | — |
| 11.6 | UI/a11y/copy | `a11y_tree`/`a11y_lint`/`copy_lint`/`keyboard_tasks_check`/`pseudo_locale` | HG-31/HG-32 |
| 11.7 | perf | `perf_gate` + `gen_perf_budgets` | HG-35 |
| 11.8 | leak | `tools/leaktest.py` | HG-36 |
| 11.9 | ext/update-diff | not_yet (P21) | — |
| 11.10 | crash/recovery | `tools/drill_check.py` | HG-33 |
| 11.11 | upgrade/downgrade | `tools/drill_check.py` | HG-34 |
| 11.12 | compatibility | `compat.py` + `wpt_delta.py` | HG-31 |
| 11.13 | fuzzing | `fuzz_fleet` + `mojom_fuzz_gen` + `seed_corpus` + `policy_fuzz` | HG-28/HG-29 |
| 11.14 | cannot-automate | manual rows (owned + scheduled) | — |
| 11.15 | evidence | `tools/evidence_check.py` | — |

## Command

```sh
python3 tools/surfaces_check.py --repo .   # PASS: 15 surface(s), 0 violation(s)
```
