# ADR-0005: Build caching — ccache (local) + remote-cache template, human-gated remote

- **Status:** PROPOSED
- **Date:** 2026-09-07
- **Deciders (humans):** Principal, RRRTX Labs (agents draft, humans decide — ADR-0002 §4)
- **Plan anchor:** Plan §4 Phase P2 task T4 (ccache + remote cache + build-farm
  bring-up); §13.1 (pools & pipelines); §9.11 (supply-chain discipline);
  §13.7 R0 (reproducibility rung: pinned inputs first).

## Context

P2 chose the local object-cache tool and recorded the rationale in
`build/farm/caching.md` (the P2 prose of record):

- **ccache** for local caching on every builder. Chromium has first-class
  `cc_wrapper` support (`cc_wrapper = "ccache"` in GN) and reclient/RBE for
  the remote tier. sccache's Rust-cache advantage is irrelevant pre-P4
  (Rust helpers land P4+ and Rust toolchains stay out of Chromium's dep
  graph per Plan §7.1). "The boring, correct choice."
- `build/farm/ccache-setup.sh` provisions `~/.ccache` with
  `CCACHE_MAXSIZE=50G` (full-Chromium-cache sized), `CCACHE_COMPRESS=1`
  (builders are disk-bound before CPU-bound), default `CCACHE_SLOPPINESS`
  (no `time_macros` — determinism first, R0).
- The **remote-cache config template** (`ccache-setup.sh --remote-template`)
  emits a commented config with **no real endpoints** — placeholders only.
  Endpoint + capacity sizing are **HUMAN-GATED (HG-11)**.
- **Cache-poisoning guard:** integrity flags stay ON (no `direct_mode`
  sloppiness, no `CCACHE_RECACHE` relaxation) because a poisoned remote
  cache is a build-supply-chain vector (Plan §9.11). A cache miss is a
  slower build, never a failed one; remote cache is never a build-time
  requirement.

What is *not* being decided here: the remote-cache endpoint/provider and
capacity sizing (HG-11), and the reclient/RBE evaluation (P10-era farm
decision).

## Decision

1. **ccache** is the local build cache for the XR build farm (all 3 OS).
2. The remote cache remains a **template only** until HG-11 approves an
   endpoint; integrity flags are non-negotiable and any future change to
   them requires superseding this ADR.
3. Cache statistics are lane evidence (`./scripts/build compile` reports
   them); a cache is an accelerator, never a correctness dependency.

## Consequences

- Deterministic-input discipline (R0) is preserved: caching never loosens
  sloppiness settings to raise hit rates.
- Farm bring-up (HG-9/10) can proceed with local caching alone; the remote
  tier is a later, separately-gated optimization.
- Approving this ADR ratifies the P2 choice; rejecting it requires naming
  the replacement cache tool with a Chromium-`cc_wrapper` compatibility
  story before farm bring-up.
