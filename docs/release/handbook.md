# docs/release/handbook.md — the XR release engineering handbook v1

Status: living doc; the per-release checklist below is mirrored
(checkable) by `tools/release_gate.py` — "Every stable:" items are what
`release check --channel stable` enforces once P38 exists.

## Channels

| channel | served | auto-rollout | notes |
|---|---|---|---|
| dev | never (dev-only-until-P16-exit) | n/a | local builds only |
| nightly-test | yes, ramp 100% | yes | the test-verifier channel (core refuses release channels in test mode) |
| beta | yes, ramp <= 50% | REFUSED until P38 | pause points at 5/25/50% |
| stable | yes, ramp 100% (steps 1/10/50) | REFUSED until P38 | promotion is a human act |

## Epoch & revocation

One active epoch (`release/server/spec/epochs.yaml`); revocation notices
are signed by the key they name (production: root, HG-36) and applied via
`epoch-apply` — revoked is STICKY, stale (seq < cur) ignored, and a
revoked epoch forces the client manual path (About renders reason +
manual download + check-again). The client never downgrades: rollback =
server-side revocation + fix-forward (release/rollback/rollback.md).

## Cadence vs the Chromium train

XR rides the 2-week Chromium train (pinned in DEPS; chromium 152.0.7977.x
today). Promotions: beta/stable follow DR-26's 8-week promotion windows
with a 72 h security-response line for out-of-band train updates — the
out-of-band/emergency runbook is rehearsed in **P39** (say so, don't
improvise: the P39 drill owns the emergency path).

## Per-release checklist ("Every stable: …" — release check mirrors this)

- [ ] release gate green for the channel (`./scripts/build release check`)
- [ ] artifact signed by the channel's key (HG-36/37 credentials; Linux
      repo metadata: gpg clearsign InRelease + detached repomd.xml.asc)
- [ ] SBOM emitted + license report attached + unknown-license gate green
- [ ] attestation built for THIS artifact set, offline-verified, published
      (transparency; HG-38 for the log)
- [ ] consumed-upstream CVE table current (train-<n>.md, live-fetched)
- [ ] leak-report artifact for the train (P9 harness)
- [ ] rollout drill transcript (10/10 cells) + crash-hook input reviewed
      (no-auto-halt until P38)
- [ ] epoch state consistent (server spec + client epoch-apply; no
      pending stale notices)
- [ ] beta/stable promotion requires the P38 control plane — until then
      promotion is manual, witnessed, and recorded in this handbook's log

## Honesty rows (not yet true — docs/release/limitations)

- delta updates (>=60% size win): NOT measured; puffin/codec feasibility
  is research item 2, deferred with the measurement setup named.
- notarization: never run (no Apple account) — HG-37.
- SmartScreen reputation: not accrued (needs EV cert + install volume).
- transparency entries externally verifiable: BLOCKED (nothing published;
  HG-38).
- three-OS rollback rehearsal: farm-gated (HG-31/35).
