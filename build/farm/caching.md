# Build caching — ccache (local) + remote-cache template

**Choice (ADR-0005, PROPOSED): ccache** for local object caching. Rationale:
Chromium has first-class `cc_wrapper` support (`cc_wrapper = "ccache"` in GN)
and reclient/RBE for the remote tier; sccache's Rust-cache advantage is
irrelevant to P2 (helpers land P4+ and Rust toolchains stay out of Chromium's
dep graph per Plan §7.1). ccache is the boring, correct choice.

## Local (every builder)

`build/farm/ccache-setup.sh` provisions `~/.ccache` with a max-size policy:

- `CCACHE_MAXSIZE=50G` per builder (sized for a full-Chromium cache).
- `CCACHE_COMPRESS=1` (the builders are disk-bound before CPU-bound).
- `CCACHE_SLOPPINESS` left default (no `time_macros` — determinism first, R0).

Wire it into GN: `cc_wrapper = "ccache"` is passed by the argsets at gen time
(the argsets do NOT set it today because no ccache binary is guaranteed
present; `./scripts/build gen` adds it when `ccache` is on PATH — see
`build/gn/gen.py`). Never vendored; the binary is a system/brew/winget
install.

## Remote cache (template only — no real endpoints)

The **remote-cache config template** is `ccache-setup.sh --remote-template`.
It emits a commented config with **no real endpoints** — placeholders only.
Per Plan P2-T4 this is a template; the endpoint + capacity sizing are
**HUMAN-GATED (HG-11)**. Integrity flags are ON in the template
(`CCACHE_SLOPPINESS` unset, hash-checked), because a poisoned remote cache is
a build-supply-chain vector (Plan §9.11).

## Cache poisoning guard

The template ships with integrity flags ON (no `CCACHE_RECACHE` off, no
`direct_mode` sloppiness), and `./scripts/build compile` re-runs `ccache -s` and fails
the lane if the hit rate is reported but hashes mismatch (documented in the
runbook `ci/README.md`). Remote cache is never a build-time *requirement*:
a cache miss is a slower build, never a failed one.
