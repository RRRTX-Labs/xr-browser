# ADR-0006: `build/` directory vs. `./build` dispatcher collision — entrypoint moves to `scripts/build`

- **Status:** PROPOSED
- **Date:** 2026-09-07
- **Deciders (humans):** Principal, RRRTX Labs (agents draft, humans decide — ADR-0002 §4)
- **Plan anchor:** Plan §7.1 (topology: `xr-browser/build/` directory and
  `scripts/ — fetch/apply/rebase/release entrypoints (python, typed)`);
  Plan §4 Phase P2 Objective ("`./build x` reproduces a branded … binary");
  P3-T0.4 (D3: `buildsys/` name deviation from §7.1).

## Context

The Master Plan requires two things that collide on the filesystem:

1. §7.1 places the build assets in a **directory** `xr-browser/build/`
   ("GN argsets, toolchain pins, branding inputs, packaging defs"), and
   §4 P2 "Touches" lists `xr-browser/build/`. The P3-T0.4 remediation
   (defect D3) mandates `git mv buildsys build`.
2. §4 P2's Objective names the entrypoint **`./build x`**, which P2
   implemented as an executable **file** at the repo root.

A file and a directory cannot share the name `build` in one parent
(`git mv buildsys build` fails while the dispatcher file exists). One of
the two must give; this ADR records which and why.

What is *not* being decided here: the subcommand surface (unchanged), the
tool modules under `build/` (unchanged locations relative to the renamed
root), or any Plan amendment (the pinned Plan text keeps its `./build x`
phrasing; this ADR is the mapping of record).

## Decision

1. **The directory wins the name.** `buildsys/` is renamed to `build/`
   (satisfies §7.1 and closes D3 as instructed).
2. **The entrypoint moves to `scripts/build`** — a typed Python dispatcher
   (executable), which is exactly §7.1's designated home: "`scripts/` —
   fetch/apply/rebase/release entrypoints (python, typed)". The P2
   bash case-statement dispatcher is retired; its subcommand surface is
   preserved one-to-one and P3's new subcommands (`rebase`, `audit`,
   `sla`, …) are declared in one mapping (`SUBCOMMANDS` in
   `scripts/build`).
3. **Invocation of record:** `./scripts/build <subcommand>` (e.g.
   `./scripts/build sync`, `./scripts/build rebase --to <rev>`). Docs,
   CI definitions and contracts cite this form; historical documents
   (PHASE1/2_RELEASE, evidence/) keep their original `./build …` text as
   records of what ran at the time.
4. The Plan's "`./build x`" objective phrase is satisfied **in spirit**:
   one entrypoint, stable subcommand grammar — with the path prefix
   changed by this collision. This ADR is the documented bridge; it is
   PROPOSED until a human decider ratifies (or rejects) the relocation.

Rejected alternatives:
- *Keep `./build` file, keep `buildsys/` dir name* — leaves D3 open
  (deviation from §7.1 persists).
- *Keep `./build` file, name the dir something else* — invents a third
  name §7.1 never sanctioned.
- *Bootstrap-generated root `./build` symlink* — makes the repo
  non-functional on fresh clone until a setup step runs; worst option
  for a governance-obsessed repo.
- *Dispatcher at `build/x`* — a pun on the objective phrase ("./build x")
  that survives as a confusing filename; rejected for clarity.

## Consequences

- All living docs/CI teach `./scripts/build`; the endpoint-deny scan
  (`brand_check.py`) covers the new `scripts/` directory.
- Every subsequent phase's tooling lands under `build/` with subcommands
  registered in `scripts/build` (single dispatch table).
- If rejected by the decider, the fallback is the first rejected
  alternative above and D3 re-opens with a Plan-amendment request
  (docs/process/plan-amendment.md).
