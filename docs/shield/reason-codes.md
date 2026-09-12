# Shield reason codes — "why was this blocked?"

P11-T5. The closed verdict vocabulary of `xr-core/shield/host_protocol.md`
(§Decision vocabularies, `verdict.why_code`) is the contract; this table
maps every code to a stable text key that P13's Activity Ledger and the
one-click "why was this blocked?" affordance render localized copy from.
Machine-readable twin: `reason-codes.json` (same data — the sync tests
read the JSON; this file is the human table). The row that CARRIES a code
is the living `block-event-v1` ledger row (`docs/contracts/block-event-v1.md`).

| why_code | text_key | Emitted when | Typical row action |
|---|---|---|---|
| `rule-blocked` | `shield.why.ruleBlocked` | a list or custom rule blocked the request | `kBlocked` |
| `rule-allowed` | `shield.why.ruleAllowed` | an allow-rule matched; the request proceeded | `kAllowed` |
| `rule-redirected` | `shield.why.ruleRedirected` | a redirect-rule rewrote the request | `kRedirected` |
| `rule-replaced` | `shield.why.ruleReplaced` | a replace-rule intercepted the request before it reached the network | `kBlocked` |
| `no-match` | `shield.why.noMatch` | no rule matched; the request proceeded | `kAllowed` |
| `no-bundle` | `shield.why.noBundle` | no list bundle is bound yet; the request proceeded (data absence fails open) | `kAllowed` |
| `exception-scope` | `shield.why.exceptionScope` | a user exception scope covered the hit; the request proceeded | `kAllowed` |
| `engine-dead-fail-open` | `shield.why.engineDeadFailOpen` | the blocking engine died; browsing continues fail-open with an amber chip | `kAllowed` |
| `engine-poisoned-fail-open` | `shield.why.enginePoisonedFailOpen` | the engine reported poison; browsing continues fail-open with an amber chip | `kAllowed` |
| `kill-switch` | `shield.why.killSwitch` | the kill switch is on; blocking is suspended with an amber chip | `kAllowed` |
| `route-loss-fail-closed` | `shield.why.routeLossFailClosed` | the egress route was lost; the request is held fail-closed (red chip) | `kBlocked` |

## Stability laws

- The codes are the closed vocabulary of `host_protocol.md` — adding or
  renaming a code is a contract change with a review packet, not a table
  edit. The `block-event-v1` schema enum, the emitter's accepted set in
  BOTH backends, this table, and the vectors' usage must agree at every
  commit (`docs/contracts/tests/test_block_event.py` asserts the
  five-way sync; drift reddens).
- `text_key` values are stable identifiers: never renamed, never reused.
  The copy behind a key is localizable and may change; the key may not.
- Every code has exactly one row; every row's `default_action` matches
  the reason-code table in `reason-codes.json` byte-for-byte in content
  (the JSON is the machine source; this table mirrors it).
- Voice law: this table and the copy rendered from it state mechanics,
  not promises — no announcement voice (claims_lint-gated; the
  §10 vocabulary law applies to the rendered strings too).

## Attention posture (brief §architecture invariant 7)

Reason codes feed the ledger, the dev page, and the one-click "why" —
plus the passive chip COUNT. No toast, badge, or modal is ever produced
from a block event; the chip counter is the only passive surface the
emitter may drive.

## P13 dependency (documented, not implemented here)

P13 renders `text_key` copy in the Activity Ledger and the one-click
affordance, and enforces retention at persist time: 90-day rolling
default, user-configurable, per-identity local storage only, exportable
by user action, never uploaded (plan §data). Until P13 lands, the
`why_code` itself is the fallback display string, and v1 pins the row
shape, the redaction, and this mapping.
