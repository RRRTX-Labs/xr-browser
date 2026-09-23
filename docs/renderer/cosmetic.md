# Cosmetic exception interplay (P12-T5)

Cosmetic and network consult the **same** P11 exception object. This file is
the written record of that decision and its three-way proof; the machine half
lives in `tools/cosmetic_scope_single_check.py`,
`tools/exception_ledger_check.py`, the golden vectors
(`docs/contracts/vectors/cosmetic-v1.json`) and
`tools/negatives/p12_t5.sh`.

## 1. The rule: one scope object, atomic

`xr-core/shield/core/scope.h` `ExceptionScope` is the single authorization
record both layers read. When a user sets "shields down" for a site, the bit
they flip (`xr-core/shield/host_protocol.md` `site-toggle`) is the same bit the
cosmetic producer and consumer consult:

- **network** (`shield/core/match.cc` `Covers`): a blocking hit matched by an
  exception scope is not blocked;
- **cosmetic** (`renderer/cosmetic`): a rule set is dropped for a scope whose
  site/identity the frame's own scope does not match (`core/blob.cc`
  `BlobError::kScopeMismatch`), and "shields down" maps to the degrade table's
  `kShieldsDown` row (`core/degrade.cc`: apply the always-on generic set only,
  render the page).

Both consult the SAME `scopes` object, not two copies. The split-brain
negative is `tools/negatives/p12_t5.sh` `cosmetic_split_brain_private_store`:
plant a private exception store in the cosmetic surface and
`cosmetic_scope_single_check.py` reddens. "Atomic" is not a claim here — it is
the grep-proved property that the cosmetic surface carries none of the shield
exception-store grammar (`exception-add`, `exception-remove`,
`exception-sweep`, `site-toggle`, `scope_id`, `expiry_mono`,
`user-site-toggle`, `workspace`, `list_id`).

## 2. The identity/OOPIF matrix (≥40 cases, pinned as vectors)

The four laws the P12 brief hardened are asserted over the committed vectors,
never prose:

1. **Embedder-shields-down must not extend to a cross-site frame.** The scope
   key is derived from the FRAME's registrable domain, never the embedder's
   (`core/scope_key.cc` `DeriveScopeKey` — a non-empty `embedder_site` is
   REFUSED with `embedder-refused`, so "key on the top-level site" is
   structurally impossible). Pinned by `matrix-scope-key-embedder-*` and the
   git-blame-visible refusal in `scope_key.cc` lines ~44-48.
2. **A frame's exception must not reach the embedder.** Two frames with the
   same identity but different `frame_site` derive different keys
   (`matrix-scope-key-site-*`: distinct hexes), while the partition stays
   constant (identity+trust only), so a frame's exception can never key
   another frame's rule set.
3. **Same site, different identity ⇒ different key-set.** `matrix-scope-key-identity-*`:
   distinct hex AND distinct partition per identity. Cross-identity leakage
   would be a distinct-key violation the byte-parity checker cannot miss.
4. **Eviction for one identity never serves another.** `IdentityPartition()`
   hashes `(trust, identity)` only; identity A's partition can never be
   reached from identity B's key. The site matrix (law 2) proves the site
   never enters the partition, and the identity matrix (law 3) proves the
   partition is identity-exclusive.

The blob-check half (`matrix-blob-*`) pins the consumer side: a blob for one
site or identity class is refused `scope-mismatch` in another, and a
`frame_scope` that smuggles an extra key (e.g. `embedder_site`) is compared on
exactly `site` + `identity_class` — the C++ host and the Python fake were made
byte-identical here by T5 (the fake had been comparing the whole frame dict and
was corrected; the host's "embedder is not an input to this comparison" law
wins).

## 3. The three-way proof and its limits

The degrade-safety property is asserted three independent ways, never merged
(see `docs/renderer/degrade-safety.md` for the full statement and the two
planted-capability negatives):

1. the static `blink_guard_lint` over the document-start seam patch;
2. the core-level "no blob / no rules ⇒ zero emitted bytes + bounded cost"
   law (`core/degrade.cc` `ShouldInstallObserver`, `core/keyset.cc` byte
   budget);
3. the named farm runbook in `docs/qa/browser-harness.md`.

What this sandbox established is the host/core/fake contract, not a rendered
result. The page-level blank-page property is `NOT-RUN (method:
docs/qa/browser-harness.md#…)` — no Blink build, `gn`/`ninja` are absent, and
no claim in this file is a browser measurement.

## 4. The ledger

`docs/limitations.md` now carries a `## cosmetic exception ledger rows` table
(empty at ship: the v1 surface consumes the shared P11 scopes object, so a
cosmetic-private exception is refused, not disclosed).
`tools/exception_ledger_check.py` checks its scope grammar, reason, monotonic
expiry against `--as-of` (never `date.today()`), and the one-object law: a
cosmetic row must have a matching shield row.
