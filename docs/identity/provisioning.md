# Identity provisioning (P14-T1)

Status: core shipped + tested (`xr-core/identity/`); the browser half
(seam wiring into `CreateTargetContents`) is the NOT-RUN half of the seam
decision (see `docs/state/research-log-P14.md` §"seam decision"). Nothing
in this doc claims a browser-measured outcome.

## The mint (opaque by construction)

* The partition domain is `xr:` + a UUID-v4 rendering of sha256(CALLER
  ENTROPY) — `xr-core/identity/core/mint.{h,cc}`. No name, site, URL, or
  guessable string can appear in it: `LooksOpaque` enforces the shape and
  rejects any domain that literally embeds a probe string (the P4 census
  corpus: partition name, title, log line, site — `test_mint.cc`).
* The mint is a PURE function: no clock, no RNG, no counter. The PRODUCTION
  HOST must supply OS entropy per call (`identity_host provision
  {"entropy": …}` — the living subcommand REFUSES to mint without it, so
  the host cannot accidentally mint from the fixture table).
* The frozen fixture table (the P5 fake's `_MINTS`, including its 40-char
  third entry — a frozen quirk, documented in `mint.h`) exists for
  byte-stable vectors ONLY (`provision {"replay": true}`; exhaustion is a
  typed refusal, never a silent fallback).

## Overlay rows + the per-identity prefs namespace

* A template's rows (see `templates.md`) merge under the user's overrides
  at provisioning; the result is the identity's OWN prefs namespace, keyed
  by the opaque domain (never the display name — the store refuses
  name-keyed inserts; the §1.1 separation bug is unrepresentable).
* Fail-safe law (`identity.h`, tested): an identity whose namespace cannot
  be READ yields "no overrides" (`resolve-pref` → `value: null`) — the
  caller applies the restrictive default. Unreadable ⇒ closed, never
  "all defaults allowed".

## Invocation (the host)

`xr-core/identity/host_protocol.md` is the contract. Frozen mojom surface:
`identity_host '{"method":"Create",…}'` (byte-parity with
`fakes/identity.py`, corpus-locked). Living surface:
`identity_host provision '{"entropy":"…","template_id":"work",…}'`.

## NOT-RUN here (methods, not surrogates)

* Runtime partition behaviour, `wake ≤ 200 ms to first paint`, per-identity
  DNS isolation: `docs/qa/browser-harness.md` (the rig lane).
* The seam wiring itself: HG-9 / the seam-decision section.
