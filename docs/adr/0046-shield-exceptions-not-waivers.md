# ADR-0046: Shield exception scopes do NOT reuse the §11.9 waivers semantics

- **Status:** PROPOSED (drafted by the P11 coding agent; ratification rides
  HG-26's queue — agents draft, humans decide, L24)
- **Date:** 2026-09-12
- **Deciders (humans):** Security lead + Design-systems lead (the waiver
  machinery is theirs; the exception surface is security-state)
- **Plan anchor:** P11 brief T4 — "Do not reuse the P8 §11.9 'waivers'
  semantics for shield exceptions; record the reason in an ADR"
- **Evidence:** `docs/state/research-log-P8.md` (the waiver rows:
  `waivers: [{token,pair,best,reason}]` in the TOKEN DATA — "auditable,
  never a comment"; light carries exactly 9 exact rows, security-critical
  hues only, "below body-text 4.5 nothing is waivable", dark/custom themes
  carry ZERO waivers), `docs/contracts/registry-post-freeze.md` (THEME
  rows: tokens_gen waiver/audit gates; "custom theme imports may NOT carry
  waivers"), `xr-core/shield/host_protocol.md` (the exception surface:
  scope grammar, refusal split, resolver coupling),
  `tools/exception_ledger_check.py` (the shield ledger + `--as-of`),
  `tools/tests/test_p11_exceptions.py` (19 negative fixtures)

## Context

P8 built a waiver mechanism for theme contrast: when a token pair cannot
meet its WCAG target, the exemption lives as a machine-readable row inside
the token data itself (`{token, pair, best, reason}`), gated by tokens_gen's
waiver/audit checks — exact-count (9 in light), floor-bounded (nothing
below body-text 4.5 is waivable), and forbidden entirely for dark/custom
themes. P11-T4 adds a superficially similar concept — user/product-granted
exceptions to a blocking default — and the brief explicitly forbids
reusing the waivers semantics for it. This ADR records why the two must
stay separate mechanisms.

## Decision

Shield exceptions get their OWN grammar, ledger, and gates; the word
"waiver" appears nowhere in the shield surface. The semantics differ on
every axis that matters:

1. **Data class.** A waiver is an audit exemption over STATIC,
   declarative design data (a contrast ratio that will never change at
   runtime). A shield exception is runtime AUTHORIZATION state — what the
   blocker is allowed to skip, for whom, until when. Folding runtime
   security state into design-audit vocabulary is a category error in
   both directions.
2. **Clock.** Waivers have no expiry at all (they live until a human
   edits the token data). Shield expiries are caller-supplied MONOTONIC
   integers swept deterministically (`exception-sweep {now_mono}`,
   boundary inclusive; the ledger checks rows with `--as-of`) — the
   determinism law forbids wall clocks, so even the §1.13-style ISO-date
   expiry is refused in the shield ledger (`not a monotonic integer`).
3. **Granularity and floors.** Waiver granularity is a token pair with a
   hard numeric floor (4.5). Scope granularity is multi-dimensional
   (identity/site/workspace/rule/list) with the resolver-coupling law
   (identity A never covers identity B) — and the shield's "floor" is a
   posture law, not a number: NOTHING can waive route-loss fail-closed.
   A shared mechanism would have to express both, weakening each.
4. **Grant direction.** Custom themes may NOT carry waivers (registry
   law — imports get zero trust). Shield exceptions are BY DESIGN
   user-grantable per site (`site-toggle` — the product's whole point).
   The trust directions are opposite; one permission model cannot serve
   both without becoming wrong for one of them.
5. **Enforcement point.** Waivers gate at tokens_gen (build-time audit
   over a checked-in palette). Exceptions gate at the host protocol
   (golden vectors + byte-parity corpus over two independent
   implementations) plus a disclosure ledger in `docs/limitations.md`
   (commit-time). A unified mechanism would couple a11y audit tooling to
   security state and security sweeps to theme data — every change to
   either side could silently alter the other's semantics, exactly the
   drift `registry-post-freeze.md` exists to prevent.

Concretely, T4 therefore ships: the T2 scope grammar unchanged (reason
REQUIRED on every scope), four host methods (`exception-add`,
`exception-remove`, `exception-sweep`, `site-toggle`) with the refusal
split (document parse errors `kMalformedInput` exit 1; conflicts with the
existing set `kRejected` exit 0), and a SECOND ledger section
(`## shield exception ledger rows` — scope/reason/monotonic expiry/owner,
zero rows valid, missing section a failure) owned by the same
`exception_ledger_check.py` that owns §1.13.

## Consequences

- `docs/limitations.md` carries two ledgers with different expiry
  vocabularies (ISO dates for §1.13 isolation cells — P9 legacy,
  untouched; monotonic integers for shield rows). The tool owns both and
  documents the split in its `--as-of` help.
- Any future surface that wants "waive a default" must pick a side
  explicitly: design-audit exemption (waiver rows) or runtime
  authorization (scope rows). This ADR is the citation for that choice.
- If ratification rejects this separation, the fallback is a unified
  exemption registry — which would require re-opening the frozen-ish
  tokens_gen waiver gates and the T2 scope grammar together (a
  cross-phase change this ADR exists to avoid).
