# Review packet: Cosmetic blob v1 (P12)

- **Contract id:** cosmetic-blob  **Version:** 1  **Freeze status:** LIVING (pre-stamp)
- **Ratification:** NOT-ELIGIBLE until post-P12 (see the note below)

## Why this one is LIVING and not REVIEW-COMPLETE

The other 15 packets are stamped REVIEW-COMPLETE with ratification PENDING
because their consumers already exist and only human sign-off is missing. This
one is different in kind: its consumers (the cosmetic host, the ABPF validator,
the scriptlet registry) are being built in the same phase that introduces the
shape. Stamping it now would freeze a contract whose consumers have not yet
discovered what they need, and `contract-amendment-rfc.md` exists precisely
because that is expensive to undo. The amendment path is available, but the
cheaper and more honest state is LIVING with an explicit stamping condition:

> Stamp `cosmetic-blob-v1` in `FROZEN.yaml` only after the host and the ABPF
> validator both consume it and the ≥150 golden vectors pass byte-parity
> against both backends. Until then, changes to the shape are ordinary commits,
> not amendments.

## Interface inventory

One object, eight required fields, `additionalProperties: false` at every
level. No field carries executable content: `selector` is text validated by
parsing, `style` is a property→value string map, and there is no scriptlet-name
field at all — scriptlets are a separate contract with execution OFF by
default, so a cosmetic blob cannot reach scriptlet execution by naming one.

compromise => a rule set that mutates pages at document-start; mitigations are
the scope match against the frame's derived scope key, the closed refusal
vocabulary, and the no-executable-content law.

## Files shipped

- `docs/contracts/cosmetic-blob-v1.md` — the contract, including the
  fail-OPEN-on-cosmetic rule and why it is the deliberate opposite of the
  network layer's fail-CLOSED rule.
- `docs/contracts/cosmetic-blob-v1.schema.json`
- `docs/contracts/vectors/cosmetic-blob-v1.json` — golden vectors (T2)
- `core:fakes/cosmetic.py` — the Python reference consumer (T3)
- `core:renderer/cosmetic/core/selector.{h,cc}` — the parser whose refusal
  vocabulary the contract's `reason` strings mirror (shipped, T1)
- `core:renderer/cosmetic/core/pseudo.{h,cc}` — the pseudo-class allowlist
  (shipped, T1)

## §7.2 import-law compatibility check

- Fake imports: stdlib + `_base` only. No cross-boundary imports, no
  reflection, no temporary direct includes.
- The C++ core is std-only and takes sha256 from the single shared copy in
  `common/core` (ADR-0043). There is no second hash and no second hex encoder;
  `tools/no_new_crypto_check.py` enforces that.
- No mojom surface in this contract: the blob is data consumed inside the
  renderer, not an IPC boundary. If a mojom surface is added later it gets its
  own packet and its own row here.

## Threat-model invariants linked

- Cosmetic rules run at document-start on arbitrary sites, so a rule that can
  match the whole document is a page-wide mutation channel:
  `kUniversalWithPseudo` is a hard refusal in the parser.
- A blob scoped to site A must not apply in site B. `scope` is compared against
  the frame's derived scope key, and the embedder site is not an input to that
  key — passing one is refused rather than silently corrected
  (`renderer/cosmetic/core/scope_key.h`).
- Fail-OPEN on cosmetic only: an invalid blob is not applied and the page
  renders unstyled but intact. Refusing to hide an ad must never refuse to
  render a page.

## Checklist (structure enforced by freeze_check.py; sign-off = human)

- [ ] narrow surface — sign-off: __NOT-ELIGIBLE (pre-stamp; see above)__
- [ ] typed errors — sign-off: __NOT-ELIGIBLE (pre-stamp)__
- [ ] no generic exec — sign-off: __NOT-ELIGIBLE (pre-stamp)__
- [ ] fuzz target required before integration — target:
      `fuzz_cosmetic_blob` (P12-T6; declaration only, ≥600 s campaign) —
      sign-off: __NOT-ELIGIBLE (pre-stamp)__

## Open questions for the S0 humans

- Confirm the stamping condition above is the right gate, rather than stamping
  now and amending later.
- Confirm the fail-OPEN choice for cosmetic is acceptable as a deliberate
  divergence from the network layer's fail-CLOSED rule. It is recorded in the
  contract so a future reader does not "fix" it.
- Confirm that refusing the whole blob on one bad rule (rather than dropping the
  bad rule) is the intended behaviour. It costs coverage; it closes a probing
  channel where a list author could learn which payloads survived.
