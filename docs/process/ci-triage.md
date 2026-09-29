# CI triage — what is public, what is not, and how to read a red run

Written after a phase was lost to a misdiagnosis: the brief once ruled that
"`/logs` and `/annotations` are admin-only — do not claim you needed them".
Half of that is true. The half that was false cost a phase, so the table below
is **measured** (2026-09-29, `RRRTX-Labs/xr-browser`, **unauthenticated**), not
recalled.

| endpoint | auth | measured | what it gives you |
|---|---|---|---|
| `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` | **none** | 200 | every check-run on that commit: `name`, `id`, `status`, `conclusion`, `details_url` (which carries the run id and the job id), `head_sha` |
| `GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations` | **none** | 200 | the annotation text — this is where `Process completed with exit code 126.` and `Process completed with exit code 1.` come from, with `path`/`start_line`/`annotation_level` |
| `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | **none** | 200 | per-job step list: the **failing step's name** (`Governance checks`) and the **skipped cascade** (10 steps that never ran, which is what a bare exit code hides) |
| `GET /repos/{owner}/{repo}/actions/runs/{run_id}` | **none** | 200 | run metadata: `name`, `head_sha`, `event`, `conclusion` — pass a run id and the tool derives the SHA from here |
| `GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs` | admin | **403** | the raw log zip. Genuinely admin-only. Do not plan around it; the annotation plus the failing step name is enough for the triage this repo needs |

## The two endpoint shapes (copy-pasteable)

```bash
# 1) every check-run on a commit (public) — check_run_id comes from here
curl -s "https://api.github.com/repos/RRRTX-Labs/xr-browser/commits/<sha>/check-runs" | jq -r \
  '.check_runs[] | "\(.name) id=\(.id) \(.status)/\(.conclusion) \(.details_url)"'

# 2) the annotation text for one of them (public)
curl -s "https://api.github.com/repos/RRRTX-Labs/xr-browser/check-runs/<check_run_id>/annotations" | jq -r \
  '.[] | "[\(.annotation_level)] \(.path):\(.start_line): \(.message)"'
```

## Use the tool, not the curl

```bash
python3 tools/ci_triage.py --sha <sha>            # everything above, in order
python3 tools/ci_triage.py --run <run_id>         # derives the sha from the run
python3 tools/ci_triage.py --sha <sha> --json     # machine-readable
python3 tools/ci_triage.py --sha <sha> --offline tools/fixtures/ci_triage
python3 tools/ci_triage.py --self-test            # fixture-backed; part of the gate
```

It prints, per check-run: name, status/conclusion, the run/job it belongs to,
the failing step names, the skipped-step count, and every annotation line — then
a verdict. A run with no failing check-run exits 0; a red one exits 1; usage
errors exit 2.

**Never a guess.** When the network is unavailable, rate-limited, or an
`--offline` fixture is missing, the tool prints

```
BLOCKED-NET (offline fixture missing: tools/fixtures/ci_triage/runs/…jobs.json) —
cannot answer for /repos/…/actions/runs/…/jobs; a fixture-backed run must not guess
```

and exits **77**. `tools/fixtures/ci_triage/` holds recordings of the red SHA
`8db682f` (check-runs, the `exit code 126` annotation, the governance run's
jobs), captured unauthenticated on 2026-09-29; they are trimmed to the fields
the tool reads and exist so the self-test can prove the reader works offline.

## So the reason arrives by itself

Since P13-P0B every gate step starts with `. tools/ci_capture.sh <lane>`
(`tools/ci_capture.sh`), which keeps a transcript and, on any non-zero exit,
emits one GitHub workflow command from `tools/gate_annotation.py`:

```
::error::governance: citation-audit - BLOCKED-NET: 23 citations unreachable from this sandbox
```

That line lands in the check-run's public annotation. A future red run
therefore says *which gate failed and why* in the same place where the runner
used to say only "exit code 1" — the diagnostic gap that made the previous hunt
take a phase. The lane name is in the annotation, and a unit test on the emitted
line format (`tools/tests/test_gate_annotation.py`) fails if it ever stops
being.
