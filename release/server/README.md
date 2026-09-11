# release/server — xr-updateserver (P10-T2)

Status: **local-real (reference)** · deployable **runner-ready (Rust lane
proves itself on the hosted runner; the dev sandbox has no cargo)** ·
hosting/egress = HG-38 (human-gated).

## Layout

```
spec/            the LANGUAGE-NEUTRAL core: version-graph / channels /
                 cohorts / epochs YAMLs + render-31.md (the byte law) +
                 README.md (GENERATED, --check diff-clean)
refimpl/         update_server_ref.py — stdlib Python reference; pure,
                 stateless, no network; --self-check
rust/            the DEPLOYABLE: std-only Rust, ZERO crates,
                 #![forbid(unsafe_code)]; byte-parity with the reference
                 enforced by tests/conformance.rs (hosted runner)
tests/           conformance.json (51 cases, committed data),
                 test_conformance_ref.py (reference half, runs here),
                 test_server_fuzz.py (>=600 s never-accept oracle)
```

## The invariants (all machine-checked)

1. **Byte-parity across the language boundary**: the corpus pins exact
   response bytes; any divergence between the reference and the Rust
   deployable is a red gate (P9 differential-parity lesson).
2. **Stateless**: a request handled twice yields identical bytes; the
   server holds no per-client state (`daystart.elapsed_days: 0` is not a
   placeholder, it is the honesty row). After an epoch revocation lands
   in the spec, the bytes differ — that is the only "state".
3. **Never-accept**: the fuzzer re-verifies every 200 with the client's
   own stub rules — no manifest renders without a valid signature over
   the canonical response under the pinned epoch key.
4. **Refusals are typed and closed**: unknown fields at any level, wrong
   protocol, non-canonical versions, bad buckets, oversized/short/long
   bodies — canonical `{detail, error}` bytes, HTTP 400, exit 1 on the CLI.
5. **Size law**: response ≤ 2048 bytes raw on the largest realistic case
   (`tools/server_size_check.py`: 1379 B raw / 435 B gzip measured).

## What this service is NOT

No accounts, no client identity, no telemetry, no logging (the lane
prints nothing but response bytes). The update egress policy is
`docs/release/egress.md` + `release/egress-allowlist.json`; hosting the
deployable anywhere is HG-38 — a human decision with an egress review,
never a sandbox act.
