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

## Running it

```bash
python3 tools/evidence_check.py                 # structural, all bundles
python3 tools/evidence_check.py --strict        # + paths resolve + source labels
python3 tools/evidence_check.py --json
```

Exit `0` pass · `1` fail (reasons printed) · `2` usage error.
