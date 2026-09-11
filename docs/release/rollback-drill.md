# docs/release/rollback-drill.md — the farm rehearsal (HG-31/35 class)

The LOCAL drill (`tools/rollout_drill.py`, transcript
`evidence/P10/logs/t5-rollout-drill.txt`) executes 10 cells for real:
serve→accept, refuse-downgrade, replay refusal, ramp boundaries 49/50,
epoch revocation applied (self-signed notice law: a notice is valid iff
signed by the key it names — production root-signed ceremony = HG-36),
revocation forcing the manual path, stale-notice ignore, the P38
auto-rollout refusal, and the dev-only crash-hook assertion.

What stays FARM (this sandbox cannot do it): the same drill against
REAL per-OS builds on three OSes — a notarized macOS app, an
Authenticode-signed Windows installer, an apt/rpm repo served over
TLS — because it needs HG-36/37 credentials + physical hosts. The farm
runbook: run `tools/rollout_drill.py --store-dir <scratch>` on each
target against a staging server, then force the epoch flip from the
ceremony HSM and observe the About view enter `refused`/manual-path on
all three OSes. HG row: rollback drill on three OSes — BLOCKED/HUMAN-GATED
this phase (HG-31/35 class), correctly not claimed.
