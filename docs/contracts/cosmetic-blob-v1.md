# Contract: Cosmetic blob v1 (P12) — LIVING, not frozen

- **Schema:** `cosmetic-blob-v1.schema.json`. **Version:** 1.
- **Status:** `LIVING`. Deliberately absent from `FROZEN.yaml`: its consumers
  (the cosmetic host, the ABPF validator, the scriptlet registry) are being
  built in this same phase, and freezing a shape before its consumers exist is
  how a contract ends up frozen around a mistake. Stamping it is a post-P12 act
  and is recorded as such in `evidence/P12/human-gates.md` (HG-26).
- **Producer:** list compilation (the `xr-lists` side). **Consumer:**
  `xr-core/renderer/cosmetic/{host,abpf}`.
- **Fake:** `fakes/cosmetic.py` (xr-browser). **Vectors:**
  `docs/contracts/vectors/cosmetic-blob-v1.json`.

## Why this contract exists

A cosmetic rule set is DATA that a renderer will act on at document-start. The
blob is the boundary at which that data stops being "text somebody wrote in a
filter list" and becomes "instructions this browser will follow", so its shape
is a security contract and not a serialization detail.

Two properties are load-bearing and are asserted by the validator, not by prose:

1. **Nothing executable crosses it.** Selectors and property maps only — no
   code, no callbacks, no `javascript:` URLs, no `expression(...)`. The parser
   in `xr-core/renderer/cosmetic/core/selector.cc` refuses those shapes with a
   typed reason; the blob validator refuses a blob that carries them.
2. **A refusal is never a partial accept.** A blob containing one bad rule is
   rejected as a whole, with the offending rule identified. Dropping the bad
   rule and applying the rest would let a list author learn which of their
   payloads survived, which is a probing channel.

## Envelope

| field | type | meaning |
|---|---|---|
| `schema` | const `"xr-cosmetic-blob-v1"` | the schema id; a mismatch is refused, not migrated |
| `schema_version` | int `1` | bumped only with an amendment RFC |
| `blob_id` | string | opaque producer id, echoed in events for traceability |
| `generated_epoch` | int | unix seconds; DATA, never read as "now" |
| `scope` | object | `{site, identity_class}` — the partition this blob applies to. It MUST match the frame's own scope key (`renderer/cosmetic/core/scope_key.h`); a blob for one site is refused in another |
| `rules[]` | array | see below |
| `refusals[]` | array | `{rule_index, reason}` — what the producer already knew it could not express. Present so a consumer can report an honest coverage number instead of silently applying fewer rules |
| `sha256` | string | over the canonical (sorted-key, `separators=(",",":")`, `ensure_ascii`) bytes of everything except this field |

Canonicalization is the same function `fakes/_base.py` and
`tools/shield_vectors_check.py` already use, so a blob hashes identically in
C++ and Python. That is what makes the ≥150 golden vectors a byte-parity test
rather than a semantic one.

## `rules[]`

| field | type | meaning |
|---|---|---|
| `id` | string | stable per-rule id; appears in every event that rule produces |
| `selector` | string | the raw selector TEXT. Validated by parsing, never by regex |
| `action` | enum | `hide` \| `remove` \| `style`. `remove` is page-modifying and is labelled as such in events — an injected/removed element is not a blocked request |
| `style` | object | present iff `action == "style"`: a map of CSS property to value. `!important` is refused; it cannot appear in a selector either |
| `enabled` | bool | default true. A disabled rule is carried, not dropped, so a user's exception list is auditable |
| `exception_sites[]` | array | sites where this rule does NOT apply. Cross-checked against the blob's `scope` |

No field carries a scriptlet name. Scriptlets are a separate contract
(`scriptlet-registry-v1`) with execution OFF by default
(`xr_shield_scriptlets = false`), so a cosmetic blob cannot reach scriptlet
execution even if a list author tries to name one.

## Refusal vocabulary

The refusal `reason` strings are the closed vocabulary in
`renderer/cosmetic/core/selector.h` (`SelectorErrorName`) plus the blob-level
reasons `schema-mismatch`, `scope-mismatch`, `sha256-mismatch`,
`rule-too-large`, `too-many-rules`, `duplicate-rule-id`. A reason outside that
set is itself a refusal: an unknown reason means the producer and consumer
disagree about the contract, and guessing is how a validator becomes
permissive.

## Security

- **Threat:** cosmetic filtering runs at document-start on arbitrary sites. A
  rule that can match the whole document (`*:has(...)`) is a page-wide mutation
  channel, so `kUniversalWithPseudo` is a hard refusal in the parser.
- **Threat:** a blob scoped to site A applied in site B would leak one
  identity's rule set into another frame. `scope` is compared against the
  frame's derived scope key, and the embedder site is not an input to that key
  (`scope_key.h`) — passing one is refused rather than corrected.
- **Fail-open on cosmetic only:** a blob that fails validation is not applied,
  and the page renders unstyled but intact. This is the one place in the phase
  where fail-OPEN is correct: refusing to hide an ad must never refuse to render
  a page. It is the opposite of the network layer's fail-CLOSED rule, and the
  difference is deliberate and recorded here so a future reader does not
  "fix" it.

## Non-goals

- Not a delta format. A blob is whole; there is no patch application, so there
  is no partial-application state to reason about.
- Not signed. Signing is the list-bundle manifest's job
  (`list-bundle-manifest-v1`); this blob is the compiled output inside an
  already-verified bundle. Adding a second signature scheme here would be a
  second crypto path, which the phase's hard stops forbid.
