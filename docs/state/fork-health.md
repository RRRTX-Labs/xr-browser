# Fork health (generated)

_Generated 2026-09-07T15:01:58+00:00 by `build/upstream/fork_health.py` (`./scripts/build fork-health`). DO NOT EDIT BY HAND._

Headline table for the current cycle. SKIP rows are honest not-measured markers (L6) — never guesses.

| Metric | Value | Status | Source |
|---|---|---|---|
| budget:blink_seams | 0/25 | OK | manifest |
| budget:branding | 1/∞ | OK | manifest |
| budget:content_seams | 0/30 | OK | manifest |
| budget:extension_chokepoint | 0/2 | OK | manifest |
| budget:hook_points | 0/45 | OK | manifest |
| budget:network_seams | 0/20 | OK | manifest |
| budget:ui | 0/35 | OK | manifest |
| budget:TOTAL | 1/150 | OK | manifest |
| seams-retired (§12.5 reward metric) | 0 | SKIP | retirements ledger |
| rebase canary (last run) | verdict=GREEN (0 patch(es) non-clean, real lane, -> c60b3b1cdb2f) | OK | rebase-report.json |
| assumptions §12.4 | 6 PASS / 1 SKIP / 0 FAIL | OK | assumptions-run.json |
| fastlane drills | last: breach → PASS (SIMULATED; 80.0h simulated) | OK | work/upstream-cache/fastlane/drill2-breach/drill-report-breach.json |
| feature-freeze marker | PRESENT (advisory pre-GA; HARD at P9) | DRIFT | feature-freeze.json |

## Reading the table

- **budget:*** — patch-budget usage (§1.2 caps; total ≤150). OVER = the T3 gate blocks CI until a seam retires.
- **seams-retired** — the §12.5 reward metric; SKIP means the zero baseline (P3 ships with 0 retirements — stated, not hidden).
- **rebase canary** — drift count from the last `rebase` run this cycle; DRIFT routes owner issue bundles (T2).
- **assumptions §12.4** — blocking surface checks; FAIL = P0 artifact + promotion block.
- **fastlane drills** — SIMULATED security-lane rehearsals (T5); real activations come with the first security tag after GA.
- **feature-freeze marker** — §15-R1 kill-switch signal (advisory pre-GA; the P9 dashboard makes it HARD — stated).
