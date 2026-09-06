# ADR-0001: Repository topology and MPL-2.0 licensing for xr-browser / xr-core

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Deciders (humans):** XR Platform team (recorded by agent draft; human ratification tracked in `docs/state/repo-map.md` pending items)
- **Plan anchor:** Plan §7.1, §14 (L9, L16), Appendix B DR-04 / DR-05, §0.1 R1/R2 (overlay model)

## Context

Plan §7.1 mandates a two-repo topology (meta repo `xr-browser` + product
repo `xr-core`) plus separately-repoed helper processes (xr-vaultd, xr-tord,
xr-wgd, xr-inspect, xr-lists, xr-leaktest, xr-update-server, xr-web) that
are **not created in P1** — they land with their owning phases (P9/P10/P31/
P32). The product code is an *overlay repo* checked out into a pinned
Chromium tree at `src/xr` (Brave pattern, Plan §1.2; verified live:
`brave/brave-core` README "a set of changes, APIs, and scripts used for
customizing Chromium", 2026-09-07).

The plan's reconciled specs all converge on **MPL-2.0 for `//xr`** with
**GPL never linked** (DR-05 / DR-04). P1 is the moment the license choice
must be recorded *before the first import* (Plan §4 P1 "why": "MPL-2.0 +
GPL rules must exist before the first import").

Chromium itself is BSD-3-Clause (verified:
`chromium.googlesource.com/chromium/src/+/main/LICENSE`, 2026-09-07). An
MPL-2.0 overlay repo of *separately-authored files* does not create a
derivative work of the BSD-3 base; upstream files that XR modifies remain
BSD-3 and are tracked in the patch ledger (P3), never copied into `xr-core`.

## Decision

1. **Topology (P1 scope):** exactly two git repositories are initialized
   now: `xr-browser` (meta) and `xr-core` (product, sibling directory; will
   mount at `chromium/src/xr`). No helper repos are created in P1 — each
   gets its own repo at its owning phase, at which time it is also licensed
   (expected MPL-2.0 for uniformity; per-repo ADR note at creation time).
2. **License:** both P1 repositories are licensed **MPL-2.0** (full
   verbatim text in each repo's `LICENSE`). Rationale: *uniform file-level
   copyleft including tooling* — every file (C++ overlay, Rust helpers,
   Python governance tooling, docs) carries the same file-level license
   semantics; enterprise distribution (P39-T4) stays simple; per-file
   attribution is automatic; the plan's DR-05 is honored exactly.
3. **File-header policy (binding from P2):** every new source file added to
   `xr-core` carries the MPL-2.0 file header; governance files in
   `xr-browser` (docs, tools) are covered by the repo-root `LICENSE`
   (acceptable under MPL-2.0 §3.4 notice mechanics) and must not carry a
   *different* license header.
4. **GPL boundary (DR-04, effective from P1):** no GPL/AGPL/SSPL code is
   ever linked into any XR binary. Filter lists (EasyList et al.,
   GPLv3/CC-BY-SA 3.0 dual — verified 2026-09-07) are consumed **as data
   only** (Plan §1.5), with attribution sidecars (`LICENSE.data`) — enforced
   by `tools/license_audit.py` (header/inventory level; full dependency-
   graph resolution lands in P9-T9 — no overclaiming, L5).
5. **No premature structure:** `xr-core` contains governance files only in
   P1. Source directories, `BUILD.gn`, `DEPS`, and `patches/manifest.yaml`
   are created by P2/P3/P5 (Plan §4). Stubbing them now would fabricate
   architecture (L24, orchestrator anti-fabrication rule).

## Consequences

- Positive: single license regime across product + tooling; license audit
  tooling enforceable from commit #2; overlay compatibility with Chromium
  BSD-3 documented and clean.
- Negative / cost: MPL-2.0 file headers add boilerplate to every future
  source file (acceptable; tooling can generate them); per-file copyleft
  means any third party can fork individual files — intended and desired.
- Follow-ups: P2 (file-header tooling + `DEPS` pin policy), P9-T9 (full
  dep-graph license resolution), P28 (vendor keepass-rs with this ADR cited).

## Reversal

Reversing DR-05 (license) or DR-04 (no-GPL-linked) requires new written
evidence + a superseding ADR with counsel sign-off (see ADR-0002 reversal
discipline). No such evidence is anticipated; the Plan records these as
carry-forward settled decisions.
