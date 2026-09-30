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

## T0-U2 amendment: the final-CI claim must point at the phase's own head

Four consecutive phases saw the closing report and `origin`/hosted reality
diverge (P7 invented "no CI on push"; P8/P9 wrote "not pushed" while origin
had moved; P11 closed without its bundle; P12 reported a gate-green that only
exists in a hand-mutated environment). The gap: a `ci-run` row could cite any
green run at any head, and nothing linked the phase's final-CI claim to the
head the bundle itself records. Rule (a)'s head match compares a run's
`head_sha` against the bundle's `pin`/`repos` text — the *previous* phase's
close head — so a row citing P11's head could still stand as P12's "final CI
is green". The final-CI claim must be: **≥1 `ci-run` row whose `head_sha`
equals the bundle's own recorded head, for every workflow that ran on that
push.**

Rule (binds every bundle that declares `phase_head`; others grandfathered,
exactly like the P9-T12 scope):

1. The bundle declares `phase_head` — its recorded xr-browser HEAD (full
   sha) — and `ci_claimed` — the workflows it claims final-CI green for (a
   list, default `["governance"]`; `governance` is mandatory because it runs
   on every push to main). A phase that touched `xr-core` lanes or C++ cores
   also declares `core-hardening`.
2. For every claimed workflow the bundle must carry ≥1 `source: ci-run` row
   whose `head_sha` **equals `phase_head`** (7–40 hex, case-insensitive,
   prefix-matched both directions). A `ci-run` row may stamp `workflow`
   (default `governance`) and `head_sha`; a row citing an older head stays
   valid **for that row's own claim** but cannot stand as the phase's
   final-CI claim.
3. This check is STRUCTURAL (offline, deterministic): it is the bundle's
   internal consistency, not a network verdict — rule (a) remains the online
   greenness proof. The `--strict` transcript prints both heads compared
   (`phase_head=…` per candidate row), so a reader sees the comparison ran
   rather than trusting a silent pass.

Negative fixtures (registered in `tools/negatives/`): (i) a bundle whose only
`ci-run` row points at a parent commit ⇒ FAIL; (ii) missing `core-hardening`
where the phase touched a core ⇒ FAIL; (iii) a green-but-stale row after the
SHA advanced ⇒ FAIL.

Row-level fields added by these amendments: `corrects` (string id of the row
an appended correction row corrects); `head_sha` and `workflow` (ci-run
rows). Bundle-level fields: `phase_head`, `ci_claimed`. Ledger schema:
`runner-capabilities-v1` — `capabilities: {<tool>: {present: true|false|
"UNOBSERVED", version?, note?, proven_by: [{ci_run, ci_job, workflow?,
job?, step?, head?, log?, date, note?}]}}`; `present: true/false` requires
non-empty `proven_by` with `ci_run`+`ci_job` or a `log` path, plus `date`;
`UNOBSERVED` requires a `note` and forbids `version`.

---

## `state: interim | final`, and WHEN the closing form binds (P13-C-P0-C / P13-C-P0.3)

Every bundle declares its own lifecycle. It has to: the **presence law**
(`tools/evidence_presence_check.py`) requires a phase's bundle to exist from
that phase's FIRST commit, and a bundle that must exist from commit one cannot
be `final` from commit one.

    state  "interim" | "final".   ABSENT MEANS FINAL — silence is a claim.

* **`interim`** is legal in exactly two cases (P13-C-P0.4):
  1. the phase the tree declares in flight (`docs/state/phase-base.json`) — its
     rows may use `*-PENDING-*` sentinels and the final rules do not apply; or
  2. **declared in writing**: any other phase, provided at least one
     `not_done_by_design` row OPENS with an ISO date. It then prints
     `finality: <phase>: interim — DECLARED, not the in-flight phase` naming the
     dated rows, the T0-U2 same-head claim does not bind it (it has made no
     final-CI claim; `phase_head`/`ci_claimed` are its recorded *intent*), and
     `partial work` is not a free pass — an undated interim has no author and no
     date on it and is a FAILURE.

  Either way, an `interim` bundle for a phase that CLAIMS closure is a FAILURE —
  that is the "interim at the closing commit" hole this law exists to close. The
  second case exists because a phase can land its substance while its same-head
  CI claim is unmakeable (no green run at its recorded head, and a run four
  commits back cannot be created); the alternatives are to cite someone else's
  green run — the exact evasion T0-U2 stops — or to say so out loud, dated.
* **`final`** means every effective row status is in the final vocabulary
  (`VERIFIED`, `PARTIAL`, `BLOCKED`, `BLOCKED-<CAUSE>`, `HUMAN-GATED`,
  `NOT-BY-DESIGN`); no effective status may carry `PENDING`; `phase_head` must be
  declared; `ci_claimed` must name `governance` (plus `core-hardening` when a
  core was touched); and `evidence/P<n>/report.md` must exist carrying the
  12-section report.
* **Append-only corrections**: a row whose id appears in a later row's
  `corrects` field is SUPERSEDED — the later row's status is effective and the
  original text stays in place. History is not rewritten.

### The closing form: `--require-phase-final` binds on a CLAIM

`tools/evidence_check.py --strict --require-phase-final` is the closing
invocation. It does **not** infer that a phase is closing from its position in
any list — position-based triggering made the law unsatisfiable for the in-flight
phase (the demand was `final`; the presence law demanded the bundle from commit
one), so `governance` was red for the whole of every future phase while
reporting a demand no commit could meet.

**Closure is claimed.** A commit that closes a phase carries a trailer, in the
same discipline `tools/dr_parse.py --check-trailers` applies to
`Register-Change:` (ADR-0002 §2):

```
P13-C-CLOSE: close the phase

<free text>

Phase-Close: P13
```

With the trailer, that phase's bundle must be `final`, with `report.md` and a
`ci-run` row at the phase's own recorded head for every claimed workflow.
Without it the flag is a no-op that SAYS SO rather than passing silently:

```
finality: P13 interim (phase open; no closure claimed) — not a verdict
```

The word "verdict" is load-bearing: a pass that judged nothing must not be
readable as a pass that judged everything.

CI passes its push range (`tools/run_checks.sh --phase-final --via-ci-invocation
"$RANGE"` → `--range` here), so every commit in the range may carry the claim;
without `--range` only `HEAD` is read.

**Negatives** (`tools/negatives/p13_c03.sh`, N=4): trailer + `interim` ⇒ FAIL;
no trailer + `interim` ⇒ PASS **with the note**; trailer + `final` without a
same-head `ci-run` ⇒ FAIL; and a `final` bundle with no trailer is still judged
by the ordinary final rules — the carve-out is for an OPEN phase, never a shield
for a bad bundle.
