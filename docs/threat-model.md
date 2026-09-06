# XR Browser — Threat model v0

- **Version:** v0 (Phase P1, 2026-09-07)
- **Bound to:** `XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md`
  (SHA-256 `02743146146fa139cd53b15216aaa26b79f9d9307998b1814019d27406265a7b`,
  pinned in `master-plan.sha256`)
- **Status of the protections described:** **v0 is pre-implementation.**
  Every protection stated below is the *target posture* from the Plan
  (§9/§11), not shipped functionality — P1 ships governance only. Rows are
  the stable adversary classes that §2 S0/S1 feature rows must cite
  (Plan §9.1: "Every S0/S1 feature row in §2 cites its model entry").

**Update rule (machine-checked by `tools/check_threat_model.py`):** this
model must be updated whenever any §2 S0 row changes. **Shipping a feature
that changes the model without updating the model is a blocked merge**
(Plan §9.1). A new documented exception (isolation matrix, leak suite)
requires a `docs/limitations.md` row in the same commit.

## How to read this document

- **Adversaries T1–T11** are the threat classes, in the Plan's order
  (§9.1). Each row states what the product *will* do about that adversary
  (target posture, with the phase that ships it) and — equally important —
  what it **does NOT protect against**. The honesty column is product law
  (DR-09, DR-18, L5): if a cell is missing or softened, the merge is
  blocked.
- **Assets** is what we are protecting.
- **Invariants** are the standing guarantees the whole design must hold
  (Plan §1.12), linked per item.
- **Out of scope** is stated, not footnoted: two adversary classes are
  explicitly *not* defended, and the product says so in-product.

## Assets

| # | Asset | Why it matters |
|---|---|---|
| A1 | The user's logins and credentials (per-identity) | The vault/credential surface is the existential component (Plan §9.4) |
| A2 | Separation of the user's personas (identity isolation) | The product's core promise: identities know about each other and can show the receipt |
| A3 | User data: notes, history, downloads, vault files | Local-first (L15); never leaves the device without documented, consented exception |
| A4 | Egress route integrity per identity | The network moat: no traffic leaves an identity's configured route (invariant 5) |
| A5 | XR's own update/list channels | A compromised channel is remote behavior control (T10) |
| A6 | The user's device | No exfiltration, bounded logs, no telemetry by default (L16) |

## Adversaries

| ID | Adversary class | XR posture (target, with shipping phase) | Does NOT protect against |
|---|---|---|---|
| T1 | Commercial trackers | Native network-level blocking (`adblock-rust` in the network service, P11) with signed list bundles (EasyList, EasyPrivacy, uAssets, Peter Lowe, AdGuard — data, not code); per-site exceptions with expiry scopes (P13); Tracker Observatory + "why was this blocked?" (P13) | Sites where the user turned Shields down; trackers not present in the list sets; first-party (same-origin) tracking that lists do not cover; content the user explicitly loads. Until P11 ships: nothing (this is v0) |
| T2 | Cross-identity linkage of the user's own personas | Identity = dedicated StoragePartition (P14) with overlay stores (permission defaults, history namespace, vault scope, extension availability); cross-identity process non-sharing asserted adversarially, not assumed (isolation matrix §11.4, P9/P14) | Shared-profile state listed in `docs/limitations.md` (GPU process, OS DNS cache, OS clipboard, downloads directory, extension background contexts, upstream History DB, CRL-set/CT state) until Fortress promotion (P35); any linkage vector the isolation matrix has not yet exercised. This is the core threat: it is *asserted by tests per build*, never promised |
| T3 | Malicious sites | Inherited Chromium posture only — renderer sandbox + Site Isolation; XR must not weaken it (L2) and does not claim to strengthen it; XR patches that touch isolation are dual-reviewed and covered by the upstream-assumptions suite (P3/P9, §12.4) | Zero-days in V8/Blink and sandbox escapes — that is Chromium's threat surface, consumed via the security fast-lane (72 h critical / 14 d high, §12.4), not XR's defense. XR adds no novel protection against malicious pages beyond Chromium's own |
| T4 | Phishing / downloads | Safe Browsing v5 Local-List + OHTTP relay (P16; terms gated by LG-2 — see `docs/legal/LG-2-safe-browsing-terms.md`); download security pipeline: local verdicts via `xr-inspect`, quarantine-until-acknowledged, signature *display* (P26) | SB results are bounded by Google's list quality and the terms' 30-minute freshness window; download protection is verification + reputation, **not AV** (Plan §1.13); brand-new phishing URLs not yet on any list; malicious archives that defeat local heuristics (fuzzed, P9 — "fuzzed" is a posture, not a guarantee) |
| T5 | Malicious / over-privileged extensions | Extension Guard (P21): static manifest grading A–D (permissions-as-outcomes), per-identity availability enforced at the single dispatch chokepoint, `nativeMessaging`/`debugger` deny-by-default, egress observation (endpoints observed, logged, optionally suspended per policy) | **Intent is never claimed** — Guard emits observations only (invariant 11); a broadly-permitted extension's background context is visible across identities by design (Plan §1.13) until Fortress; extensions behaving strictly within declared permissions; the CWS install channel itself (fragility for forks — DR-13 fallback kept warm) |
| T6 | Passive network observers | Per-identity DoH/DoT presets + custom templates (P17); route binding per NetworkContext (P18); Tor identity with in-tunnel DNS, WebRTC off, `.onion` confinement (P31); leak suite gates every route class (P19, published results) | On direct (non-Tor) routes, the path operator still sees your traffic; **Tor mode = Tor networking, not Tor Browser** (DR-09, non-dismissible disclosure in-product); OS DNS resolver cache side channels are shared (`docs/limitations.md`); observers who control the exit endpoint the user configured |
| T7 | Fingerprinters | Fingerprint **reduction** (P20): per-eTLD+1-per-session farbling (canvas/WebGL/AudioContext), clamps, normalization; partitioning by identity | **Resistance is not claimed** — fingerprinting is "reduced, partitioned, never resisted" (Plan §1.13); XR's own configurability *enlarges* the fingerprint space, and the product says so; a determined operator can still build a partial profile; letterboxing is Fortress opt-in only (P35), default off |
| T8 | Local malware / compromised OS | **Out of scope — stated** (Plan §9.1 T8). The product says so in help. | Everything on a compromised host: a local adversary with OS-level access can read local state, hook the process, or steal keystrokes. XR makes no defense claim here and no claim should ever be read from this document to the contrary |
| T9 | State-level deanonymization | **Out of scope — stated** (Plan §9.1 T9). The product directs users needing that grade of protection to Tor Browser/Tails in-product (Plan §1.13) | State-level correlation, corroboration, and infrastructure-level observation. An XR Tor identity is explicitly **not** a substitute for Tor Browser; the first-run disclosure is non-dismissible (P31-T8) |
| T10 | XR's own update/list channels (compromise = remote behavior control) | In scope by design: signed update manifests with pinned keys, staged rollout, epoch revocation, transparency log (P10); signed list bundles with pinned content hashes, last-known-good fail-closed, continuous parser fuzzing (P11/P9); endpoint audit per release (the contacted-host set must equal the documented set exactly, §11.8) | A compromise of the signing key hierarchy itself — mitigated by offline root/HSM, rotation drills, and the out-of-band runbook (§9.10), which is an *operational* mitigation, not a property of the channel; a list channel compromise is contained by rule-grammar sandboxing + provenance + published diffs, but a validly-signed malicious list is by definition within the trust the user granted to the channel |
| T11 | Dependency supply chain | L9 evaluation pack before any dependency lands (this repo, `docs/dependencies/`); vendored + pinned + vetted (no "latest"); SBOM per release (P10); advisory SLA: critical triage ≤ 72 h (P9+); max-2-promotion vendor-adapt rule (§12.3) | A malicious upstream release that passes vetting — mitigated by pinning exact revisions and reviewed vendor diffs, not by any scanner; note the honest scope of P1 tooling: `tools/license_audit.py` is **header/inventory-level** — full dependency-graph license/advisory resolution lands in P9-T9 (no overclaiming, L5) |

## Invariants

Standing guarantees from Plan §1.12 ("Major invariants, CI-enforced or
release-blocking"). The threat model and the isolation/leak suites must
agree with these; a change to any invariant is an ADR + register event
(ADR-0002). Each entry links the plan copy in this repo.

1. **Storage:** no identity's web storage reachable from another identity via any browser-mediated path — asserted by the isolation matrix (§11.4). [Plan §1.12-1](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
2. **Processes:** renderers of different identities never share a process — inherited from partition-suitability, asserted adversarially under load, not assumed. [Plan §1.12-2](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
3. **Vault:** no vault plaintext or key material in the browser process, logs, crash dumps, or renderer memory — verified by memory-inspection test. [Plan §1.12-3](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
4. **License:** no GPL/AGPL code linked into any shipped binary — CI dep-graph scan; lists/feeds are data; GPL tools are separate processes or absent. [Plan §1.12-4](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
5. **Route integrity:** no traffic leaves an identity's configured egress route — `xr-leaktest`, every build, every route class, results published. [Plan §1.12-5](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
6. **Ephemeral integrity:** zero bytes of ephemeral-identity data on disk (FS-diff assertion, incl. crash). [Plan §1.12-6](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
7. **Accountability:** every block/deny/grant/expiry decision has an Activity Ledger row with reason code + the rule/permission that caused it. [Plan §1.12-7](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
8. **Upstream security posture:** no XR patch weakens Site Isolation, the sandbox, Mojo validation, or CORB/ORB; no release ships with a known-unpatched upstream critical CVE. [Plan §1.12-8](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
9. **Honesty:** no user-facing claim exceeds the published limitations (`docs/limitations.md`); banned vocabulary is release-blocking copy-check. [Plan §1.12-9](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
10. **Consent:** nothing leaves the device without a documented exception (update channel, list fetches, SB OHTTP, user search) or explicit opt-in; telemetry default-off with byte-accurate local viewer. [Plan §1.12-10](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
11. **No intent claims:** Guard and Observatory emit observations only; copy review enforces ("XR can see where an extension connects, not what it intends."). [Plan §1.12-11](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
12. **AI boundary:** no assistant/copilot/chat surface anywhere in chrome, panels, omnibox, context menus, or extension APIs (DR-12). [Plan §1.12-12](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
13. **Identity dignity:** identity is visible on 100% of tabs in 100% of layouts; no silent identity switch. [Plan §1.12-13](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)
14. **Fail-safe:** death of Shield engine, vault process, tord, or wgd degrades security posture *visibly* — never silently, never by bricking browsing. [Plan §1.12-14](XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md)

## Out of scope

Stated per Plan §9.1, restated here so a reader of *this* document never
has to infer it:

- **T8 — local malware / compromised OS:** out of scope, stated. A
  compromised OS can read everything local; no browser can defend that
  case, and the product says so (help page, P37).
- **T9 — state-level deanonymization:** out of scope, stated. Users who
  need that grade of protection are directed to Tor Browser/Tails
  in-product (Plan §1.13); an XR Tor identity is Tor *networking* (DR-09).

These two rows are load-bearing honesty (DR-09, DR-18): removing or
softening them requires an ADR + register event, and the copy gate treats
their absence as a release blocker.

## Change history

| Version | Date | Change |
|---|---|---|
| v0 | 2026-09-07 | Initial transcription of Plan §9.1 adversary classes T1–T11 + §1.13 limitations + §1.12 invariants (Phase P1, XR-P1-T4). Pre-implementation posture; every protection statement is target, not shipped. |
