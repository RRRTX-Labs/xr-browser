# docs/shield/privacy.md — the block-log privacy statement (P11-T6)

The shield's activity ledger records decisions, not browsing. This is the
`docs/release/PRIVACY.md`-style statement of record for the block log
(plan P11 law 8); every claim below is machine-pinned, and the pin is
cited inline.

## What a BlockEvent row carries — the minimum the ledger allows

A `block-event-v1` row (schema: `docs/contracts/block-event-v1.schema.json`;
generator: `xr-core/shield/core/events.cc`) carries exactly: the
caller-supplied `ts_millis` and monotonic `seq`, the browser-assigned
`identity.value`, `tab_id`, the `origin` pair (`scheme`,
`registrable_domain`), the REDACTED `target` (`scheme://host/path`), the
matched `rule` text, `list_provenance`, the frozen `action` k-spelling,
`request_class`, the closed-set `why_code`, and optional rule/list/bundle
provenance ids. Nothing else parses: unknown fields are refused at every
nesting level (strict deny-on-unknown, both backends).

## No full URLs — redaction at creation, byte-proven

Query strings and fragments are stripped BEFORE a row is written; they
never reach the ledger, a ring, or the dev page.

- Golden-vector pin (both backends, byte-identical):
  `e-emit-redact-shop` in `docs/contracts/vectors/shield-v1.json` feeds
  `https://shop.example/cart?cc=4111111111111111#pay` and the serialized
  row's `target` is `https://shop.example/cart` — the query (a card
  number, deliberately) and the fragment are gone. `e-emit-redact-port`
  pins the port handling. Any backend that stops redacting DRIFTS the
  vectors and reddens `tools/shield_vectors_check.py` +
  `xr-core/shield/tests/test_golden_vectors.cc` (the negative canary
  `tools/negatives/p11_t5.sh::case_t5_vectors_drift` proves the gate can
  fail).
- C++ unit pins: `xr-core/shield/tests/test_events.cc` /
  `test_context.cc` (redaction at creation on the compiled side).

## No cross-identity linkage

Rows are keyed by `identity.value` (the browser's own P6 identity
concept — never a global or network identifier). The per-identity ring
and every reader surface (`Status`, `RecentEvents`, the dev page's ring
rows) filter to the requesting identity; the ledger exposes no
cross-identity join, no correlation key, and no per-user tracker. The
90-day rolling retention window is enforced locally at persist time
(`docs/state/attention-budget.md` §4 pattern; browser-side persistence
is P13's and inherits this law).

## No network path

`shield/core/**` performs no I/O beyond the injected bundle bytes and
the ledger append (plan law 5, egress-gated); the shield host is a stdio
JSON process — no socket, no uploader, no clock (every time value is a
caller-supplied integer). List FETCHING is the component-updater
channel's job (P10, `docs/release/PRIVACY.md`); the shield core only
consumes signed bundle bytes. Nothing in this phase uploads anything
anywhere.

## What the surfaces show

- The chip shows a COUNT of `kBlocked` rows for the current identity —
  the only passive security counter in the product
  (`docs/state/attention-budget.md` §Shield; enforced by
  `tools/attention_check.py`).
- `xr://shield` exists in dev builds only (real `--build-channel dev`
  startup gate) and renders exactly the state the caller rode in —
  including the enterprise force-disable reason VERBATIM, because a
  suppressed shield must never be silently suppressed (disclosure law,
  `xr-core/shield/host_protocol.md` §dev-only debug page).
- Panel and why-blocked affordances are P13's; this phase emits the
  codes they will read (`docs/shield/reason-codes.md`).
