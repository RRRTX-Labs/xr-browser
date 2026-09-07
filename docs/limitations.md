# Published limitations (verbatim, Plan §1.13)

**Source:** copied verbatim from
`XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` §1.13 "Published limitations (a
shipped surface, not a footnote — Isolation Card + `xr://help`)", plan copy
pinned by SHA-256 in `master-plan.sha256`. This file is the seed copy for
the in-product Isolation Card and `xr://help` (P4/P13/P35 feed it with
*measured* rows — the Isolation Card is data-driven from the isolation
matrix, not prose).

---

Shared across identities (until Fortress promotion): GPU process & OS graphics state; OS DNS cache and hostname resolution side channels; OS clipboard; downloads directory; extension *background contexts* (a broadly-permitted extension is visible across identities by design — Guard narrows this); upstream History DB contents (identity-filtered UI, export tags); CRL-set/CT state. Fingerprinting is **reduced, partitioned, never resisted** — XR's own configurability enlarges the space; that is why we say so. Disposable = browser-side forgetting, not forensic erasure, not network anonymity. Tor mode = Tor *networking*, not Tor Browser; anonymity-critical users are directed to Tor Browser/Tails in-product. Download protection = verification + reputation, not AV. XR Vault = zero-knowledge *by construction*; we cannot help you if you lose the master password — printed, on first unlock.

---

**Maintenance rule:** any new documented exception (isolation matrix, leak
suite) requires a row added here in the same commit (Plan §9.1 / §11.4).
This page is a *shipped surface*, not a footnote — its copy is legal-
reviewed and its drift from measured suites is a release blocker (L5,
§17 "Documentation" row: "threat model = shipped reality, bot-checked").

---

## Measured cross-profile-shared disclosure (P4, static evidence only)

Added by P4, from `docs/spike-identity/measured-shared-state.md`. Only rows
with static `file:line@pin` evidence appear here; every row is
machine-re-audited (`./scripts/build spike citation-audit`) and **runtime
confirmation is PENDING-FARM (HG-21)**. This block is data-driven from the
isolation matrix, not prose — it is the seed for the Isolation Card.

With identity implemented as a per-tab `StoragePartitionConfig` domain
(ADR-0042, PROPOSED), **partitioned** by identity:

* cookies, LocalStorage, IndexedDB, CacheStorage and ServiceWorker state
  (`services/network/public/mojom/network_context.mojom:282`);
* the HTTP cache, including its directory
  (`…network_context.mojom:242`);
* HSTS / transport-security state (`…network_context.mojom:307`);
* HTTP/QUIC server-property hints (`…network_context.mojom:302`);
* proxy configuration, bound per NetworkContext at creation
  (`…network_context.mojom:443`;
  `content/browser/storage_partition_impl.cc:3506`);
* renderer processes — reuse requires the same StoragePartition
  (`content/browser/renderer_host/render_process_host_impl.cc:4952`).

**Still shared across identities** (the honest part of the card):

* site permissions (`HostContentSettingsMap`), History, Bookmarks, the
  password/autofill store, the extension registry and the Downloads DB —
  all Profile-level;
* the favicon cache — a shared cache hit discloses whether another identity
  has visited a site;
* **DNS**: the per-context host cache is partition-local, but the
  `HostResolverManager` is one per NetworkService
  (`services/network/network_service.cc:492`) and the OS resolver cache is
  outside the browser entirely;
* the GPU process and the OS clipboard.

Identity partitions are a **storage and process** boundary, not a full-profile
boundary. Nothing about them is airtight, and the product must not imply
otherwise.

## Policy resolver (P5 contract)

* **The policy resolver is total: unknown input ⇒ deny.** Any unknown
  identity, unknown origin, unknown request class, or malformed input resolves
  to the fully-denying `EffectivePolicy` — never a permissive default and never
  a guess (DR-07 / L3). Schema of record:
  `docs/contracts/effective-policy-v1.schema.json`; the deny rows are pinned in
  `docs/contracts/vectors/policy-resolver-v1.json` and the purity/determinism
  of the function is a contract test (`docs/contracts/tests/test_policy_determinism.py`).

## Policy resolver (P6 implementation)

* **The C++ JSON layer is strict-int, not arbitrary-precision.** Out-of-int64
  integers degrade to doubles, and doubles are formatted by `std::to_chars`
  rather than Python's float repr — both diverge from the Python fake on
  round-trips of arbitrary JSON. This is deny-safe (every strict validator in
  the policy path rejects doubles where integers are expected) and no frozen
  contract carries floats; pinned in `xr-core/policy/tests/test_json.cc`.
* **The cache invalidation is generational, not evented.** Watch is
  poll-mode (`snapshot seq` + `generation` counters over the stdio protocol);
  no push channel exists yet (nothing upstream subscribes in P6 — P21 wires
  Guard dispatch).
* **The enterprise managed source requires the `minisign` binary.** Absent
  tool ⇒ managed policy is IGNORED (visible SKIP, ledger row) — never
  partially enforced. Tests exercise the signed path only where minisign is
  installed; CI installs it pinned (HG-7 pattern).
* **Bench budgets are two-core sandbox numbers.** p99 ≤5µs warm / ≤200µs
  cold / ≤2ms snapshot-apply were measured on the 2-core dev sandbox;
  reference-hardware re-measurement is HG-28. Verdicts are emitted by the
  bench binary itself (`MET`/`DEVIATION`), not post-hoc eyeballing.
* **The 24h fuzz campaign and full-matrix mutation run are farm-gated**
  (HG-28); the repo lane runs a 10-minute fuzz timebox and a deterministic
  90-mutant sample with the same gates (score ≥90%, deny-guard 100%).

