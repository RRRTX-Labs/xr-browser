# ADR-0043: standard public algorithms live in-tree exactly once, in an S0-owned location — a second copy is a defect

- **Status:** PROPOSED (drafted by the P11 coding agent; ratification rides
  HG-26's contract queue — agents draft, humans decide, L24)
- **Date:** 2026-09-11
- **Deciders (humans):** Platform lead + Security lead (S0 dual review, L13)
- **Plan anchor:** Plan §14 DR-11 (no custom crypto), §7.2 (S0 ownership),
  P1-T7 (S0 paths: sandbox/Mojo/vault/crypto/network); P11 brief T0-b
- **Evidence:** xr-core `895ae6f` (the move), `tools/no_new_crypto_check.py`
  (+ `--self-test`), `common/tests/test_sha256_kat.cc` (10 vectors, compiled
  into all six suite lanes), `evidence/P11/logs/t0b-*.txt`

## Context

At P10 close, xr-core carried **five byte-identical copies** of an in-house
SHA-256 (`{policy,commands,settings,themes,update}/core/sha256.cc`, 97 lines
each, identical modulo the namespace word — diffed) and five of the strict
JSON model/parser (`json.cc`/`json_parse.cc`). The FIPS known-answer test
existed in exactly one place (`policy/tests/test_vectors.cc`, 3 vectors):
four copies of a security primitive were unpinned and nobody owned them.
P10's header was candid ("the same standard, public algorithm already
shipped in-tree … NOT an invented primitive") and the P10 brief said
"implement a hash ⇒ stop and report"; copying dodged the letter of that rule
and missed its point. P11 is precisely the phase that would add copies 6 and
7 (rule hashing, bundle digests, corpus fingerprints), so the question was
forced: where does a public algorithm live, and how many times?

## Decision

1. **Standard, public algorithms may be implemented in-tree — exactly once,
   in an S0-owned location.** That location is `xr-core/common/core/`
   (namespace `xr::common`): `sha256.{h,cc}` (FIPS 180-4, corruption
   DETECTION only) and `json.{h,cc}` + `json_parse.cc` (the strict canonical
   JSON model every core speaks). A second copy anywhere under
   `xr-core/*/core/` or `xr-core/shield/` is a **defect**, machine-refused by
   `tools/no_new_crypto_check.py` (single-copy multiplicity rule + constant/
   library/banned-symbol/PRNG/`std::hash`-disposition scan, planted-fixture
   self-test).
2. **This is NOT a relaxation of DR-11.** No new algorithm is added: the
   banned-symbol table refuses Sha1/Sha512/Sha3/Md5/Blake2/Blake3/Keccak/
   HMAC/PBKDF2/HKDF/scrypt/Argon2/Poly1305/ChaCha20/AES/Ed25519/X25519/RSA
   shapes outright; adding one is a stop-and-report (P11 failure
   condition 4), never an edit. Authenticity never rides a bare digest: it
   lives behind the injected `SignatureVerifier` (the boundary law is stated
   on `common/core/sha256.h` itself, where the next reader will see it).
3. **Consumption is by alias shim or direct include — never by copy.** Each
   core keeps a 3-symbol `<core>/core/sha256.h`/`json.h` shim
   (`using common::…` into the core's namespace): zero implementation, zero
   drift potential, every call site untouched. Behavior proof: update's
   golden vectors stayed 224 checks / 0 failures through the move; policy's
   suite lost exactly the 3 inline KAT checks that moved to the shared file.
4. **The KAT is one source, compiled into every consumer suite**
   (`common/tests/test_sha256_kat.cc`; 10 vectors incl. the padding/block
   boundaries, a 1 MiB stream and the 2^29-bit length-field case; published
   FIPS values plus committed goldens dual-computed with `hashlib` AND
   `sha256sum` before commit). Coverage cannot desynchronize because there
   is nothing to synchronize: the six lanes compile the same bytes.
5. **Layout choice (recorded per the P11 brief):** flat `common/core/`
   rather than `common/crypto_lite/` + `common/json/` subdirs, because
   `<name>/core` + `<name>/tests` is the shape the proof machinery already
   discovers (`ci_lane_discovery`, `mutation_test`, `mutation_freshness`,
   `core_hygiene_check`) — the shared primitives inherit the same lanes as
   every other core instead of sitting outside them. GN label:
   `//xr/common:common_core`.
6. **Trust classification (same commit, plan P1-T7 applied to code that
   already exists):** `docs/process/s0-paths.yaml` adds `/common/` (crypto
   is named S0 in plan §7.2), `/update/` (decides whether a downloaded
   binary is trusted — verifier/epoch/seen) and `/shield/` (P11's own
   network-path code, classified BEFORE it lands). **`/commands/` is judged
   S1, not S0**, with reasons: it is a UI-action dispatch surface whose
   availability predicates READ the P6 resolver's pinned snapshot (data in,
   verdict out — no second brain, no trust decision of its own); it holds no
   key material and no network authority; it is not in plan §7.2's S0 set
   (sandbox/Mojo/vault/crypto/network). `xr-core/OWNERS` + both CODEOWNERS
   are regenerated from that one YAML (`owners_sync.py --write`; never
   hand-edited).

## Consequences

* Moving bytes out of five `core/` dirs stales all five recorded mutation
  scores (the freshness gate's law: a score is a statement about specific
  bytes). Fresh FULL matrices for all cores incl. the new `common` core land
  with P11's evidence (`evidence/P11/logs/`), and `SUITE_MAPS` drops the
  moved TUs from the five maps and gains the `common` map.
* `mutation_test.py` copies `common/` into every target's tmp tree (all
  suite lanes compile the shared objects).
* Any future phase needing a digest/parse in a core includes the common
  header; the gate, not review discipline, keeps the count at one.
* `std::hash` survives in exactly one dispositioned place
  (`policy/core/cache.h` — LRU bucket keys, never integrity); every other
  use reddens until dispositioned in writing.
