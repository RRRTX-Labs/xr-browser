# Identity lifecycle (P14-T1)

Status: the state machine is pure core, fully tested
(`xr-core/identity/tests/test_identity.cc`, `test_hibernate.cc`); browser
runtime halves are NOT-RUN (methods at the bottom).

## States (frozen mojom v1)

`kActive` / `kHibernated` / `kDestroyed` — the transitions
Activate/Hibernate/Destroy/PromoteToFortressProfile carry the frozen
spellings on the wire (byte-parity with the fake, corpus-locked).

## Destroy = purge AND verify (the §1.4 law)

A destroy that leaves bytes is a SECURITY FAILURE, not a leak:

1. the purge drops the identity's own surface, prefs namespace, and record;
2. the store is then WALKED — the purge's return code is never trusted.
   Out-of-place bytes (the temp files / crash dumps / shader caches a real
   purge forgets) are modeled by the store's residual ledger;
3. any residual ⇒ `kInternal`, exit 1, the error names the bytes. The
   negative is replayable: `identity_host plant-residual … ` then
   `destroy` (also `test_identity.cc` §4b and the pytest scenario case).

In-memory (disposable) identities carry no durable session data and cannot
be promoted to Fortress (promoting would persist the volatile — refused
with the reason).

## Concurrency cap + hibernation

Plan §1.4: SOFT cap of 5 concurrent active identities (configurable);
excess identities hibernate. The scheduler
(`xr-core/identity/core/hibernate.{h,cc}`):

* evicts the least-recently-ACTIVATED identity when the cap is hit, and
  RECORDS the eviction (`reason: "cap"`); explicit hibernation records
  `reason: "user"` — never silent;
* hibernation discards the volatile surface (cache) and PRESERVES the
  partition state (cookies/prefs/storage — what wake needs);
* wake obeys the same cap (an eviction may fire — recorded);
* **wake never resurrects**: a purged/destroyed identity is
  `kUnknownIdentity`, not a silent re-mint (the disposable law; the
  resurrection negative is `test_hibernate.cc` §4);
* ordering uses the caller's monotonic tick — there is no clock in the
  core.

## NOT-RUN (methods, not surrogates)

* `switch ≤ 200 ms`, `wake ≤ 200 ms to first paint` — rig budgets:
  `docs/qa/browser-harness.md`; the perf-budget rows are generator-owned
  (`rig_class: trend`), never MET in this sandbox.
* Lifecycle chaos (`kill -9` each process type with identities live):
  P9-T11's drill is the method (`docs/qa/browser-harness.md`).
