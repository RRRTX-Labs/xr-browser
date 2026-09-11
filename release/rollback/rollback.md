# release/rollback/ — the rollback contract (P10-T5)

A rollback is **never** a downgrade offer. The client refuses downgrades
by law (`update/core/verify_policy.cc`: older ⇒ `downgrade` deny, no
auto-rollback), so rolling back means changing what the SERVER offers and,
when the new build itself is harmful, revoking the epoch.

## Server-side (the only safe lever): epoch revocation

1. Publish the signed revocation notice (root-signed, wrapper exactly
   `{body, signature}`): `release/keys/key-hierarchy.md` §epoch revocation
   runbook, steps 1–4.
2. The server stops offering (`error-epochRevoked` for affected clients —
   `release/server/spec/epochs.yaml` + conformance case
   `epoch-revoked-typed-error`).
3. Clients `epoch-apply` the notice: `revoked` sticky, `manual_path`
   forced — the About view renders the reason + manual download + "check
   again" (no silent failures). Stale notices (seq ≤ current) are
   ignored — monotonic.
4. Fix forward: the next epoch id + key re-opens updates (rotation runbook).

## Client-side (already law, drilled): refuse-downgrade + replay

- `downgrade` deny — the server can never talk a client backwards.
- replay deny — a served response cannot be re-fed (SeenSet FIFO,
  4096, persisted; corrupt store ⇒ refuse updates, never guess).
- The drill (`tools/rollout_drill.py`) executes ALL of these cells for
  real here against the reference server + the compiled verifier core.

## What rollback is NOT

No automatic version reversion, no "rollback flag" the server flips per
client, no trust-on-server kill switch beyond the signed epoch notice
(TLS-independent by construction). The farm rehearsal on three OSes
(physical Apple/Windows hardware, real notarized builds) stays
**farm/human** (`docs/release/rollback-drill.md` — HG row HG-31/35
class), exactly like the plan's DoD row says.
