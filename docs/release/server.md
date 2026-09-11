# docs/release/server.md — the XR update server (P10-T2)

The server is a **stateless renderer**: request in, exact 3.1 response
bytes out. The language-neutral core lives in `release/server/spec/`
(data + `render-31.md` byte law); the reference implementation is
`release/server/refimpl/update_server_ref.py` (stdlib Python, runs in the
sandbox); the deployable is `release/server/rust/` (std-only Rust, zero
crates, `#![forbid(unsafe_code)]`).

- **Conformance**: `release/server/tests/conformance.json` — 51 cases,
  byte-exact against the reference here (`test_conformance_ref.py`) and
  against the deployable on the hosted runner (`tests/conformance.rs`).
- **Fuzz**: `release/server/tests/test_server_fuzz.py`, ≥600 s campaigns
  at 0 violations; oracle = never emit a manifest the verifier would
  accept without a valid signature/epoch; statelessness per-iteration.
- **Size**: ≤2048 B raw (measured 1379 B / 435 B gzip; see
  `tools/server_size_check.py`).
- **Privacy**: no accounts, no client identity, no logging; the only
  datum the server sees is the request the CLIENT chose to send (its
  channel/bucket/version — cohort buckets are computed client-side from
  a local random id, `update/core/cohort.cc`).
- **Deployment posture**: hosting + egress approval = HG-38 (human
  gate). The repo carries code + tests, never a live endpoint.
- **Emergency rollbacks**: server-side = epoch revocation notice
  (signed, `release/rollback/`); client-side = refuse-downgrade +
  forced manual path. Drill: `tools/rollout_drill.py` (real, here).
