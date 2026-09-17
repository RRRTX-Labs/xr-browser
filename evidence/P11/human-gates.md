# evidence/P11/human-gates.md — the human gates P11 leaves open

**Provenance.** This file is a RETRO-BUNDLE artifact, authored by the P12 agent
on 2026-09-17 at the orchestrator's explicit request (P12-T0-b). The P11 phase
agents shipped `evidence/P11/logs/` (24 transcripts) and no bundle, so P11's
human gates were recorded only in commit-message prose. Nothing here claims a
P11 agent wrote it, and no P11 log was modified. Every row below names the act
this sandbox cannot and must not fake.

| id | gate | why human | operator steps (exact) | status |
|---|---|---|---|---|
| HG-31 | Browser-rig page-level assertions for the Shield/cosmetic surface | needs a real browser, a real renderer and a real DOM — none exist in this sandbox | `docs/qa/browser-harness.md`: build at the pin, run the document-start timing harness, the blank-page detection sweep on the fixture corpus, and the 50-hard-apps spot check | NOT-RUN (no `gn`/`ninja`, no Chromium checkout, no browser; `gn` ABSENT is measured, not assumed) |
| HG-9 / HG-27 | Real mojom bindings replacing `fakes/*.py` | farm glue; requires a Chromium build | build `//xr/shield` in-tree at the pin and drive `shield.mojom` from the browser process instead of the stdio fake | NOT-RUN (the fakes are explicitly labelled behavioural fakes, never bindings — `fakes/README.md`) |
| HG-26 | Ratify-or-amend the living-contract consumers before the next phase | sign-off act | `docs/contracts/FROZEN.yaml` carries 14 rows, all `ratified: PENDING`, now six consumers deep (P6 policy, P7 command-descriptor, P8 settings/theme, P9 evidence format, P10 update-manifest, P11 list-bundle). Review `docs/contracts/registry-post-freeze.md` and ratify in one batch or record the amendment | OPEN (recommended: one-batch ratification; six consumers now depend on the shapes) |
| HG-20 | PAT revocation | user action, user-owned credential | revoke the over-scoped GitHub PAT exposed in chat, and rotate anything it ever touched | OPEN (carried from P9; still user-owned). **P12 note:** the P12 dispatch supplied a token in chat again — see `evidence/P12/human-gates.md`, which records the revocation request for that token too |
| HG-34 | Branch protection on `main` in both repos | org setting, not a repo artifact | GitHub → Settings → Branches → require signed DCO commits + green `governance` before merge on `RRRTX-Labs/xr-browser` and `RRRTX-Labs/xr-core` | OPEN |
| — | `sast` scheduled lane: verify the next fire is green | scheduled cadence, not a push-time act | the last `sast` run at the P11 tip is `STALE-FAIL`: the workflow file was fixed at `35d0993` AFTER that run started, so its verdict predates the fix. `tools/scheduled_lane_check.py` reports this exactly (visible, non-fatal, never counted green). Confirm the 2026-09-21 04:17 UTC fire | OPEN (standing check; carried into P12) |
| HG-28 | 24 h full-mutation matrices at the release pin | wall-clock farm budget | `tools/mutation_test.py --targets <all> --sample 0` per core at the release pin | PARTIAL (P11's local full matrices are recorded in `docs/state/mutation-scores.json`: 7 cores, shield 396/396, update 215/216 with one dispositioned equivalent mutant; the 24 h farm cadence remains) |
| — | Perf budget rows are browser measurements | needs a real browser + the reference uBO build | p99 decision ≤ 1 ms/request; memory ≤ 80 MB default sets; list apply ≤ 1.5 s background. Method: `docs/shield/perf.md` + `docs/qa/browser-harness.md` | NOT-RUN (sandbox numbers are `rig_class: trend` ⇒ NEUTRAL by rule; a trend rig may never assert MET) |
| — | Corpus parity against a 1,000-site browser capture | needs a browser to capture with | the in-repo corpus is band-checked against the vendored uBO-derived fixture; the real capture set is farm. Method: `docs/shield/parity.md` | NOT-RUN (method committed, not a number invented) |
| — | Dogfood 2 weeks full-time + breakage-triage rota (median < 48 h SLA) | ops act, needs a shipping build and a rota | the rota pipeline is P13-T5; the rota itself starts here | NOT-RUN |
| — | Signed-channel rotation drill on real keys | needs HG-36 custody | `xr-lists/tests/roundtrip.sh` runs the gpg sign/verify/tamper/wrong-key/hot-pin-out/replay matrix with the pinned TEST-ONLY key; the production rotation drill needs the ceremony HSM | PARTIAL (the local matrix runs green here; production rotation is HG-36-gated) |
