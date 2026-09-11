# Contract: evidence bundle v1 (`evidence/<PHASE>/evidence.json`)

**Status:** active · **Introduced:** P4-T0.3 (debt D-C) · **Validator:**
`tools/evidence_check.py` (stdlib, no new dependencies) · **Owner:** A lead
(Platform/Chromium)

## Why a contract and not a convention

P1 and P2 each shipped an `evidence.json` + `human-gates.md`. P3 shipped
neither and still reported "104 tests pass" — a claim that was true only in a
pre-seeded environment and was contradicted by nine red hosted runs at
`e35f332`. Nothing in the tree could have caught that, because the standard
was a habit rather than a gate. This contract makes it a gate, and
`run_checks.sh` enforces it for every phase directory.

## Layout

```
evidence/<PHASE>/evidence.json      # machine-checked (this contract)
evidence/<PHASE>/human-gates.md     # the human actions this phase cannot do
evidence/<PHASE>/logs/*             # raw transcripts the JSON cites
```

## Required top-level keys

| key | type | meaning |
|---|---|---|
| `phase` | string | e.g. `P4 — Identity-seam spike` |
| `generated` | string | ISO date the bundle was produced |
| `plan` | string | path of the pinned plan the DoD rows came from |
| `dod_rows` | list **or** dict | one row per Definition-of-Done item |

Optional: `repos`, `tasks`, `verdict_vocabulary`, `policy`, `human_gates`,
`not_done_by_design`, `supersedes`, `source_labels`, `sources`,
`toolchain_capture`.

A row: `{"id", "dod", "status", "evidence": [...], "notes"?, "source"?}`.
`dod_rows` may also be a mapping of id → row (P2's shipped shape); the
validator accepts both.

## Verdict vocabulary

`VERIFIED` · `HUMAN-GATED` · `SIMULATED` · `BLOCKED-*`.

- **VERIFIED** — executed here, artifact cited, path resolves under `--strict`.
- **HUMAN-GATED** — requires a human act; carries a `gate` id.
- **SIMULATED** — fixture/dry-run execution that is honest about being a
  rehearsal; never presented as the real thing (drills label
  `elapsed_real_seconds` vs `simulated_elapsed_hours`).
- **BLOCKED-*** — stopped, with the reason in the suffix (`BLOCKED-NET`,
  `BLOCKED-PENDING-PUSH`, …). A blocked row is a result, never a hidden gap.

P1/P2 bundles use qualified statuses (`VERIFIED (mock; …)`); the validator
accepts the leading token for legacy bundles. **New bundles run `--strict`
and must use bare tokens.**

## Source labels (`--strict`)

When a bundle declares `source_labels`, every row must carry a `source` from
that list. P4 uses: `static` (source/byte measurement), `fixture` (synthetic
data), `real-fetch` (bytes fetched through `build/upstream/fetch.py`),
`hosted-ci` (GitHub API/run evidence), `local-run` (executed in this
workspace).

A bundle that declares source labels and omits one is a failure — this is the
rule that stops an unlabelled fixture result from reading as a real
measurement.

## Anti-fabrication rules (L11)

1. A row may not claim `VERIFIED` without citing at least one artifact path.
2. Under `--strict`, every cited path must exist (relative to the phase
   directory, else the repo root).
3. `evidence/<PHASE>/human-gates.md` must exist and be non-empty — a phase
   with no recorded human gates is not closed.
4. Nothing may be recorded as executed when it was not; un-run work is
   `BLOCKED-*` or `HUMAN-GATED`, never `VERIFIED`.

## Strict scope (auto-covers new bundles — T0)

`--strict` with no `--only` covers **every `P<n>` bundle newer than the P2
legacy exemption (P3+)**, discovered from the `evidence/` directory — P1/P2
stay exempt per the HG-25 ruling (their qualified statuses). A new phase is
gated the moment its bundle lands; there is no hardcoded list to forget (the
P6/P7 debt this rule closes — `run_checks.sh` used to pin `--only P3,P4,P5`).

## Machine-side green + run ids (P9-T12)

Plan §11.15 fixes the evidence row shape as `{suite, run_id, commit,
artifact_url, verdict, links}`, and P9-T12's convention: **"green" is
defined machine-side**. In this repo that means the validator itself
enforces (for every `P<n>` bundle with `n >= 9`):

1. **(a) ci-run rows.** A row with `source: ci-run` must carry `ci_run` and
   `ci_job` ids. Under `--strict` the validator resolves them through
   `build/upstream/fetch.py` (the chokepoint; api.github.com is allowlisted):
   a run whose job did not conclude `success`, or whose `head_sha` is not a
   commit the bundle's `pin`/`repos` block records, is a FAIL; offline is a
   visible `SKIP` (printed to stderr). A run id is never fabricated.
2. **(b) explained open rows.** Any row whose status is
   `PARTIAL`/`BLOCKED*`/`HUMAN-GATED` requires the bundle's
   `not_done_by_design` to be a non-empty list — P8 shipped `[]` while work
   was partial; that hole closes here.
3. **(c) transcripts.** A `local-run` row must cite at least one `logs/*`
   transcript (and every cited path must exist, per the citation rule).

P1–P8 predate these rules and stay grandfathered (P6 has a HUMAN-GATED row
with no `not_done_by_design`); P9's own bundle is the first checked under
them. A verdict is only `VERIFIED` when a runner computed it, and a human
edit to a verdict without an attached ADR is an anti-fabrication violation
(L11).

## Running it

```bash
python3 tools/evidence_check.py                 # structural, all bundles
python3 tools/evidence_check.py --strict        # auto-covers P3+ (paths + source labels)
python3 tools/evidence_check.py --strict --only P6,P7   # or an explicit list
python3 tools/evidence_check.py --json
```

Exit `0` pass · `1` fail (reasons printed) · `2` usage error.

## P11-T0-d amendments: hosted claims need ci-run rows; stale BLOCKED fails

`--strict` tightening, scoped exactly like the P9-T12 rules (bundles P9+):

1. **(d) A hosted claim needs a ci-run citation.** A VERIFIED row whose own
   `dod`/`notes`/`evidence` text claims hosted execution (`hosted`,
   `GitHub Actions`, `on the runner`) passes only if the row itself carries
   `source: ci-run` (with `ci_run`+`ci_job`, resolved machine-side per rule
   (a)), OR the bundle carries an APPENDED correction row — `source: ci-run`
   with `"corrects": "<row-id>"` — supplying the citation. Correction rows
   are the append-only mechanism: a prior phase's row is NEVER edited to
   satisfy this rule; its history is recorded once and the correction lands
   beside it. Motivating case: P10-DOD-2 shipped BLOCKED ("no cargo in
   sandbox"), was flipped to VERIFIED by hand once the hosted runs went
   green, and nothing in the validator could resolve the hosted half of the
   claim until P10-DOD-2-C1 landed.
2. **(e) A stale BLOCKED row fails.** A BLOCKED-* row whose blocker is the
   absence of a tool that is PROVEN PRESENT is stale and must be re-run and
   re-recorded (or re-argued in the row). Presence is proven by
   `docs/state/runner-capabilities.json` — the runner-capabilities ledger,
   where every present/absent entry cites the real hosted run(s) or
   transcript that observed it (`tools/runner_caps.py --check` refuses
   comment-claims; `go` stays UNOBSERVED because no lane ever printed it) —
   or by this sandbox (`which`). An absent ledger makes rule (e) inert with
   a visible SKIP line, never silently.

Row-level fields added by this amendment: `corrects` (string id of the row
an appended correction row corrects). Ledger schema:
`runner-capabilities-v1` — `capabilities: {<tool>: {present: true|false|
"UNOBSERVED", version?, note?, proven_by: [{ci_run, ci_job, workflow?,
job?, step?, head?, log?, date, note?}]}}`; `present: true/false` requires
non-empty `proven_by` with `ci_run`+`ci_job` or a `log` path, plus `date`;
`UNOBSERVED` requires a `note` and forbids `version`.
