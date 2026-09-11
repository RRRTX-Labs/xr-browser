# docs/release/egress.md — the update-channel egress policy (P10)

The update channel must not become a data channel.

- **Client egress**: exactly one origin — `updates.rrrtx.labs:443` for
  update checks and artifact downloads
  (`release/egress-allowlist.json`; HG-38 approves the host). No
  telemetry, no crash funnel, no CDN personality detection, no OCSP
  stapling callback of ours. The verifier is TLS-independent BY LAW: a
  proxy cannot flip an update (bad TLS + good signature ⇒ accept; good
  TLS + bad signature ⇒ deny — tested, not asserted,
  `update/tests/test_verify_policy`).
- **Server egress**: NONE. `release/server/` (both backends) is a
  stateless renderer — it fetches nothing, calls nothing, logs nothing
  (the log-scrub law). The spec data (version graph, epochs) is baked at
  release time from this repository.
- **fetch.py ALLOWED_HOSTS is untouched by P10** (chromiumdash reads
  remain the P3 choke point); this release egress policy is the separate,
  HG-38-owned surface. Adding a fourth network egress = P10 failure
  condition 4 (stop and report, never an allowlist edit).
