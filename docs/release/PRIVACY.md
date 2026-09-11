# docs/release/PRIVACY.md — the update-path privacy statement (P10)

What the update server sees: a request the CLIENT chose to send —
channel, cohort bucket, current version. That is all.

- The **cohort bucket** is computed on-device from a LOCAL random install
  id (`xr-core/update/core/cohort.cc`); the install id never leaves the
  device. Buckets carry no identity (100 values, reshuffled per channel).
- The server keeps **no state and no logs** (statelessness is a
  conformance-asserted property: the same request twice → identical
  bytes; `release/server/README.md`).
- No accounts, no cookies, no client certificates, no A/B identifiers on
  the update path. The epoch is a public key id, not a device id.
- Failures are rendered locally (About shows reason + manual path); a
  failed update never phones home.
- The signature verifier is TLS-independent: privacy does not depend on a
  CA vouching for the update server, and the server cannot be asked to
  personalize an offer (it cannot see anything to personalize with).
