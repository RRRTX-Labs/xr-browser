# Fuzzing fleet (P9-T8)

The four C++ cores each ship an **in-house seeded fuzzer** (built by their
own `make test`, g++ only) and a **CI-side clang/libFuzzer entry point**
(`build/fuzz/libfuzzer/`). The fleet (data in `build/fuzz/fleet.yaml`,
runner `tools/fuzz_fleet.py`) runs the in-house fuzzers under the timebox
law and gates the libFuzzer lane's corpus.

## Why both

- The in-house fuzzer is the **gate**: it runs everywhere g++ runs (this
  sandbox included) and enforces its own danger-class invariants (a fuzz that
  never hits a page-source proves nothing — P7's words).
- libFuzzer is the **depth** campaign, CI-side only: this sandbox has no
  clang, so the entry points compile and run only on the CI lane (HG-28).

## Fleet (build/fuzz/fleet.yaml)

| id | core | in-house runner | libFuzzer target |
|---|---|---|---|
| policy-core | policy | `tools/policy_fuzz.py` (python harness around `policy_host`) | `policy_resolve_fuzz` |
| commands-core | commands | `commands/tests/build/test_fuzz` | `commands_dispatch_fuzz` |
| settings-core | settings | `settings/tests/build/test_settings_fuzz` | `settings_core_fuzz` |
| themes-core | themes | `themes/tests/build/test_fuzz` | `themes_loader_fuzz` |

`not_yet:` rows record the plan's Rust + Mojo-bind targets with their owning
phase — recorded, never fabricated (no rustc, no clang, no browser process
here).

## Commands

```sh
# gate: >=60 s per target, min-iters floor, corpus dirs must be seeded
python3 tools/fuzz_fleet.py --repo . --timebox 60

# evidence campaign (the T0-a pattern: >=600 s via XR_FUZZ_SECONDS)
XR_FUZZ_SECONDS=600 python3 tools/fuzz_fleet.py --repo .

# contract-driven Mojo request generator (4 hosts; deterministic)
python3 tools/mojom_fuzz_gen.py --repo . --count 1000 --seed 20260910

# corpus derivation (real artifacts only) + drift check
python3 tools/seed_corpus.py --repo .
python3 tools/seed_corpus.py --repo . --check
```

## Laws

1. **Timebox law** — `>=60 s` in the gate, `>=600 s` in evidence
   (`XR_FUZZ_SECONDS`). Both are enforced, not suggested.
2. **Empty-run law** — a target that executed nothing, and a corpus dir with
   no seeds, are FAILURES. `policy_fuzz.py` gained `--min-iters` this phase
   (default 100).
3. **Determinism law** — same seed => same bytes (`mojom_fuzz_gen`,
   `seed_corpus --check`, and every in-house fuzzer's fixed seed).
4. **cwd law** — in-house fuzz binaries read their schema relative to their
   tests dir (`../../<core>/core/*.json`); the fleet runs them from the
   Makefile dir exactly as `make -C <core>/tests test` does.

## Corpus

`build/fuzz/corpus/<target>/` is derived by `tools/seed_corpus.py` from the
frozen P5 fixtures (`xr-core/fakes/fixtures/*`) and the P9-T0-a parity
corpora — byte-copies of committed artifacts, never placeholder synthesis.
The libFuzzer lane consumes them; the fleet gate fails if any dir is empty.

## Farm rows

- **HG-28** — the 24 h campaign: `python3 tools/policy_fuzz.py --timebox
  86400 --seed <fixed>` (policy), and the CI libFuzzer jobs for the other
  three cores.
- **HG-29** — Mojo bind-side fuzzing (clang + browser process; the
  generator `tools/mojom_fuzz_gen.py` runs today, the driver is P16).
