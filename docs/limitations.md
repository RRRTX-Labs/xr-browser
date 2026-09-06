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
