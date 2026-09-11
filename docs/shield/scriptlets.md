# XR Shield scriptlet & advanced-directive posture (P11-T3, ADR-0045)

**v1 executes NOTHING from a list.** The decision surface is
network-block only. This document is the threat analysis behind that
boundary, the refusal table that enforces it, and the list of what a
future capability would have to prove first (§arch 4 of the P11 brief;
the decision itself is recorded in ADR-0045).

## Why the boundary exists

* **Scriptlets are page-privileged JavaScript.** The plan's own words:
  "scriptlets run with page privileges". uBO's scriptlet surface has an
  XSS-shaped history — the phase brief calls it "the crux of the phase's
  biggest security risk". A list-compromise (T10's threat model: the
  list channel = remote behavior control) turns directly into script
  execution in every page that matches, if scriptlets run.
* **The pin does not give us a sandbox we have verified.** adblock-rust
  0.13.3's resource/scriptlet machinery exists, but what its ABPF
  sandbox actually forbids at the pin (page access? DOM APIs? `window`
  handles?) is research item R9b — UNVERIFIED until a live read at the
  pin lands with citations (T6). Shipping scriptlets before that read
  would be asserting safety from memory, which the brief forbids.
* **There is no renderer.** P11 lands before the renderer exists — there
  is literally no surface to inject into. Any "support" would be dead
  code that pretends to be a capability.
* **Refusal is the honest failure mode.** Every unsupported directive
  class becomes a TYPED refusal (`{directive, reason, count}` in the
  bundle's refusal table), surfaced later on `xr://shield` (T6) and as
  `kUnsupportedDirective` BlockEvents (T5) — never a silent ignore, so
  the cost of the boundary is always visible and countable.

## What is refused, and with which token

The compiler (`xr-lists/compile.py`) refuses at compile time; the shield
core's bundle grammar (`xr-core/shield/core/bundle.cc ParseFilter`)
refuses the same classes at load time — a compiled bundle the host
refuses is a compiler bug, and the round-trip's host cells cross-check
the two. Closed vocabulary (pinned by `tools/list_bundle_check.py`,
per-class vectors in `docs/contracts/vectors/xr-lists-compile-v1.json`):

| class | examples | refusal token |
|---|---|---|
| scriptlets | `#%#//scriptlet(…)`, `##+js(…)`, `#$#abort-on-…` | `unsupported-directive:scriptlet` |
| procedural/extended cosmetic | `#?#div:has(…)`, `#@?#…:matches-css(…)` | `unsupported-directive:procedural-cosmetic` |
| regex filters | `/re/` | `unsupported-directive:regex` |
| uBO preprocessor | `!#if env_chrome` | `unsupported-directive:preprocessor` |
| any other `$option` | `$important`, `$third-party`, `$csp`, `$replace`, `$popup`, type options | `unsupported-option:<name>` |
| allow+redirect conflict | `@@||x^$redirect=y` | `unsupported-option-combination:redirect-on-exception` |
| malformed option values | `$domain=`, `$redirect=`, bare `$` | `malformed-option:{domain,redirect,empty-name}` |
| bundle-grammar leaks | `#`/`@` in filters, interior pipes, empty filters | the matching `unsupported-directive:*` / `empty-filter` token |

`$important` deserves its own line: it exists to INVERT
allow-overrides-block, which is a load-bearing law of the v1 decision
order (`match.cc`). Accepting it would make the exception surface
non-total, so it is refused like every other unsupported option.

## What v1 DOES carry

* network rules in the literal/wildcard/anchor grammar (`||`, `|`, `*`,
  `^`) with structured `domains`/`exclude_domains`;
* `$redirect=<resource-name>` → `kind:redirect` with a resource NAME —
  the engine-supported resource-replace form. The name is data; what it
  resolves to is T8's resource work, and no executable bytes ever cross
  the FFI shim (`xr-core/shield/engine/` passes names, and the shim's
  cargo features exclude `css-validation`/`content-blocking`);
* simple cosmetic selectors as INERT data (`kind:cosmetic`) — carried so
  the bundle format does not lose upstream information, never matched by
  the v1 network engine, never injected anywhere.

## What a future scriptlet capability must prove first

1. R9b's cited read of the sandbox at the pin (what it forbids: page
   access, DOM APIs, `window` handles) — live citations, not memory;
2. 2–3 public CVE/advisory examples of scriptlet-class bypasses behind
   the refusal-list entries (the brief's evidence requirement);
3. a threat-model update treating the list channel as a code-execution
   channel (T10 currently models it as behavior control — scriptlets
   escalate that);
4. parity + fuzz coverage for the scriptlet path on BOTH bindings
   (T8's machinery, extended);
5. a human decision (ADR amendment, HG-gated) — not an agent call.
