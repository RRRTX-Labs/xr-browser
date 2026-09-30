# ADR-0049: `panel-tab-registration-v1` — panel tabs are declared, and the §10 unit follows

- **Status:** PROPOSED (drafted by the P13-CLOSE coding agent; ratification rides
  HG-26/HG-35 — agents draft, humans decide)
- **Date:** 2026-09-30
- **Deciders (humans):** WebUI lead + Platform lead (§10 is a shipped-feature law,
  and this ADR changes what its unit IS)
- **Plan anchor:** §10 ("any feature without a command does not ship"; every
  Settings section and panel tab maps to a command) and §4 P13-T6.

## Context

The §10 lane (`tools/coverage_check.py`) scans `ui/{settings,panel}/**/*.ts` and
demands each file map to a registered command. Measured at `e503f9e`, that unit
was wrong: `focus-trap.ts` (focus containment) and `panel-frame.ts` (chrome) are
not tabs, and they read as unaccounted features — the red that opened P13.

Four fixes were available, and three were forbidden by the brief for the same
reason (they all make the law quieter):

| Candidate fix | Why not |
|---|---|
| exempt `ui/panel/` files whose names are not tabs | a directory exemption; the next file gets the same treatment |
| synthesise a command (or a tab) per file | a fake; the law would be satisfied by a name |
| widen the scan / add a `skip:` list | weakening the check, the class the brief names explicitly |
| **declare the unit** | the file-to-feature ambiguity is the defect, not the scan |

## Decision

A panel tab is a **declared registration** — `{id, title_msgid, order,
requires_identity_scope}` — listed in `xr-core/ui/panel/tabs.json` (the
inventory) and validated by `docs/contracts/panel-tab-registration-v1.schema.json`.
The §10 lane's unit is that declaration; a landed `.ts` file is claimed by exactly
one surface's `sources:` list, and a file nobody claims is a finding rather than a
tab. The runtime half (`ui/panel/tab-registry.ts`) refuses unknown ids and
collisions with typed errors; the gate half (`tools/panel_registry_check.py`)
holds the schema, the vectors, the msgid table, the `sources:` claim and the
bypass law.

`focus-trap.ts`, `panel-frame.ts`, `tab-registry.ts` and `tab-strip.ts` are
claimed by the frame surface `panel/xr` — a `unit: frame` entry, not a tab. That
is a statement about what those files ARE, which is what the old scan could not
express.

## Consequences

* Adding a tab is a declaration plus a `sources:` claim plus a command; the three
  are checked in one lane pair, and the register cannot drift in one direction.
* The inventory is additive-only; orders are spaced by 10 so insertion does not
  renumber (deep links survive).
* A subsystem that hardcodes itself into the frame instead of registering is now
  a named failure (`tools/negatives/p13_c5.sh` case 1).
* P14 (Identity v1) becomes the first non-Shield consumer of this API; the tab
  API's `requires_identity_scope` field is the hook its identity switcher will
  use, and the per-identity allowlisted query P14 must implement for real is
  named in `evidence/P13/report.md` §12.

## Alternatives rejected

A per-file `tab: true` marker comment (unverifiable at runtime — a comment
cannot refuse a registration), and a build-time codegen step (the toolchain is
pinned and small; codegen would add a pin for a five-row table).
