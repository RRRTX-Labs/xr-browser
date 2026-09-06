# XR BROWSER — MASTER IMPLEMENTATION & EXECUTION PLAN

**Product:** XR Browser by RRRTX Labs
**Status:** **CANONICAL — single operational source of truth** for engineering, security, QA, UX, release, contributors, and coding agents
**Version:** 1.0 · Ratified 2026-09-07
**Supersedes (demoted to evidence, not authority):**
- **Spec-A** — `XR-BROWSER-MASTER-SPECIFICATION (1).md` (v1.0 reconciliation spec)
- **Spec-B** — `XR_BROWSER_MASTER_PRODUCT_ENGINEERING_SPECIFICATION.md` (RRRTX Labs engineering spec)
- **Spec-C** — `XR-Browser-Master-Specification.md` (Office of the Chief Architect spec)

**How to use this document.** Section 2 is the feature registry: no feature exists outside it. Section 4 is the phase system: no work is scheduled outside a phase. Section 14 is the law: no exception is legitimate without a recorded Decision Register entry. Section 17 defines "done": nothing else does. Changes to any §18 Decision Register (DR-xx) entry require new external evidence and a recorded reversal — not preference. Every claim marked **[VERIFIED]** was re-checked against primary sources on 2026-09-07 (Appendix A). Claims marked **[ASSUMPTION]** carry a named verification task in Phase 1–2.

---

# 0. FINAL RECONCILIATION SUMMARY

## 0.1 The three supplied specifications, judged

All three specs converged, correctly, on the essentials: Chromium base with a Brave-style overlay repo and a hard ≤150 upstream-file patch budget; native filtering via `adblock-rust` with filter lists as signed runtime data; Identity as the core primitive with storage, permissions, extensions, credentials and egress scoped to it; a three-position Adaptive Trust dial (Standard/Shield/Fortress) driving exactly one policy resolver, with Tor and Disposable as *identities*, not dial positions; a sandboxed KDBX-4 vault with zero custom crypto behind an external audit gate; no XR-operated VPN/sync/store/AV/threat-intel; no security scores; no intent verdicts on extensions; direct-media download only, never DRM circumvention; opt-in telemetry only; MPL-2.0 for `//xr` with GPL never linked; AI-free core. Those decisions are inherited by this plan and are not re-litigated below.

Where they disagreed, each disagreement was researched against primary sources this week. The rulings:

| # | Question | Spec-A | Spec-B | Spec-C | **RULING (this plan)** | Decisive evidence |
|---|---|---|---|---|---|---|
| R1 | **Engine base** (Firefox ESR vs Chromium) | Chromium | Chromium | Chromium (all three already rule out Spec-PDF's Firefox) | **Chromium, confirmed.** The "containers need profile surgery on Chromium" objection is dead: Brave shipped containers on Chromium 1.92 (July 2026) **[VERIFIED]**, and upstream's own process-model doc states documents in different **StoragePartitions** — "which may differ between tabs" — can never share a renderer process **[VERIFIED]**. The seam exists, is supported, and is what Brave used. | Chromium `docs/process_model_and_site_isolation.md` (Process Reuse → Suitability); Brave 1.92 announcements |
| R2 | **Identity implementation seam** — the single most consequential engineering choice | Identity = BrowserContext; in-window mixing = "60% of the cost," Phase 3 | BrowserContext inside Profile | Identity **== Profile**; in-window mixing deferred to P4 as "per-WebContents surgery" | **None of the three is right.** Canonical model (§1.4): **Identity = a named, XR-owned object backed by a dedicated `StoragePartitionConfig` (custom partition domain) inside its owning Profile, resolved per-SiteInstance via `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance`.** This is the Chrome-Apps/IWA isolation mechanism — an *upstream-supported* seam, not a fork-patch. Consequences: (a) per-tab mixed identities in one window is native Chromium shape, not a Phase-3 heroics project; (b) cross-identity process isolation is *inherited from Site Isolation for free* (partition ≠ shareable); (c) per-identity `NetworkContext` (proxy/DNS) follows the partition — the network half of the moat becomes binding, not surgery; (d) the genuinely shared upstream state (HostContentSettingsMap, history, extension registry, password store) is handled by XR-owned identity-keyed overlay stores the product needs anyway (identity-tagged history, per-identity permission defaults, Guard availability). Fortress-grade users can **promote an identity to a dedicated off-the-record Profile** for maximal isolation. A Phase-0 **identity-seam spike (P4)** must empirically prove papercut classes (downloads, print, DevTools attach, omnibox, drag-across-identity) with a documented fallback: *identity-per-window via BrowserContext* — shipping the moat minus in-window mixing. | Upstream docs **[VERIFIED]**; Brave's own architecture description ("containers sit inside one profile … partitioning site-specific state between containers," extensions/autofill/passwords/history explicitly shared) **[VERIFIED]** |
| R3 | **Tor engine** | Arti, defer to Phase 4 | little-t-tor child; "track Arti" | little-t-tor first; Arti = P4 alternative | **Build Tor (Spec-A right against Spec-PDF's DROP). Ship an engine-swap design: `xr-tord` helper daemon with a frozen local IPC (SOCKS5 + control socket); default engine Arti 2.6.0, fallback upstream C tor selectable in settings.** Arti is now genuinely "a full-featured Tor client … can connect to and run onion services … suitable for general client usage" (official README, Aug 2026) **[VERIFIED]**, is memory-safe, is designed for embedding, and its RPC/bootstrap APIs eliminate the control-port parser we would otherwise have to build and fuzz (Spec-C's C-tor-only position preserves that liability). C-tor remains selectable because anti-censorship completeness (Snowflake, exotic transports) is currently stronger there; the leak-suite tests the daemon boundary, so engine swaps don't re-open the leak surface. | torproject Arti README + Arti 2.6.0 release notes (2026-09-01) **[VERIFIED]** |
| R4 | **WireGuard userspace** | boringtun (BSD-3) primary; wireguard-go fallback | — | **wireguard-go primary; "boringtun carries restructuring warning"** | **Spec-C is right; Spec-A's preference is rejected.** boringtun's upstream repo still warns "currently undergoing a restructuring… not rely on master" **[VERIFIED]** and its FreeBSD port was marked IGNORE/DEPRECATED after "the first and only available release was deleted from upstream" **[VERIFIED]**. Canonical: `xr-wgd` = **wireguard-go (MIT)** user-space tunnel exposing **local SOCKS5 only** (wireproxy pattern). No TUN, no root, no system routing table, no macOS NetworkExtension entitlement — that constraint is permanent (DR-20 inherited from Spec-A: the local-SOCKS design deliberately sidesteps per-platform tunnel pain; "do not let anyone improve it into a system tunnel"). | cloudflare/boringtun README; FreshPorts history **[VERIFIED]** |
| R5 | **MV2 compatibility layer** | DROP (Chrome 151 deleted the machinery) | DROP | **RESTORE as opt-in P2** ("genuine power-user differentiator") | **Spec-A right; Spec-C rejected on verified fact.** Timeline confirmed: MV2 stopped running on Chrome 138 (2025-07-24); Chrome 150 deleted the first dev flag (2026-06-30); **Chrome 151 (2026-07-28) deleted the last dev flag and *all MV2 machinery* from source; CWS purged every MV2 listing 2026-08-31** **[VERIFIED]**. Reviving MV2 means carrying a *deleted* subsystem — a permanent, unbounded patch-budget line inside the extension platform (S0-class code) — whose only real customer (uBO-class blocking) XR already serves natively with strictly more power. DROP, with a per-train re-check task; the honest in-product answer to "I want uBO MV2" is: native Shield already covers uBO syntax incl. scriptlets; users may sideload uBO Lite (MV3). | superchargebrowser/duskbyte timeline reconstruction vs Google deprecation notes **[VERIFIED]** |
| R6 | **Safe Browsing transport** | Keep; local-list mode; no proxy | "privacy-preserving where licensed" | Keep v4 **plus an XR-operated anonymizing proxy** (Brave pattern) — which contradicts its own "no operated services" rule | **Superseded by upstream progress: adopt the current Safe Browsing v5 architecture's Local-List mode + Google's OHTTP (Oblivious HTTP) relay — no XR-operated proxy needed.** v5 offers explicitly documented modes (Real-Time / **Local List** / No-Storage) and a "Safe Browsing Oblivious HTTP Gateway" so the list vendor "only has access to the IP address… via a non-colluding third party" **[VERIFIED]**. Default: Local List + OHTTP; opt-in Real-Time; **Enhanced never shipped**. The API is free **for non-commercial use** (commercial → Web Risk) → legal gate LG-2, and the license posture drives the enterprise-edition plan, same as Widevine. | developers.google.com/safe-browsing (v5 overview) **[VERIFIED]** |
| R7 | **Translation stack** | Chromium Translator API + user endpoints | **Bergamot** integration | Chrome on-device (Gemini Nano); "Bergamot sunset" | **Spec-B's Bergamot-as-integration target is dead** (Mozilla sunset the add-on in favor of built-in FF118+ **[VERIFIED]**). Spec-C's "inherit Chrome's Google-model" conflicts with XR's de-Google posture and creates a Google infrastructure dependency. Canonical: a **Translation Provider framework** — (1) user-configurable endpoints (self-hosted LibreTranslate/Bergamot-server, DeepL with user key), provider **named inline at point of use**; (2) optional fully-offline model component *only if* independently inspectable and Google-infra-free (re-check each phase); (3) default OFF, per-origin memory. It is a *translation tool*, never an assistant — AI policy §0.4 unchanged. | Mozilla support pages **[VERIFIED]** |
| R8 | **Tracker categorization source** | list provenance metadata | "Disconnect-like lists" | Disconnect excluded: **CC BY-NC-SA 4.0** | **Spec-C's correction is right** — Disconnect's tracker lists moved to CC BY-NC-SA 4.0 in June 2020; commercial use requires a paid license **[VERIFIED]**. Canonical: categorize by **list provenance** (EasyPrivacy/uAssets/Peter Lowe metadata + an XR-maintained small entity map, CC0). Optional paid Disconnect license is a P39 business decision, not an engineering dependency. | disconnectme GitHub LICENSE + blog **[VERIFIED]** |
| R9 | **Chromium release-cadence assumption** | "4-week train; track canary weekly" | cites "4-week milestones" | "follow stable train" | **All three are obsolete as of this week.** Google announced (2026-03-03) that **Stable/Beta move to a two-week milestone cadence starting Chrome 153 (2026-09-08 — tomorrow)**, Extended Stable stays 8-week with security backports, and weekly (piloting twice-weekly) security patches continue **[VERIFIED]**. CEF's public response — tracking even milestones only — is the template. Canonical strategy (§12): `main` rebase-tracks **canary daily**; *shippable* branches align to the **8-week Extended-Stable-equivalent series**, security hotfixes cherry-pick from Chromium security tags **without milestone promotion**; never user-visible-track the 2-week train. Patch budget, rebase staffing, and QA matrices in all three specs were sized for a 13-milestone year; the plan re-sizes them for the real pace. | ghacks/9to5Google/CEF#4114 **[VERIFIED]** |
| R10 | **KDBX implementation risk** | "keepass-rs (MIT)… validate write correctness" | keepass-rs as "reference engine" | KDBX 4.1-compatible | Both understate it. `keepass` crate 0.13.6 (MIT, active, co-owned by a KeePassXC maintainer) **still labels KDBX4.1 writing experimental**, and the fork lineage warns writes are **lossy for unparsed fields** **[VERIFIED]** — credential databases cannot tolerate lossy writes. Canonical: keepass-rs as **read/reference**; XR owns the writer; a **golden-corpus round-trip matrix** (files generated by KeePass 2.x, KeePassXC, strongbox variants × every field type, custom fields, attachments, history) is a hard gate inside P28 before real credentials are allowed; `kdbx-rs` (GPL-3) remains banned. | crates.io/docs.rs/GitHub **[VERIFIED]** |
| R11 | **Update stack** | "build update system" | "Omaha-compatible or Sparkle-class per OS" | "signed auto-updater" | **Build far less than any spec planned.** Upstream ships an open-source cross-platform updater client in-tree at `//chrome/updater` ("Chromium Updater"), explicitly recommended by its maintainer for forks, protocol 3.1 JSON; only the *server* must be written **[VERIFIED from maintainer threads]**. Canonical (§8): in-tree `//chrome/updater` client + a small, audited, stateless XR update server (signed manifests, pinned keys, staged rollout metadata) + the existing component updater for filter lists/CRL sets/models/tor engines. Linux additionally ships native repos; Flatpak documented as a degraded channel (§13). |
| R12 | **Vault/credential phasing & "full product" pressure** | Vault P3, audit-gated; cards P5 evidence-gated | Vault P2 after GA credentials | Hardened upstream creds P1; Vault P2 engineering, GA P3 | **Synthesized, audit gate unchanged:** P27 ships *hardened upstream* credential manager day one (users are never credential-less); P28–P30 build `xr-vaultd` with the **external audit as the release gate for storing real credentials**; browser-resident passkeys only hardware-bound (P33); cards last (P39), interface reserved at P5. All three agree on the substance; phase numbering unified here. | — |
| R13 | **Widevine/DRM** | "component updater; no MLA needed for a *client*; legal confirm" | "decide contractually; never block launch" | "negotiate from P0; if unavailable say so" | **Spec-A's factual claim checks out** — the in-tree mechanism downloads Google's CDM via the component updater; an MLA is for *issuing* licenses; distribution terms still differ per platform (Linux CDM cannot be repackaged freely — the FreeBSD ports split is the cautionary tale; community helpers like `silvervine` show the user-initiated-install pattern is live in 2026) **[VERIFIED]**. Canonical: **user-initiated, explicitly consented CDM download using the in-tree Widevine bundle-manager path (the Brave model), never pre-bundled**; legal gate LG-3 must clear platform terms before P10 exit; fallback = honest download-page disclosure. Never silently proxy, never fake. | brave-core wiki; chromium-dev thread; silvervine **[VERIFIED]** |
| R14 | **Tor `.onion` and leak posture** | leak suite gates Tor; `.onion` confined to Tor identity | same | "Brave's 2026 `.onion` leak is a test case" | All agree; **upgraded to law**: the leak suite (xr-leaktest) is a CI artifact with **published per-release results**, and the Tor engine/identity ships only green. `.onion` confinement, DNS-through-tunnel-only, WebRTC-off, extension-traffic capture, update-check routing, captive-portal and prefetch probes are named test cases from P5 fixture definitions, run against every route config. | — |
| R15 | **"Pins" / Notes / Highlights / Reader / Research Mode / Region routing / media** | — | — | — | **Unanimous across all three; inherited verbatim:** Pins → **Highlights** on `#:~:text=` with honest degradation; Notes = local per-identity Markdown store; Research "mode" → Research identity template + curated bang engines (arXiv, Semantic Scholar, PubMed, GitHub, manpages); region routing = exit-label dropdown on user proxies; media = direct/unprotected `<video/audio>` + plain HLS-as-file only, DRM extraction categorically out, permanent (DR-16). | — |

## 0.2 Things all three got wrong, omitted, or left open — now decided

1. **The cadence fact (R9).** Rebase economics nearly double. This plan moves *user-facing* milestone promotions to an 8-week Extended-Stable-equivalent rhythm with 72h out-of-band security capability, and makes "milestone promotion" a *policy output*, not an obligation. (§12)
2. **Nobody froze the per-identity `NetworkContext` contract precisely enough** (R2). Per-identity DNS/proxy is *the moat*; it now has a named interface (`xr.mojom.RouteManager` bound at partition creation) and a named leak test per route class from P5 onward.
3. **Nobody priced the shared-state disclosure correctly.** Brave's own containers explicitly share extensions, autofill, passwords, permissions, history **[VERIFIED]**. XR's differentiator is precisely the *overlay stores* that close those gaps — so the Activity Ledger, permission overlay, Guard availability, and identity-scoped vault are the product, and the Isolation Card must list *residual* shared state (GPU process, OS clipboard, downloads dir, OS-level state) — never claim more (§9.11).
4. **No spec defined the extension-availability enforcement point.** Guard's "Banking runs zero extensions" needs a browser-side chokepoint: `ExtensionFunction::Dispatch` consults the policy resolver (§1.8, patch ≤2 files) plus content-script injection filtering. This is now a contract, not a hope.
5. **No spec addressed Flatpak/sandbox interaction, nor Linux keystore fragmentation, as first-class release engineering.** §13.4: deb/rpm/AppImage are tier-1; Flatpak is tier-2 with documented capability loss; Linux keystore degrades to password-only mode honestly (Spec-A's note, elevated to a gate).
6. **No spec planned for the two-week Beta churn against site-compat:** the compat corpus bot (P9) tracks Chrome *Beta* continuously, not just stable — cheap insurance now that Betas land every two weeks.
7. **Funding discipline.** Spec-A's DR-01 funding gate (10–14 engineers or do not fork) is inherited **verbatim as the Stage-0 exit condition** — this plan assumes the funded-team premise (the brief says build the full product), and §15 records the fallback posture (hardened-Chromium distribution + companion processes) that activates the moment the gate regresses.
8. **AI policy** is inherited at maximum strictness: **no assistant/copilot/agent/chat/LLM surface, ever** (DR-12). The *only* tolerated adjacent capability is a pure translation/reading utility under §0.1-R7 — no text input box, no chat surface, off by default, offline-capable option. Chrome's Gemini-Nano surfaces are **stripped** at build time (they ride Google infra and are conversational-adjacent); stripping is a P6 task, listed, not implied.

## 0.3 Rhetoric rules carried forward (all three agree; binding)

XR never says "anonymous," never says "unbreakable," never ships a "protection score," never claims insight into extension *intent*, never promises bit-identical reproducible builds with a date. Every shipped protection states, in-product, what it does **not** do. These are not marketing opinions; they are release-blocking copy gates (§11.6, §17).

## 0.4 Final product verdict (carried from the reconciliation, restated once)

Build the **full** XR Browser. The moat is *identity-scoped everything* — storage, permissions, extension availability, credential scope, DNS/egress route, process affinity — composed by one policy resolver, on the only engine with full web compatibility, proven by radical transparency. Blocking alone is table stakes (Brave/Mozilla/Waterfox all ship `adblock-rust` now **[VERIFIED]**); Tor networking alone is Brave's; a vault alone is Bitwarden's. XR is the browser where those things **know about each other and about which identity you are being right now** — and can show you the receipt.

---
# 1. FINAL ARCHITECTURAL BASELINE

This is the agreed architecture after reconciling Specs A/B/C and independent research. It is binding: subsystem work that contradicts §1 is out of contract.

## 1.1 System context

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ XR UX LAYER                                                                     │
│  C++ Views: window chrome · tab strip (Top/Vertical/Rail/Compact) · toolbar ·  │
│             Identity pill · Trust dial · Split/Focus/Compact layouts            │
│  WebUI (TypeScript + Lit): Command Palette · XR Panel (5 tabs) · Settings ·    │
│             Vault UI · Onboarding · Themes · Help/Threat-model browser          │
│  THE COMMAND REGISTRY is the spine: every surface is a view over one table.    │
└──────────────────────────────────────────┬───────────────────────────────────────┘
                                           │ Mojo (//xr/mojom — versioned, reviewed)
┌──────────────────────────────────────────▼───────────────────────────────────────┐
│ XR POLICY RESOLVER   //xr/policy   (C++, pure, cacheable)         ◀── ONE RESOLVER │
│  f(IdentityId, TrustContext, Origin/Site, ExtensionId?, RequestClass)              │
│    → EffectivePolicy { blocking, cosmetic, permissions, egress/dns, extensions,   │
│                        storage-class, vault-scope, fingerprint, process-isolation } │
│  No feature may hold private mode logic. Trust dial, Fortress, Tor, Disposable,    │
│  Guard, Shield, Network, Vault scoping are ALL inputs/outputs of this function.    │
└───────┬───────────────┬────────────────┬────────────────┬─────────────────┬────────┘
        │               │                │                │                 │
┌───────▼──────┐ ┌──────▼───────┐ ┌──────▼────────┐ ┌─────▼─────────┐ ┌────▼──────────┐
│ XR IDENTITY  │ │ XR SHIELD    │ │ XR NETWORK    │ │ XR VAULT      │ │ XR GUARD      │
│ //xr/identity│ │ //xr/shield  │ │ //xr/net      │ │ //xr/vault    │ │ //xr/extensions│
│              │ │              │ │               │ │               │ │               │
│ Identity =   │ │ adblock-rust │ │ per-identity  │ │ CLIENT in     │ │ static        │
│ XR object    │ │ (MPL-2.0) in │ │ NetworkContext│ │ browser proc; │ │ manifest      │
│ bound to     │ │ network      │ │ DoH presets · │ │ crypto in     │ │ review A–D ·  │
│ dedicated    │ │ service      │ │ SOCKS/HTTPS   │ │ SANDBOXED     │ │ per-identity  │
│ Storage-     │ │ + signed     │ │ proxy ·       │ │ UTILITY       │ │ availability  │
│ Partition-   │ │ list bundles │ │ WG/Tor routes │ │ PROCESS       │ │ via resolver ·│
│ Config inside│ │ cosmetic +   │ │ route binding │ │ (xr-vaultd):  │ │ nativeMsg/    │
│ the owning   │ │ scriptlets   │ │ at partition  │ │ KDBX-4 ·      │ │ debugger deny ·│
│ Profile;     │ │ via Blink    │ │ creation ·    │ │ Argon2id ·    │ │ egress        │
│ overlay      │ │ document-    │ │ leak policy   │ │ OS-keystore   │ │ observation   │
│ stores for   │ │ start hook · │ │ per trust     │ │ wrap ·        │ │ (endpoints,   │
│ perms/       │ │ why-blocked  │ │ context;      │ │ zero custom   │ │ never intent) │
│ history/     │ │ events →     │ │ fail-closed   │ │ crypto        │ │ update diffs  │
│ vault-scope  │ │ Activity Log │ │ on route loss │ │               │ │               │
└───────┬──────┘ └──────────────┘ └──────┬────────┘ └───────────────┘ └───────────────┘
        │                                │
┌───────▼──────────────────────────────────▼─────────────────────────────────────────┐
│ CHROMIUM (as close to upstream as possible; overlay-repo model)                     │
│ Blink · V8 · Site Isolation/Fission · renderer+network sandboxes · NetworkService · │
│ StoragePartition machinery · Extensions MV3 · WebAuthn · Autofill · Downloads ·     │
│ Safe Browsing v5 (Local List + OHTTP) · Reading Mode · Task Manager · Settings      │
│ machinery · //chrome/updater (client reused) · DevTools (UNPATCHED)                 │
└───────┬─────────────────────────────────────────────────────────────────────────────┘
        │ separate, unprivileged helper processes — NEVER linked into the browser binary
┌───────▼─────────────────────────────────────────────────────────────────────────────┐
│ xr-vaultd  (Rust)  KDBX I/O + crypto, sealed by policy                                                    │
│ xr-tord    (Rust)  Tor daemon front-end: Arti 2.6 default, C-tor selectable; SOCKS5+ctl │
│ xr-wgd     (Go)    wireguard-go tunnel → local SOCKS5; no TUN, no root                                    │
│ xr-inspect (Rust)  untrusted archive/binary sniffing for download security                                 │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Reading the diagram.** Three rules make the whole design checkable: (1) the only vertical authority is the **policy resolver** — every subsystem asks it and nothing else decides; (2) the only horizontal authority is **Chromium's own isolation machinery** — XR configures Site Isolation and StoragePartition, never replaces them; (3) anything that parses hostile input (vault files, archives, Tor handshakes, filter-list bytes) is either memory-safe Rust/Go in its own sandboxed process, or an upstream component we track, and never a new attack surface in the browser process.

## 1.2 Chromium strategy (what we fork, what we wrap, what we never touch)

**Fork model: overlay repo, not patch-queue.** `xr-core` is an independent repository (MPL-2.0) checked out into `src/xr` inside a pinned Chromium checkout, exactly the Brave pattern (Brave is live evidence the model survives years of trains; Thorium is live evidence the *alternative* — a hobby patch-queue — stalls: abandoned through 2025, revived onto LTS milestones by a single collaborator **[VERIFIED]**). Upstream modifications are a *budgeted, CI-counted* resource:

| Patch class | Budget | Rules |
|---|---|---|
| Branding/defaults (GRD, strings, about pages) | unlimited-ish (cheap) | trivial rebase; CI-confirmed |
| Hook points (new extension points called from upstream) | ~45 files | each hook has an owner + a `patchinfo` file |
| Blink seams (cosmetic injection at document-start; fingerprint surfaces) | ~25 files | security-reviewed; degrade-safe (page must render if hook dies) |
| content/ seam uses (storage-partition resolution, process policy, network-context binding) | ~30 files | **read-only hooks via `ContentBrowserClient` overrides live in `//xr` — target is ≤5 files in `content/` proper** |
| NetworkService seam (Shield URLLoaderFactory interception) | ~20 files | fail-open on engine death (never brick browsing), fail-closed on *route* loss |
| UI (`chrome/browser/ui`) | ~35 files | views-layer additions; never rewrite layout classes in place |
| Extension function chokepoint (`ExtensionFunction::Dispatch` guard consult) | ≤2 files | S0 review, dual sign-off |
| **Total upstream-touched files** | **≤150, enforced by CI, count published per release** | exceeding budget = architecture review, never silent scope |

**Never patched:** V8 internals, sandbox internals (policy *tightening* only, in `//xr`), Mojo core, DevTools internals (XR ships an internal **DevTools extension panel** instead — all three specs concur), certificate verifier, origin-bound crypto.

**Feature intake order (binding):** WebUI page → internal component under `//xr` → *Rust helper process* → Blink/content hook (budgeted) → upstream patch (rarest). "Components before patches."

**De-Googling posture:** take ungoogled-chromium's *inventory* as a checklist (RLZ, UMA, GAIA, GCM, field trials, domain relabeling) but **not** its build model (domain-substitution patching is built for purity, not product cadence). XR's approach: strip/neutralize Google services plumbing at build via GN args + `//xr` overrides, keep *component updater machinery* pointed at XR servers, keep Safe Browsing *protocol* (R6 ruling), keep Widevine download path (R13), keep Google-dependent *features* switchable-off with UI explaining what was removed (honest de-Googling, not silent breakage). Gemini-Nano/assistant surfaces: stripped (DR-12).

**Cadence (R9 ruling, §12 has the machinery):**
- `xr-core@main` rebases onto Chromium **canary daily** (bot; conflicts auto-file to the owning team) — keeps debt flat, surfaces seam loss early.
- **Shipping branches follow the 8-week Extended-Stable-equivalent milestone series** (even milestones, matching CEF's public adaptation to the new two-week train **[VERIFIED]**), so user-visible churn ≈ 6–7 promotions/year, not 26.
- **Security releases are decoupled:** Chromium security tags → cherry-pick → 72h SLA for critical/in-the-wild, 14d high, *without* milestone promotion (patch-version bumps). Measured and published per release.

## 1.3 Process architecture

| Process | Contents | Trust level | Notes |
|---|---|---|---|
| **browser** | UX, policy resolver (authoritative), identity manager, extension system, prefs | privileged | no vault plaintext, no untrusted archive parsing, ever |
| **renderers** | Blink+V8; cosmetic filter module; fingerprint shim | untrusted | sandbox policies inherited; **partition ≠ sharing ⇒ cross-identity process isolation is upstream's own rule** |
| **network service** | NetworkContexts (≥1 per identity partition), Shield engine (Rust FFI), SB v5 local-list client | brokered | route binding frozen at context creation |
| **GPU, storage, audio…** | inherited | as upstream | disclosed as shared state (§1.9) |
| **xr-vaultd** | KDBX parse/crypto/TOTP | **semi-trusted island** — the strictest boundary in the product | seccomp/seatbelt: filesystem access limited to vault dir + keystore IPC; **no network capability until P30 sync, then only to user-configured endpoint**; no `--type=utility` network |
| **xr-tord** | SOCKS5 + control pipe, engine = Arti (default) / C-tor (fallback) | untrusted-by-consequence (it sees cleartext pre-encryption? no — it owns the crypto) | zero inbound reachability beyond localhost socket; killed & re-seeded on demand |
| **xr-wgd** | wireguard-go handshake + local SOCKS5 | same posture as tord | config = secret; process memory never swapped? best-effort mlock, documented |
| **xr-inspect** | archive/binary sniffing for downloads | **untrusted** (parses hostile files) | output = verdict struct only |

**Mojo rules.** All cross-boundary XR APIs live in `//xr/mojom` — versioned, reviewed, frozen at P5 before feature work. Interfaces are narrow: request/response with typed errors, no generic "run" endpoints, no byte-slots. Fuzz targets are required *with* each interface (P9 harness). Renderer never receives vault material; WebUI receives redacted summaries.

**Memory reality (inherited from Spec-A, quantified):** each *active* identity adds real RAM (context, caches, service workers). Policy: soft cap of 5 concurrent active identities (configurable); excess identities hibernate (discard all renderers, keep partition state); budget per §11.7 (`≤40MB` idle-identity overhead target, verified in P14).

## 1.4 Identity, containers, disposables — canonical model

**Definitions (vocabulary is law; §10 maps it to UI):**

| Concept | Definition | Lifetime | Boundary enforced |
|---|---|---|---|
| **Profile** | OS-login-level persona = Chromium `Profile` (own user-data dir) | permanent, rare | everything incl. update channel, OS keystore namespace |
| **Identity** | XR's core primitive: named security context inside a Profile; **backed by a dedicated `StoragePartitionConfig` (`partition_domain = "xr:<identity-uuid>"`)** resolved per-SiteInstance | permanent; 2–6 typical | cookies, storage, cache, service workers, quota, `NetworkContext` (DNS/proxy/egress), **plus XR overlay stores**: permission defaults, history namespace, vault scope, extension availability; process isolation **by Site Isolation's own suitability rule** |
| **Ephemeral identity** (Disposable, Tor) | Identity whose partition is `in_memory = true` | destroyed at last-window close | same, then zero bytes on disk (asserted by FS-diff test) |
| **Fortress-promoted identity** (optional) | Identity may be *promoted* to a dedicated off-the-record `Profile` for maximal separation of shared-Profile state | permanent binding per identity | adds per-profile HCMS/password store; one-window-per-profile UI tradeoff |
| **Workspace** | named set of tabs + window layout + optional default identity | user-managed | **nothing** — organizational only |
| **Tab group** | native groups | session/saved | nothing; **cannot span identities** (enforced in P22) |
| **Trust context** | Standard/Shield/Fortress — resolver input | per-site (⌥ = per-identity) | blocking/permissions/fingerprint/isolation strictness |

**Why the partition seam (R2 ruling), stated precisely for implementers:**
1. Upstream: `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance()` lets the embedder map a SiteInstance → custom partition. Chrome Apps, WebUI, and IWAs isolate this way; it is a supported public override point, not a hack. XR's implementation: identity is `WebContentsUserData`; every SiteInstance created for that WebContents (or inherited by same-document/new-tab relations) resolves to that identity's partition config; navigation into a *different* identity is a tab move (destructive, confirmed, reloads in target identity).
2. Upstream: "two documents from different … StoragePartitions can never share the same renderer process" — cross-identity process separation is therefore *inherited* under full Site Isolation and *asserted* by XR's isolation matrix (adversarial process-inspection test, §11.4), not promised.
3. Upstream: StoragePartition owns its cookie jar, local storage, caches, service workers, quota — the whole web-storage surface.
4. NetworkContext is per StoragePartition ⇒ per-identity proxy/DNS/route binds once at context creation (`xr.mojom.RouteManager.BindIdentity(id, NetworkContextParams)`); Tor/proxy state attaches to the same object. Route loss ⇒ **fail closed**: pending + future requests error; recovery is user-acknowledged (§8.3, leak-tested).
5. Shared within a Profile (upstream reality; Brave's container design note confirms it): `HostContentSettingsMap`, History DB, Bookmarks, password store, extension registry, Downloads DB, DNS cache (context-local but OS resolver cache shared), GPU process, OS clipboard. XR closes the *product-relevant* ones with overlay stores (permission defaults keyed by identity inside the resolver; history/bookmarks rows carry `identity_id`; password/vault items carry scope; Guard gates extension functions by identity); the rest are **disclosed on the Isolation Card** and, for Fortress-promoted identities, upgraded to Profile separation.

**Identity lifecycle contract (frozen at P5):** Create(name, color, glyph, trust default, template?) → provision partition + overlay rows; Activate(window/tab binding); Hibernate(discard renderers, keep state); PromoteToFortressProfile (explicit, destructive re-provision with copy); Destroy(scope, purge: partition, overlay rows, queued telemetry, *and verify zero residual FS*); MoveTab(dst, confirm, reload). No silent auto-switch — ever (resolver may *suggest* a site→identity rule; applying is user-gated).

## 1.5 Filtering architecture (XR Shield)

- `adblock-rust` (MPL-2.0, `third_party/rust/adblock` vendored + pin policy) embedded in the **network service** at the `URLLoaderFactory` layer — before dispatch, below the extension API tier (so MV3 DNR caps are irrelevant: XR *is* the browser). Decision path: policy resolver inputs (identity, trust, site exception state) + compiled rule sets per identity.
- **Lists are data, not code:** EasyList, EasyPrivacy, uAssets (filters + privacy), Peter Lowe, AdGuard Base (license-permitted set; EasyList's dual GPLv3/CC-BY-SA applies as *data* consumption). Fetched as **signed bundles from XR's own update channel** (upstream integrity attested by pinned content hashes in the bundle manifest), delta-capable, **fail closed to last-known-good**; a compromise of the list channel is threat-modeled as remote *behavior* control (T10) — list grammar parsing is fuzzed continuously (P9 harness; adblock-rust parser targets from P11 first commit).
- **Cosmetic filtering + scriptlets + resource replacements** run renderer-side at document-start via one Blink hook (budgeted, degrade-safe). Rule compilation stays in the network service; renderer receives the compiled-for-this-page subset.
- **Every decision is an event**: `{ts, identity, tab, origin, target, rule, list_provenance, action, request_class}` → bounded per-tab ring (2k) → **Tracker Observatory** (Panel tab) and the **Activity Ledger** (SQLite, per identity, exportable). "Why was this blocked?" is one click from every blocked resource, citing rule + list.
- Per-site "Shields down" = scoped **dynamic rule** with expiry options once/session/7d/permanent(→Settings) — the exception scopes are part of the contract, matching the Attention Budget rules (§1.11).

## 1.6 Networking architecture

Per-identity `NetworkContext` params: DoH/DoT (presets: quad9/cloudflare/mozilla/cleanbrowsing/custom templates + `!identity` override), proxy (direct/SOCKS5/HTTP CONNECT with auth; user endpoints only), route binding (Tor/wgd SOCKS endpoints), QUIC policy, WebRTC policy (default `disable_non_proxied_udp` under Shield/Fortress/Tor; disabled in Tor), DNS-prefetch and speculative-connection suppression per trust, captive-portal probes re-homed or disabled per route, update checks and component fetches **follow the default identity's route and are labelled as such in the Network tab** (never silently leak on a Tor route — Tor identity disables auto-update by policy and surfaces the fact, learning from Brave's documented failure modes).
**`.onion` rule (law):** non-Tor contexts must not resolve `.onion` at all (fail with a dedicated error + pointer to New Tor Window); the check sits in the *resolver policy*, unit-asserted, and is a leak-suite case (derived from the Brave `.onion`-handling regression class noted by Spec-C).
**Safe Browsing:** v5 Local List + OHTTP relay (§0.1-R6); full-hash lookups via OHTTP; download-hash reputation same path; Enhanced never compiled in. Toggleable in Settings with plain-language consequences; status visible in Panel→Site.

## 1.7 Vault architecture (credentials)

- **P27 (GA credentials):** hardened upstream password manager: OS-keystore-wrapped encryption key (DPAPI / Keychain / libsecret-KWallet with documented password-only fallback on fragmented Linux), no cloud sync, per-identity scoping via `origin+identity → visible/hidden` mediation in `//xr/vault` (the upstream LoginDatabase gains an XR-side scope index; no schema forks), re-auth for sensitive origins, cross-origin **visible** mismatch chip. External managers (KeePassXC, Bitwarden ext) first-class.
- **P28–P30 XR Vault:** `xr-vaultd` sandboxed utility process owning KDBX-4.1 read/write (writer = XR code; keepass-rs reference + corpus), Argon2id (params calibrated at save-time, encoded in header), AES-256-GCM / ChaCha20-Poly1305 via libsodium/BoringSSL only, HMAC-protected blocks per KDBX spec, zero custom primitives (law). Browser process holds **no plaintext, no key material** — item-scoped request/response over `xr.mojom.VaultService`: `Unlock(hint) · ListForOrigin(origin,identity) · GetField(itemId,field) · PutItem · Totp(itemId) · Lock` — there is **no `GetDatabase`, no key export, ever** (interface review checklist makes absent methods a test).
- Autofill mediation (browser process): origin binding (eTLD+1 exact, IDN-homograph check), identity binding ("3 logins hidden — Personal identity" explanation), iframe policy (fill only into top-frame or matching-origin child; block sandboxed/opaque), clickjacking defenses (focus-visible fill, no fill on `about:blank`, re-verify on redress), 45s clipboard auto-clear with countdown, hold-to-reveal. The full §11.5 vault attack suite gates any build that can store real credentials.
- **Passkeys:** P27 platform/hybrid WebAuthn (upstream, unmodified — Windows Hello / Touch ID / security keys). **P33 XR-resident authenticator** only when bound to TPM/Secure Enclave/Hello — browser-resident software passkeys are banned (security downgrade, all three specs concur).
- **Sync (P30):** *one* backend shape — client-side-encrypted vault blobs to **user-owned storage** (WebDAV or S3-compatible; local folder for single-device ceremony). Device pairing over short-lived codes; printable recovery kit; RRRTX can read nothing and resets nothing (copy is contractual, §17). No XR-operated sync service (DR-10).
- **Audit gate (DR-11):** external published cryptographic audit, high/critical closed, *before any stable build stores real credentials*.

## 1.8 Extensions

Upstream MV3 platform, unmodified except: (a) Guard hooks — install/update review UI, static manifest risk grading **A–D** (permissions-as-outcomes: "reads and changes everything you see on every site, including passwords you type"; grade from host-pattern breadth + capability classes; no intent claims, law), `nativeMessaging`/`debugger` deny-by-default with high-friction opt-in (friction attractor: typed confirmation), update-time permission **diff alerts** before enable; (b) **per-identity availability** enforced at `ExtensionFunction::Dispatch` + content-script injection filter + network-egress tagging in Shield (extension requests carry `extension_id`; undeclared-host log/deny per policy; observable endpoints only); (c) Chrome Web Store installs supported best-effort (fork reality), with `.crx`/unpacked sideload + a small **signed XR Verified metadata catalog** (metadata + review notes only — *not* a store, no hosting of extensions beyond mirrors where license-permitted) kept warm as the CWS-contingency (DR-13). MV2: **not revived** (R5); the registry item exists so a future evidence-backed reversal is one-line.

## 1.9 Storage model

| Data | Location | Scope | Encryption/at-rest | Notes |
|---|---|---|---|---|
| cookies/localStorage/IDB/CacheAPI/SW/quota | StoragePartition (`xr:<uuid>`) | identity | OS-level user-dir perms; in-memory for ephemeral | upstream machinery; destroyed-with-identity purge tested |
| permission state | upstream HCMS (global) + **XR identity overlay** (defaults, temp grants, audit) | profile + identity | — | overlay consulted by resolver |
| history, bookmarks, reading list, notes, highlights, pins metadata | **Activity/Content Ledger** (XR SQLite, rows tagged `identity_id`) atop upstream stores | identity-filtered | OS-level | upstream history kept for omnibox compat; ledger is authoritative for identity UI + export |
| identity definitions, site→identity rules, trust bindings, Guard ledger, firewall rules | `//xr` prefs (SQLite) | profile | OS-level | schema migration system mandatory (P6; every row versioned) |
| credentials P27 | Chromium LoginDatabase (+ XR scope index) | identity | OS-keystore-wrapped | |
| Vault | KDBX-4 file(s) | per profile; item scope tags per identity | Argon2id+AEAD | never in prefs; never in logs |
| filter lists / component data | signed bundles in component store | global | signature-verified | fail-closed LKG |
| Observatory ring | memory (2k/tab) + Activity Ledger (bounded, 90d default, user-config, **never uploaded**) | identity | local only | |
| downloads DB | upstream | shared, identity-tagged | — | Panel filters by identity |
| egress/firewall secrets (proxy creds) | OS keystore (not prefs!) | identity | keystore | law: no secret in plaintext prefs |
| Ephemeral everything | memory | window | n/a | FS-diff verified on close |

## 1.10 UI architecture

- **Native views for the 96px that matter** (toolbar, tab strip, identity pill, trust dial, window borders), **WebUI/Lit for panels and pages** (Palette, XR Panel, Settings, Vault, Onboarding, Help, Themes). One design-token pipeline feeds both (§8.6), because *isolation must be painted on the compositor-surfaces a malicious page can spoof-observe* — tab identity bar lives in views.
- **Command Registry**: `Register(id, title, keywords, group, scope: global|window|identity|site, availability predicate, danger class, handler)`; palette, Tools menu, overflow menu, shortcut editor, printable cheatsheet, and **the help index are views over it**; *any feature without a command does not ship* (CI check: every `Settings` section and panel tab maps to a command). Palette ≤50 ms interactive warm / ≤150 ms cold — budgeted in CI (P7 bench).
- **Chrome tiers (from the design system, binding):** Tier 1 always-visible ≤9 controls; Tier 2 one interaction (Palette ⌘K, Panel ⌘⇧X, sidebar, context menus, selection toolbar); Tier 3 Settings search-first, deep-linkable (`xr://settings/network/dns`). Promotion between tiers requires usage data.
- **URL field is security UI:** eTLD+1 emphasis, punycode/IDN caution chip, trust-dial underline, per-tab identity color bar in *every* layout, full-window border for Ephemeral(amber dashed)/Tor(violet solid). Color never alone — always + glyph + text.
- **XR Panel**: 360px right-docked, five tabs — **Site · Network · Extensions · Downloads · Activity** — replacing the four proposed dashboards (all three specs concur; separate "Security/Performance/Observatory centers" = **DROP as separate surfaces**). Activity tab = exportable accountability log ("we show receipts" is the brand).
- **Attention Budget T0–T5 is code**: a small ledger service counts interruption classes; ceilings (T1 ambient chips · T2 toasts ≤8/session · T3 anchored prompts ≤3/hour · T4 interstitials ≤1/week · T5 modals ≤1/month) **demote overflow one tier + log; never silently drop**; T5 requires friction (type-domain/hold); exception prompts offer once/session/7d only — *permanent* exceptions live solely in Settings; `--xr-critical` red reserved for <1/session events. A tier exceeding ceilings for >5% of beta users = P1 design bug (§11.9 gate).
- **Trust dial never auto-reloads**; inline "Reload to apply fully" chip instead (input destruction = trust destruction; all three specs concur).

## 1.11 Data contracts frozen before feature work (the P5 freeze)

`EffectivePolicy` (v1, schema+golden vectors) · `xr.mojom.IdentityManager` · `xr.mojom.PolicyResolver` (pure f with determinism tests) · `xr.mojom.Shield` (+`BlockEvent`) · `xr.mojom.RouteManager` · `xr.mojom.VaultService` · `xr.mojom.GuardLedger` · `xr.mojom.DownloadSafety` · `xr.mojom.ActivityLog` · `CommandRegistry` descriptor format · List-bundle manifest (signed) · Update manifest (3.1 JSON) · Isolation-Card disclosure strings (localizable, legal-reviewed). Each contract ships with: IDL, version, migration note, fixture set, and a **fake implementation** usable by dependent tracks *at freeze time* — later phases never block on earlier implementations, only on contracts (§6 sync points).

## 1.12 Major invariants (CI-enforced or release-blocking; inherited + amended from the three specs)

1. **Storage:** no identity's web storage reachable from another identity via any browser-mediated path. Asserted by the isolation matrix (§11.4).
2. **Processes:** renderers of different identities never share a process — inherited from partition-suitability, *asserted* adversarially under load, not assumed.
3. **Vault:** no vault plaintext or key material in the browser process, logs, crash dumps, or renderer memory — verified by memory-inspection test.
4. **License:** no GPL/AGPL code linked into any shipped binary — CI dep-graph scan; lists/feeds are data; GPL tools are separate processes or absent.
5. **Route integrity:** no traffic leaves an identity's configured egress route — xr-leaktest, every build, every route class, results published.
6. **Ephemeral integrity:** zero bytes of ephemeral-identity data on disk (FS-diff assertion, incl. crash).
7. **Accountability:** every block/deny/grant/expiry decision has an Activity Ledger row with reason code + the rule/permission that caused it.
8. **Upstream security posture:** no XR patch weakens Site Isolation, the sandbox, Mojo validation, or CORB/ORB; no release ships with a known-unpatched upstream critical CVE.
9. **Honesty:** no user-facing claim exceeds the published §1.13 limitations; "anonymous"/"unbreakable"/scores banned in copy (release copy-checklist).
10. **Consent:** nothing leaves the device without a documented exception (update channel, list fetches, SB OHTTP, user search) or explicit opt-in; telemetry default-off with byte-accurate local viewer.
11. **No intent claims:** Guard and Observatory emit observations only; copy review enforces ("XR can see where an extension connects, not what it intends.").
12. **AI boundary:** no assistant/copilot/chat surface anywhere in chrome, panels, omnibox, context menus, or extension APIs.
13. **Identity dignity:** identity is visible on 100% of tabs in 100% of layouts (screenshot assertion in visual CI), and no silent identity switch.
14. **Fail-safe:** death of Shield engine, vault process, tord, or wgd degrades *security posture visibly* (chip goes amber, route fails closed) — never silently, never by bricking browsing.

## 1.13 Published limitations (a shipped surface, not a footnote — Isolation Card + `xr://help`)

Shared across identities (until Fortress promotion): GPU process & OS graphics state; OS DNS cache and hostname resolution side channels; OS clipboard; downloads directory; extension *background contexts* (a broadly-permitted extension is visible across identities by design — Guard narrows this); upstream History DB contents (identity-filtered UI, export tags); CRL-set/CT state. Fingerprinting is **reduced, partitioned, never resisted** — XR's own configurability enlarges the space; that is why we say so. Disposable = browser-side forgetting, not forensic erasure, not network anonymity. Tor mode = Tor *networking*, not Tor Browser; anonymity-critical users are directed to Tor Browser/Tails in-product. Download protection = verification + reputation, not AV. XR Vault = zero-knowledge *by construction*; we cannot help you if you lose the master password — printed, on first unlock.

## 1.14 Module ownership map (also §7)

| Module (//xr/…) | Owns | Track |
|---|---|---|
| `policy/` | resolver, trust contexts, EffectivePolicy, prefs schemas | B |
| `identity/` | partition provisioning, lifecycle, templates, promotion, overlay stores | B |
| `shield/` | adblock-rust binding, list pipeline, events, exceptions | D |
| `net/` | RouteManager, DoH/proxy config, leak policies, onion guard, SB relay | D |
| `fingerprint/` | seeds + surface shims (consumes shield's injection plumbing) | D |
| `extensions/` | Guard: review, grades, availability, egress ledger, verified metadata | D |
| `vault/` + `xr-vaultd` | client, mediation, KDBX, TOTP, sync-crypto | C |
| `downloads/` + `xr-inspect` | pipeline hooks, quarantine, verdicts | C |
| `commands/` | registry, palette glue, shortcut table | F |
| `tools/` | screenshots, reader glue, notes, highlights, translate framework | F |
| `ui/` | views + webui: panel, settings, onboarding, themes | F |
| `network/helpers/` | `xr-tord/`, `xr-wgd/` | E |
| `mojom/` | the contracts (§1.11) | A (chair) |
| `patches/` | the upstream budget ledger | A |

Module law: **a subsystem may not import another subsystem's internals — only `mojom` + `//xr/common` types.** The resolver is imported by everyone; it imports no one.

---
# 2. CANONICAL FEATURE & SUBSYSTEM INVENTORY (THE FEATURE REGISTRY)

The definitive registry of everything XR contains. **A feature that is not in this table does not exist for XR.** Verbs: **BUILD** (XR writes it) · **INTEGRATE** (ship a 3rd-party component largely as-is) · **ADAPT** (shape/policy-wrap an upstream capability) · **DEFER** (architecturally reserved from P5 contract freeze; implemented in a later phase — DEFER ≠ omitted) · **DROP** (decided not to build; rationale recorded so the question stays closed; reversal requires new evidence in the Decision Register).

Columns: **D**ecision · **O**wner (subsystem) · **Dep**endencies · **Ph**ase (§4) · **Crit**icality (P0 launch-moat / P1 daily-driver / P2 depth / P3 advanced) · **Sec** security-sensitivity (S0 = security-critical code path; S1 = security-surfacing; S2 = privacy-adjacent; S3 = none) · **Risk** (major technical risks) · **Proof** (validation requirement, expands to the §4 phase DoD and §11 tests).

## 2.1 Foundation & engine

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Chromium/Blink/V8 engine via overlay repo | BUILD(overlay) | A/infra | P2,P3 | P1–P39 | P0 | S0 | rebase treadmill; seam loss | full 3-OS builds per patchset; WPT parity ≥ upstream−0.5% tracked daily; CVE SLA metrics published |
| Modern web compat posture (never weaken upstream guarantees) | LAW | A | — | all | P0 | S0 | regressions from patches | compat corpus (top-1k + hard-app list) per release; site-isolation assumption tests |
| De-Googling (RLZ/UMA/GAIA/GCM/field trials; strip Gemini surfaces) | ADAPT | A | P2 | P1,P6 | P0 | S2 | breakage of update/components paths | build-manifest audit: zero Google endpoints except disclosed list (§9.13) |
| XR branding, icon set, `xr://` scheme surfaces | BUILD | E | P7 | P6 | P1 | — | trivial churn | visual + install tests |
| Windows 10+/macOS 12+/Linux desktop | BUILD | A | P2 | P10 | P0 | — | platform drift | per-OS smoke matrix green |
| Android | DEFER | (new track) | full arch stable | P39+ | P2 | — | second-platform team cost | gated by decision DR-23a at P39 review |
| iOS | **DROP** | — | — | — | — | — | WebKit mandate kills the moat | — |

## 2.2 Shield: blocking, fingerprinting, site protection

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Native network ad/tracker blocking (`adblock-rust` in network service) | INTEGRATE+BUILD | D | P4,P5,P10 | P11 | P0 | S0 | list-format drift; perf | uBO conformance corpus ±2% on 1,000-site benchmark; p99 ≤1 ms; memory ≤80 MB |
| Cosmetic filtering + scriptlets (document-start Blink seam) | BUILD | D | P11 | P12 | P0 | S0 | layout breakage; hook death | 0 corruption on compat corpus; degrade-safe kill-switch test |
| Filter lists as signed runtime data (EasyList, EasyPrivacy, uAssets, Peter Lowe, AdGuard) | INTEGRATE(data) | D | P10 update stack | P11 | P0 | S0 | list channel = attack surface | signature pin/rotation drill; fail-closed LKG test; GPL-as-data license audit green |
| Per-site Shields-down + scoped exceptions (once/session/7d/Settings-only) | BUILD | D | P6 resolver | P13 | P0 | S1 | exception sprawl | expiry tests; settings-only-permanent assertion |
| Breakage-report pipeline (user-initiated, redacted, public tracker) | BUILD | E+D | P13 | P13 | P1 | S2 | privacy of reports | report contains zero page content by schema test |
| Tracker Observatory (per-tab ring 2k + categorization by list provenance) | BUILD | D+E | P11 | P13 | P0 | S1 | OOM via unbounded log (real footgun) | bounded-ring soak; categorization accuracy spot-audit |
| "Why was this blocked?" explainers (rule + list provenance) | BUILD | D+E | P11 | P13 | P0 | S1 | mislabeling | 100% events carry rule-id+list; fuzz no crash |
| Fingerprint farbling: canvas/WebGL/AudioContext per-eTLD+1-per-session | BUILD | D | P4 seam | P20 | P0 | S0 | site breakage; perf | Brave-style determinism tests; compat diff ≤ baseline+0.5% |
| `deviceMemory`/`hardwareConcurrency` clamps, font enumeration limits, navigator/screen normalization | BUILD | D | P20 | P20 | P1 | S0 | detection of clamps | AmIUnique-family regression suite (expect improvement, ban claims) |
| Letterboxing | BUILD (Fortress opt-in) | B | P20 | P35 | P2 | S1 | UX damage | default-off assertion; Fortress-only test |
| Third-party cookie blocking, storage partitioning, CHIPS, referrer trimming | ADAPT (upstream default-on) | B | — | P16 | P0 | S0 | none — inherit | upstream defaults asserted; no reimplementation |
| HTTPS-First / always-upgrade with styled interstitial | ADAPT | D+E | — | P16 | P0 | S1 | downgrade UX | per-trust policy tests |
| Malicious/phishing protection: SB v5 Local-List + OHTTP relay; Real-Time opt-in; Enhanced never | ADAPT | D | legal LG-2 | P16 | P0 | S0 | license terms (non-commercial) | protocol mode matrix + no-phone-home packet capture; legal sign-off artifact |
| Punycode/IDN homograph caution + eTLD+1 emphasis | ADAPT+BUILD | E | P7 | P16 | P0 | S0 | subtle bypasses | homograph suite incl. mixed-script vectors |

## 2.3 Identity, containers, disposables, trust

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| **Identity (the moat)** = StoragePartitionConfig seam + overlay stores | BUILD | B | **P4 spike**, P5 freeze | P14 | P0 | S0 | papercuts (downloads/print/DevTools/omnibox); upstream seam change | isolation matrix 100% or disclosed §1.13 row; mixed-tab windows E2E; per-identity NSContext binding test |
| Identity templates (Personal/Work/Research/Banking/Shopping/Disposable/Tor as *tunable starting points*, user-named) | BUILD | B | P14 | P14 | P0 | S1 | preset zoo ≈ false security | creation ceremony shows defaults applied (transparency copy) |
| "Containers" as separate user concept | **DROP** (merged into Identity; word resolves in palette) | F | — | — | — | — | vocabulary confusion | naming lint in docs |
| Site→identity assignment rules; never silent switch | BUILD | B | P14 | P17 | P0 | S1 | wrong-identity logins | suggestion-only UX test; move=destructive+confirm |
| Disposable (ephemeral) identities — plural, simultaneous, in-memory | BUILD | B | P14 | P14 | P0 | S0 | disk residue | FS-diff zero-bytes incl. crash-kill |
| Mixed identities in one window | BUILD | B | P4 spike result | P14(v1)/P34(split) | P0 | S0 | chrome confusion | per-pane persistent identity chip visual test |
| Per-identity `NetworkContext`: DNS + proxy + route binding | BUILD | D | P14,P10 | P17,P18 | P0 | S0 | shared-state leaks | xr-leaktest per route, published |
| Fortress-promoted identity (dedicated OTR Profile) | BUILD | B | P14 | P35 | P2 | S0 | profile mgmt complexity | promotion ceremony + rollback test |
| Preset identity zoo as *security boundary* | **DROP** → templates | — | — | — | — | — | "Shopping isn't a threat model" | — |
| Profiles (OS-persona) | ADAPT | B | — | P14 | P1 | — | de-emphasize but keep | import/export per profile |
| **Adaptive Trust** = one resolver; dial Standard/Shield/Fortress (3 positions) | BUILD | B | P6 | P14 | P0 | S0 | unreadable if 5 modes; combinatorial QA | resolver exhaustive unit matrix; usability gate §17 (users state mode unaided) |
| Tor/Disposable as dial positions | **DROP** — they are identities | — | — | — | — | — | mode explosion | IA test |
| Per-identity partitioning of DNS cache/HSTS/TLS-state where shared upstream | BUILD (Fortress-promoted; disclosed elsewhere) | D | P35 | P35 | P2 | S0 | hard; partial | leak matrix documents exceptions or closes them |
| Workspaces (tabs+layout, never logins) | BUILD | F | P22 | P23 | P1 | S3 | scope creep | hidden-until-second-workspace assertion |
| "Workspaces as security boundary" claims | **DROP** (organizational only) | — | — | — | — | — | — | copy review |

## 2.4 Permissions, extensions, Guard

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Permission Firewall: per-identity defaults + one-time grants + audit + revoke-all | ADAPT(HCMS+PermissionManager)+BUILD(overlay, ledger) | B | P6,P14 | P15 | P0 | S0 | grants leaking across identities | grant state-machine tests incl. expiry; ledger row per grant |
| Runtime auditing of permission *usage* | **DROP** | — | — | — | — | — | needs WebAPI hooks across Blink; low yield | — (re-check annually, evidence required) |
| Extension support (MV3) | ADAPT (upstream) | D | P3 | P21 | P0 | S0 | CWS fragility for forks | top-100 CWS install/run/uninstall corpus |
| Extension Guard: static manifest review → A–D grade, outcomes-as-copy | BUILD | D | P21 | P21 | P0 | S1 | false precision | copy checklist: zero intent claims; grade reproducibility test |
| Per-identity extension availability ("Banking runs zero extensions") | BUILD | D | P14 | P21 | P0 | S0 | enforcement gaps | dispatch-chokepoint test from disallowed identity = denial + ledger row |
| `nativeMessaging` / `debugger` deny-by-default, high-friction opt-in | BUILD | D | P21 | P21 | P0 | S0 | friction fatigue | default-denied asserted; typed-confirmation flow |
| Egress observation: extension requests through Shield; undeclared-host log/deny | BUILD | D | P11 | P34 | P1 | S1 | proxy/cert noise | endpoint-vs-declared diff tests |
| Update-time permission diff alerts | BUILD | D | P21 | P34 | P1 | S1 | alert storms | Attention Budget ceiling test |
| Behavioural "this extension is tracking you" verdicts | **DROP — banned** | — | — | — | — | — | unfalsifiable | copy gate |
| MV2 compatibility layer | **DROP** (upstream deleted machinery 2026-07-28) | — | — | — | — | — | unbounded fork cost | re-check task per §12.6 |
| Own extension store | **DROP** | — | — | — | — | — | ops company | — |
| Sideload `.crx`/unpacked + signed "XR Verified" metadata catalog | BUILD | D | P21 | P21 | P1 | S1 | metadata mirror licensing | signature verify; catalog staleness SLA |
| **XR Panel (5 tabs: Site · Network · Extensions · Downloads · Activity)** — replaces the separate Security/Performance/Observatory/Firewall dashboards of the source concepts | BUILD | E | P7,P11,P13→P34 | P13 | P0 | S1 | dashboard sprawl creeping back | visual+perf budgets; parity bot checks subsystem-tab registration; every row links evidence |

## 2.5 XR Vault & credentials

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Launch credentials: hardened upstream password manager, OS-keystore, identity-scoped | ADAPT | C | P14 | P27 | P0 | S0 | keystore fragmentation (Linux) | per-OS keystore tests + documented fallback |
| Password generator | BUILD | C | P27 | P27 | P1 | S1 | weak defaults | entropy config tests |
| **XR Vault** core: KDBX-4.1 in sandboxed `xr-vaultd` | BUILD(+INTEGRATE crypto) | C | P5 contract, P28 | P28–P29 | P0 | **S0** | data loss (lossy writes — keepass-rs write path experimental **[VERIFIED]**) | golden-corpus round-trip matrix vs KeePassXC/KeePass; §11.5 full suite |
| Zero custom primitives (BoringSSL/libsodium/RustCrypto) | LAW | C | — | P28 | P0 | S0 | — | dep audit + code review checklist |
| TOTP (RFC 6238, auto-clear copy) | BUILD | C | P29 | P29 | P1 | S1 | clock drift | vectors + drift tests |
| Secure notes | BUILD | C | P29 | P30 | P1 | S1 | — | export/import parity |
| Autofill with visible cross-origin + cross-identity guards | BUILD | C | P27 | P29 | P0 | S0 | the CVE generator | full §11.5 attack suite (iframe, redress, clickjacking, homograph, about:blank) |
| Passkeys — USE platform/hybrid (Chromium WebAuthn) | ADAPT | C | — | P27 | P0 | S0 | must not break upstream | WebAuthn compat suite (security keys, Hello, Touch ID) |
| Passkeys — XR-resident authenticator, **hardware-bound only** | BUILD | C | P29 audit | P33 | P2 | S0 | per-platform token APIs; recovery story | attestation + wipe/recovery ceremony; software-only = banned (design review gate) |
| Payment cards | DEFER | C | P29 | P39 | P2 | S1 | PCI-adjacency, abuse value | demand evidence required to start |
| Local-first zero-knowledge model; "we cannot reset" copy | LAW | C | — | P27 | P0 | S0 | — | help-copy contract test |
| Encrypted sync — BYO storage (WebDAV/S3), client-side E2EE, multi-device pairing | BUILD | C | P29 | P30 | P1 | S0 | key ceremony UX; conflict merge | sync threat-model tests; offline-matrix; conflict no-loss |
| BYOK + printable recovery kit | BUILD | C | P30 | P30 | P0 | S0 | key loss | naive-user recovery drill on clean machine |
| XR-operated sync service | **DROP** | — | — | — | — | — | ops liability | — |
| Vault sharing / emergency access | **DROP** | — | — | — | — | — | multipart KMS ≠ feature | — |
| External cryptographic audit | BUILD(gate) | C | P28 | P28–P30 | P0 | S0 | finding backlog | **no stable stores real creds until published audit + closures** |

## 2.6 Network sovereignty

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| DNS controls: per-identity DoH/DoT, presets + custom templates | ADAPT | D | P14 | P17 | P0 | S0 | misconfig leaks | DNS leak matrix every route |
| Proxy per identity (SOCKS5/HTTPS + auth) | BUILD | D | P17 | P18 | P0 | S0 | fail-open mistakes | fail-closed test (route loss ⇒ error, not direct) |
| **VPN (XR-operated)** | **DROP — permanently** | — | — | — | — | — | different company | — |
| **WireGuard** via `xr-wgd` (wireguard-go userspace → local SOCKS5) | INTEGRATE | D | P18 | P32 | P1 | S0 | key mgmt UX; perf | route proof; key lifecycle; proxy-down kill test; no-TUN asserted |
| Tor via `xr-tord` (Arti default / C-tor fallback), per-first-party stream isolation, DNS-in-tunnel, WebRTC off, `.onion` confined | INTEGRATE | D | P14,P19 | P31 | P1 | S0 | leaks; younger engine churn | Tor leak suite green = only path to ship; disclosure modal read-gated |
| Tor *handoff* (open in Tor Browser) cheap affordance | BUILD | D | P14 | P19 | P1 | S2 | false sense | copy: handoff, not equivalent |
| Onion websites support (view `.onion` in Tor identity only) | BUILD | D | P31 | P31 | P1 | S0 | non-Tor resolution | resolver-policy unit assert + leak case |
| Region routing = exit dropdown on user endpoints, never XR infra | ADAPT | D | P18/P32 | P32 | P2 | S2 | geo-unblocking expectations | no such marketing claim (copy gate) |
| Network Firewall: per-site/identity allow-deny rules over Shield engine | BUILD (view+rules) | D | P11,P6 | P34(rules UI)/P11(engine) | P1 | S0 | blind-click rule creation | deliberate sub-dialog; scope ladder once/session/site/identity |
| Network status live view (route, resolver, latency, offline state) | BUILD | D+E | P18 | P18 | P1 | S1 | stale data | staleness indicator test |

## 2.7 Productivity & tools

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Universal Search + custom engines + `!bang` + per-identity defaults | ADAPT(TemplateURLService) | E | P7 | P24 | P1 | S2 | revenue-lever simplicity loss (deliberate) | engine CRUD E2E; bang conformance |
| Research providers (arXiv, Semantic Scholar, PubMed, GitHub, manpages…) as curated bangs | BUILD | E | P24 | P24 | P1 | S3 | list rot | curated-file freshness check |
| "Research Mode" as named mode | **DROP** → template+presets | — | — | — | — | — | mode explosion | — |
| Bookmarks (+identity metadata, search, import) | ADAPT | E | P14 | P25 | P1 | S3 | — | move/tag E2E |
| Notes (page- and workspace-scoped, Markdown, per identity, export) | BUILD | E | P25 | P25 | P1 | S3 | sprawl | export/import round-trip |
| Pins → **Highlights** (`#:~:text=` + provenance) | ADAPT+BUILD | E | P25 | P25 | P1 | S3 | silent anchor miss | anchor-miss honest fallback test |
| Reading list (upstream + identity metadata) | ADAPT | E | — | P25 | P1 | S3 | — | E2E |
| Reader mode (typography, width, theme, save) | ADAPT(Reading Mode) | E | — | P25 | P1 | S3 | distiller edge pages | corpus render parity |
| Screenshot: visible → +full-page → +region → +redact/annotate | BUILD | E | P7 | P25(visible/full)/P26(region/redact) | P1 | S1 | PII in annotations | redaction irreversibility test |
| Translation: provider framework (user endpoint/self-host; offline option only if Google-free), inline provider disclosure, per-origin memory, default-off | ADAPT+BUILD | E | P5 contract | P34 | P1 | S2 | silent page-content egress (banned) | packet capture proves provider+consent; provider shown before send |
| Media downloading: direct `<video/audio src>`, plain HLS/DASH-as-file (no DRM) | BUILD | C(downloads) | P26 | P26 | P1 | S1 | legal posture creep | policy lint: no manifest decryption; only unprotected bytes |
| Universal extractor ("download any media") | **DROP** | — | — | — | — | — | §1201 pressure onto a *signed browser*; weekly-break treadmill | — |
| DRM circumvention | **DROP — categorical** | — | — | — | — | — | — | contribution-policy ban |
| Download manager (queue, pause/resume, per-identity tagging) | ADAPT | C | P26 | P26 | P1 | S1 | — | E2E under throttle |
| Download security: magic/MIME/extension mismatch, dangerous-type warnings, MoTW (Win)/quarantine (mac), Authenticode/notarized-signature display, hash display, **VirusTotal link only — never upload**, quarantine-until-acknowledged | BUILD | C | P26 | P26 | P0 | S0 | sniffing bugs | xr-inspect fuzz 72h clean; verdict fixtures |
| Archive content peek | BUILD (in xr-inspect) | C | P26 | P26 | P1 | S0 | hostile archives | sandbox escape tests; zip-bomb limits |
| XR malware-scanning engine | **DROP** | — | — | — | — | — | we are not an AV | — |
| Performance tools: Task Manager re-skin + Memory Saver + tab discard + per-identity aggregation | ADAPT | E | P14 | P34 | P1 | S3 | re-derivation of telemetry stack (banned) | no new data collection (audit) |
| DevTools: unmodified + XR panel as internal DevTools extension (identity/partition view, block decisions, storage contents) | ADAPT | G | P14 | P34 | P1 | S2 | none (patches banned) | DevTools version-drift smoke per promotion |

## 2.8 UX shell & polish

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Command Registry + Palette (⌘K) — first feature | BUILD | E | P5,P7 | P7 | P0 | S3 | scope creep of "every command" | 50ms/150ms budgets in CI; every settings section = command |
| Tabs: top/vertical/rail/compact, identity-aware; groups | BUILD+ADAPT | E | P7 | P22 | P0 | S1 | tab-strip perf at 500 tabs | bench + visual CI (identity bar everywhere) |
| Split view (2–4 panes; focused pane owns toolbar; same-identity first; mixed at P34) | BUILD | E | P14 | P23(same-id)/P34(mixed) | P1 | S1 | address-bar ambiguity (solved by focused-pane rule) | E2E + accessibility |
| Focus View (explicit, 3 recovery routes, security UI always wins) | BUILD | E | P7 | P34 | P1 | S1 | hides security signals | auto-exit on any security UI test |
| Compact mode / sidebar | BUILD | E | P7 | P22/P34 | P1 | S3 | — | visual |
| Themes: declarative JSON tokens only — **no CSS, no JS in themes** (+custom import framework at P30; security boundary, not limitation); contrast ≥4.5:1 enforced by loader | BUILD | E | P8 | P30(ui)/P6(tokens) | P1 | S1 | web-exposed color side channels (Fortress: normalize) | loader rejects failing theme; side-channel test in P20 |
| Built-ins: Light, Dark, System, High Contrast (+2 curated); themed gallery post-GA (community, format-locked) | BUILD | E | — | P30 | P1 | S3 | QA matrix per theme | visual regression ×theme |
| Settings: search-first, deep-linkable, XR sections | ADAPT(WebUI) | E | P7 | P8(v0)/P31(full) | P0 | S1 | forking settings UI (banned) | every setting reachable by search+URL |
| Onboarding ≤4 screens + teach-on-use (6 lifetime coach marks) | BUILD | E | P14 | P37 | P0 | S2 | tour fatigue | first-run completion telemetry-free timing study (local) |
| Migration/import: Chrome/Edge/Firefox/Brave/Vivaldi (bookmarks, history, passwords re-encrypted, engines, extensions→Guard review) + **KDBX/CSV vault import at first run** | ADAPT+BUILD | E+C | P27 | P37 | P0 | S1 | importer fragility | fixture corpus per source; password re-encrypt verified |
| Help: `xr://help`, threat-model browser, "what this does NOT protect against" mandatory section | BUILD | E | P6 | P37 | P0 | S1 | stale docs | doc-parity CI: feature flags ↔ help entries |
| Accessibility: WCAG 2.2 AA gates, AAA for security copy where practical; keyboard model; SR labels; reduced-motion; no color-only signal | BUILD(program) | G | P9 | P36 (+per-phase gates) | P0 | S1 | SR contracts on novel surfaces | axe CI + NVDA/VoiceOver/Orca manual passes per release |
| Localization: ICU pipeline; en + 9 at stable (incl. RTL locales); security copy human-reviewed per locale | ADAPT | G+E | P9 | P36 | P0 | S2 | RTL layout drift; string freeze slips | pseudo-loc + RTL smoke pre-freeze |
| Backup/recovery: per-identity encrypted export bundles; session restore; crash card not modal; vault recovery kit | BUILD | C+E | P28,P30 | P30/P37 | P1 | S1 | bundle corruption | restore-on-clean-machine drill |

## 2.9 Operations, trust, supply chain

| Feature | D | Owner | Dep | Ph | Crit | Sec | Risk | Proof |
|---|---|---|---|---|---|---|---|---|
| Updates: `//chrome/updater` client + XR update server (signed manifests, staged, delta, **rollback**, visible failed-state w/ manual download) | BUILD(client reuse) | A | P2 | P10 | P0 | S0 | update channel compromise | signature/rollback/downgrade attack tests; update drill per release |
| Component updates (lists, OHTTP configs, tor geoip, Widevine path, models) via upstream component-updater on XR endpoints | ADAPT | A | P10 | P10 | P0 | S0 | same as above | pinned-keys + rotation drill |
| Release channels: nightly (dev-only, unsiged→test-signed) / beta / stable (+ ESR-class "XR Security Series" patch cadence between promotions) | BUILD | A | P10 | P10 | P0 | S1 | channel skew | channel matrix E2E |
| Signed artifacts + transparency log of build hashes (sigstore/rekor; in-toto/SLSA-style attestations) | BUILD | A | P10 | P10→P38 (independent rebuilder) | P0 | S0 | key compromise | verify-at-CDN; rebuild attempt publishes delta |
| Bit-identical reproducible builds | DEFER — **no date ever promised**; ladder: toolchain pins → determinism-of-XR-code → independent rebuilds | BUILD(ladder) | A | P39 | P2 | S0 | chasing chromium-wide nondeterminism = multi-year | only *current rung* is claimable (§0.3) |
| SBOM (CycloneDX from GN third_party graph + cargo metadata) published per release | BUILD | A | P2 | P10 | P0 | S1 | SBOM tooling drift | diff gate; unknown-license fails build |
| Dependency policy: pin, review, `cargo vet`-style auditable allowlist for Rust/Go deps | BUILD | A | — | P1 | P0 | S0 | supply chain | CI license+advisory gates |
| Telemetry: default **off**; opt-in aggregate; local "what would be sent" byte viewer; crash reports opt-in, URL/credential-scrubbed | BUILD | A/G | P10 | P13(viewer)/P38 | P0 | S0 | accidental phone-home | endpoint capture diff = documented set |
| Bug bounty + coordinated disclosure + SECURITY.md + advisories | BUILD | G | — | P1 | P0 | S1 | unmanaged intake | runbook drill (synthetic report end-to-end) |
| Open-source governance: public monorepo, DCO, contribution guide, RFC process for `//xr` contracts, published patch ledger, CODEOWNERS | BUILD | A | — | P1 | P0 | S1 | drive-by PRs into S0 code | CI requires 2-review label on S0 paths |
| Security testing program: fuzz fleet, SAST, isolation/leak suites, red-team weeks | BUILD | G | P9 | P9→P38 | P0 | S0 | theater without cadence | §11; CI green definitions |
| Crypto wallets / tokens / rewards / ads / sponsored tiles / feeds | **DROP — permanently** | — | — | — | — | — | sells the product's only asset | New Tab = zero network beyond user search (test) |
| AI assistant/copilot/agent/chatbot/LLM (any surface) | **DROP — permanently** (DR-12; sole exception: non-conversational offline translation/reader utility) | — | — | — | — | — | breaks "page content stays local" | copy+feature checklist; build-flag scan for AI endpoints |
| Security scores / "% protected" | **DROP — banned** | — | — | — | — | — | unfalsifiable | copy gate |

## 2.10 Explicitly-reserved interfaces (the "full product from day one" mechanism)

At the P5 contract freeze, the following ship as **typed interfaces + fakes + fixtures even though implementation lands later**: RouteManager (covers proxy/WG/Tor before WG/Tor exist) · VaultService (covers autofill mediation for P27 before vaultd exists) · GuardLedger (covers update-diff/egress in P34) · DownloadSafety (covers xr-inspect) · ActivityLog (every subsystem's accountability rows) · EffectivePolicy fields for fingerprint/letterbox/storage-scope (resolver is total from day one — unknown fields ⇒ deny, never guess). A phase may not invent a parallel path around these; extending requires an approved contract-amendment RFC (L14; procedure ships with P5-T10).

---
# 3. DEPENDENCY GRAPH

Not the illustrative chain in the brief — derived from §1 boundaries and §2 dependencies. Read `X → Y` as "Y cannot start before X completes (its DoD is green)"; `[par]` marks parallel lanes.

```
                         ┌─────────────────────────────────────────────────────────┐
                         │ P1 Governance/Legal/Funding gate (DR-01, LG-1..3)       │
                         └───────────────┬─────────────────────────────────────────┘
                                         ▼
                         P2 Build System + Hermetic Chromium Build ──┐
                                         │                            │
                         P3 Rebase machinery + patch-budget CI [par]─┤
                                         ▼                            ▼
                         P4 IDENTITY-SEAM SPIKE (go/no-go)   P5 CONTRACT FREEZE (mojom+schemas+fakes)
                                 │  (result feeds P11..P14)          │  (everything after P5 codes against fakes first)
                 ┌───────────────┼──────────────────┬────────────────┼─────────────────┐
                 ▼               ▼                  ▼                ▼                 ▼
            P6 policy resolver  P7 Command      P8 WebUI/theme   P9 TEST infra     P10 Update+Release
            (pure, total)       Registry+shell  tokens, settings  harness, CI       v0, signing, SBOM
                 │               │   v0          skeleton          fixtures          │
                 ├───────┬───────┴──────────────┬─────────────────┴──────┬───────────┘
                 ▼       ▼                      ▼                         ▼
            ┌─── STAGE 2 — Shield & Identity ──────────────────────────────────────┐
            │ P11 adblock-rust network v1 ─▶ P12 cosmetic/scriptlets ─▶ P13 panel+ │
            │ observatory+exceptions+breakage pipeline                               │
            │ P14 Identity v1 (seam per P4) ─▶ P15 Permission Firewall ─▶ P16 site │
            │ protections (HTTPS-First, SB+OHTTP, URL field, cookie/partition        │
            │ defaults)                                                              │
            └───────────────┬─────────────────────────────┬────────────────────────┘
                            ▼                             ▼
            ┌─── STAGE 3 — Network & Extensions ───────────────────────────────────┐
            │ P17 per-identity DNS/DoH ─▶ P18 proxy+route UI+fail-closed ─▶ P19    │
            │ leak-suite v1 (all routes incl. handoff-Tor)                         │
            │ [par] P20 fingerprint reduction (needs P12 hook infra, P6 resolver)  │
            │ [par] P21 Extension Guard v1 (needs P14 identity scoping)            │
            └───────────────┬──────────────────────────────────────────────────────┘
                            ▼
            ┌─── STAGE 4 — Daily-driver UX ────────────────────────────────────────┐
            │ P22 tabs v2 ─▶ P23 workspaces+session store ─▶ [par] P24 search/     │
            │ engines; P25 bookmarks/notes/highlights/reader/screenshot; P26        │
            │ downloads+security+direct media                                      │
            └───────────────┬──────────────────────────────────────────────────────┘
                            ▼
            ┌─── STAGE 5 — Vault ──────────────────────────────────────────────────┐
            │ P27 credential hardening (upstream manager, identity scope) ─▶       │
            │ P28 xr-vaultd core (KDBX, sandbox, fuzz) ─▶ P29 vault UX+autofill ─▶  │
            │ P30 sync+BYOK+recovery+notes  ⚑ external-audit gate spans P28–P30    │
            └───────────────┬──────────────────────────────────────────────────────┘
                            ▼
            ┌─── STAGE 6 — Advanced ───────────────────────────────────────────────┐
            │ [par] P31 Tor identity (needs P19 leak suite) · P32 WG helper ·       │
            │ P33 hardware-bound passkeys · P34 mixed split+focus+sidebar+perf+      │
            │ translate+devtools panel+network-firewall rules+extension egress       │
            │ P35 Fortress grade (letterbox, profile promotion, partition hardening)│
            └───────────────┬──────────────────────────────────────────────────────┘
                            ▼
            ┌─── STAGE 7 — Full product & release ─────────────────────────────────┐
            │ P36 a11y+l10n completion · P37 onboarding/migration/help · P38 beta+  │
            │ pentest+independent-rebuild+bounty program · P39 GA + community        │
            │ launch + long-horizon register (cards, Android, on-device translation,│
            │ repro ladder, theme gallery)                                           │
            └───────────────────────────────────────────────────────────────────────┘
```

**Critical path (must-not-slip):** P2 → P4/P5 → P6 → P14 → P17/P18 → P19 → P28 → P31. Anything on it slips ⇒ the phase *after* it re-plans, features never skip a DoD.

**Hard prerequisites worth stating explicitly (the three specs each under-specified at least one):**
1. **P4 before P11–P14 scope lock** — if the partition seam loses papercut classes, Shield/Identity UX scoping changes shape; deciding *after* building is the retrofit the brief forbids.
2. **P5 freeze before P6+** — dependent teams code against fakes from day one; this is what lets 7 tracks run in parallel without interface drift (the anti-"retrofit after individual features exist" mechanism).
3. **P9 test infra before feature phases** — every §4 phase declares tests it *runs*, not tests it *invents* mid-flight (isolation-matrix runner, leak harness, visual CI, WPT bot exist first).
4. **P10 update/release v0 before any public build** — a browser without an emergency-patch path is a liability; the SLA machinery predates features so the treadmill is proven under load.
5. **P19 leak suite before P31/P32** — Tor and WireGuard ship only against an existing green baseline; no bespoke per-feature leak one-offs.
6. **P28 fuzz+design-review before audit engagement**; **audit closure before real credentials in stable** — the vault's two non-negotiable gates (DR-11).

**What can proceed with zero engine dependencies (pure/WebUI/infra):** P1, P3 tooling, P5 docs/IDL, P6 resolver (C++, testable against fakes), P7 registry logic, P8 WebUI shell, P9 harnesses, P10 server-side work, list-bundling tooling, xr-vaultd crypto core (independent Rust crate!), xr-wgd/xr-tord engines (independent processes!), Themes engine, Notes/Highlights storage layer. **The helper processes are deliberately independent-buildable** — Stage 5/6 tracks start their *engine* work early and integrate late.

---

# 4. COMPLETE PHASE-BY-PHASE BUILD PLAN (+ §5 WORK BREAKDOWN — tasks are the WBS)

**Format per phase:** Objective / Why / Prereq / **Tasks (WBS — issue-ready)** / Touches / Contracts out / Deps in / Decisions locked / Security req / UX req / Tests / Manual / Perf / Rollback / **DoD** / Artifacts / Feeds.
Task IDs are `XR-Pxx-Ty`; each is written so an engineer (or agent) can open it as a GitHub issue without asking questions first. Task grammar law (§5; laws L8/L11): a task names *what to change, where, the contract, the tests, what must not break, and the verification artifact*.

## STAGE 0 — PROVEN GROUND (P1–P5)

### Phase P1 — Governance, legal gates, repository skeleton
- **Objective:** Make the project legal, licensed, funded-gated, and open-source-ready before any code compiles.
- **Why:** Three gates can each kill the product later if not decided now: fork viability (funding), Widevine (LG-3), Safe Browsing terms (LG-2). MPL-2.0 + GPL rules must exist before the first import.
- **Prereq:** none (this phase *is* the gate).
- **Tasks:** XR-P1-T1 create `xr-browser` meta-repo + `xr-core` repo (MPL-2.0 LICENSE, README, CONTRIBUTING, DCO); T2 adopt `docs/adr/` RFC system (template + numbering); T3 write `SECURITY.md`, embargo process, security@ routing, disclosure policy, bounty charter v0; T4 publish `docs/threat-model.md` v0 (T1–T11 adversary table from §9.1, with the "does NOT protect" column); T5 legal brief LG-1 fork viability + codec budget, LG-2 SB v5 terms (non-commercial clause, Web Risk fallback, OHTTP relay operators), LG-3 Widevine CDM redistribution per platform — each with a written verdict; T6 funding-gate check per DR-01 (staffing ≥10 engineers or invoke §15 fallback posture, recorded); T7 CODEOWNERS with S0 path list (sandbox/Mojo/vault/crypto/network) requiring dual senior review; T8 dependency-intake form (license/health/security/maintenance-burden/current-status per external project — the *evaluation* artifact for every §2 INTEGRATE row); T9 decision-register tool (dr-parse: machine-checkable `DR-xx` table with status).
- **Touches:** repo root, `docs/`, CI (license scanner, DCO bot).
- **Contracts out:** ADR template; dependency-eval template; S0 path list.
- **Deps in:** none. **Decisions locked:** DR-01 (funding), DR-02/03/04 (Chromium/overlay/MPL) re-ratified here with §0 evidence; DR-14/15 equivalents = LG-2/LG-3 *opened*, not guessed.
- **Security req:** disclosure pipeline *tested* (synthetic report walked end-to-end).
- **UX req:** none. **Tests:** license-scan fails on an injected GPL sample; DCO bot blocks unsigned PR.
- **Manual:** counsel memo filed for LG-1..3 (verdicts, not vibes). **Perf:** n/a.
- **Rollback:** n/a — decisions recorded, not un-made.
- **DoD:** repos exist; MPL-2.0 everywhere in `//xr`; LG-1..3 written verdicts attached to DR entries; threat model v0 published; S0 review rules enforced by CI.
- **Artifacts:** `LICENSE`, `SECURITY.md`, `threat-model.md@v0`, LG memos, dependency-eval pack v1 (pre-filled for adblock-rust/Arti/wireguard-go/keepass-rs/BoringSSL/libsodium/Lit per Appendix A research).
- **Feeds:** everything; specifically unlocks P2 and the §8 procurement of anything.

### Phase P2 — Build system & hermetic Chromium build
- **Objective:** `./build x` reproduces a branded, fully-offline-capable XR binary on Win/mac/Linux from pinned sources, on real CI hardware.
- **Why:** The fork is a build system first. Brave/ungoogled/Thorium evidence: teams that skip hermetic builds die of "works on my machine" rebase debt.
- **Prereq:** P1.
- **Tasks:** T1 vendored Chromium checkout via DEPS pins (`chromium_ver`, `v8_rev`, …) with a *refresh* command; T2 GN arg set (`xr_branding`, disable GoogleService APIs, `enable_widevine=false` default, component-updater endpoints→XR dev URL); T3 `xr-core` mount script into `src/xr` with patch-manifest applicator (each patch = `{id, owner, files, patchinfo.md}`); T4 ccache + remote cache + build farm bring-up (Linux/mac bare-metal, Win VMs — capacity sized at 26 Chromium canaries/year × 3 OS × config matrix); T5 toolchain pins (clang/autolink SDKs), sysroot digests recorded; T6 de-branding pipeline (icons, strings GRD overrides, about-page); T7 build docs exact enough for external rebuild; T8 artifact signing *scaffold* (test certs) — real certs land P10; T9 build-time SBOM emission (GN third_party walk + cargo metadata) wired to artifact; T10 patch-manifest CI counting hook (budget meter, no budget yet).
- **Touches:** `xr-browser/build/`, `xr-core/BUILD.gn`, scripts, CI runners.
- **Contracts out:** patch-manifest format v1; DEPS pin policy; SBOM schema.
- **Deps in:** P1 repos. **Decisions locked:** no in-tree fork; overlay repo + DEPS pinning; build flag names become public API.
- **Security req:** build scripts have zero network beyond pinned remotes; provenance of every toolchain digest recorded.
- **UX req:** none. **Tests:** clean-VM build matrix; bit-stability of two same-input builds *for XR-owned targets* (chromium-wide determinism deferred).
- **Manual:** a contributor outside RRRTX reproduces a nightly per docs; time-to-first-build recorded.
- **Perf:** cold build ≤ 4× chromium reference; warm ≤ 25 min at cache-hit 90%.
- **Rollback:** any toolchain bump is a PR; revert = pin change.
- **DoD:** 3-OS builds green nightly for 2 consecutive weeks; external-rebuild proof filed; SBOM published on dev channel.
- **Artifacts:** build docs, nightly artifacts (test-signed), SBOMs.
- **Feeds:** P3 (needs a bot that can build), P4 (needs to build experiments fast), P10 (real signing).

### Phase P3 — Upstream tracking machinery (rebase bot + patch budget)
- **Objective:** Prove the treadmill is *survivable at the real 2026 pace*: automated canary rebase with owner-routed conflicts, and an enforced, published patch budget.
- **Why:** This is the "a lagging security browser actively harms users" insurance, and the cadence change (R9) makes automation non-optional. None of the three specs automated *conflict routing* — ours does.
- **Prereq:** P2.
- **Tasks:** T1 daily job: fetch upstream canary, `git`-rebase `xr-core` patches onto chromium/main, build, run patch-budget check; T2 conflict classification: for each failed patch, file auto-issue at owner team with diff context + last-touch upstream commits; T3 budget gate: upstream-touched-files ledger (per §1.2 categories, ≤150 total, per-category caps), CI fails on exceed, count *published in release notes*; T4 weekly *promotion* job against even milestones (Extended-Stable-equivalent series, R9) running full compat smoke (P9 corpus stubs ok); T5 security fast-lane: watch Chromium security tags; cherry-pick→build→promote pipeline with SLA clock + on-call rotation defined; T6 patchinfo lint (every patch must reference owner+rebase-notes+upstream-bug-if-any); T7 "seam retirement" metric: patches *removed* by upstreaming or obsolescence, charted per release.
- **Touches:** `xr-browser/ci/`, `xr-core/patches/manifest`, dashboards.
- **Contracts out:** patch ledger format; SLA metrics definition (measured from *tag publication*, not announcement).
- **Deps in:** P2. **Decisions locked:** daily-canary/8-week-promotion split; conflicts are *work items*, not outages; budget is law from commit #1 of P4 onward.
- **Security req:** fast-lane artifacts signed with the same keys as releases; no unsigned hotfix path, ever.
- **UX req:** none. **Tests:** synthetic rebase drill — inject a fake upstream refactor across 5 XR patches, verify classification+issues+fix; budget-break injection fails CI.
- **Manual:** 2 consecutive real promotions executed by on-call, ≤2 person-hours each.
- **Perf:** rebase bot wall-clock ≤ 8h end-to-end.
- **Rollback:** promotion abort ⇒ stay on prior milestone; SLA breach escalates per §13.6.
- **DoD:** 3 consecutive upstream ranges auto-rebased green; published budget meter; two synthetic security-fast-lane drills < 72h.
- **Artifacts:** rebase dashboard, SLA metrics feed, patch ledger.
- **Feeds:** every later phase codes with the treadmill running under it.

### Phase P4 — Identity-seam spike (go/no-go; the moat's foundation)
- **Objective:** Empirically validate (or falsify) §1.4: identities as per-WebContents `StoragePartitionConfig` domains inside one profile — cookies/storage/SW/cache isolation, non-shared renderers, per-partition NetworkContext proxy/DNS, ephemeral partitions, mixed-identity tabs — and enumerate papercuts with owners.
- **Why:** R2 ruling. A product-defining architecture must be *proven in code* before a dozen teams build against it; all three specs guessed at Chromium's real constraint instead of measuring it.
- **Prereq:** P2, P5 *contract drafts* (interfaces may wobble during P4; only P4 output feeds P5 freeze for identity-adjacent contracts).
- **Tasks:** T1 PoC: patch `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance` consult (from `WebContentsUserData` identity), verify via `chrome://process-internals`; T2 isolation probe: cookies/LS/IDB/CacheStorage/SW/BroadcastChannel/SharedWorker/`window.name`/favicon-cache matrix between two partition domains; T3 process-sharing probe: same-site across identities never co-locates (scripted under 50-tab load, Task Manager + `--enable-logging` verification); T4 network probe: bind distinct SOCKS + DoH per partition via `NetworkContextParams` diff; confirm DNS cache/HSTS/TLS-session behavior (which states follow the context, which don't) — *this task produces the §1.13 disclosure table as measured fact*; T5 ephemeral probe: `in_memory` partition writes nothing (FS-diff); T6 papercut census with repro + suggested owner + patch estimate: downloads, printing, DevTools attach, omnibox providers, drag-and-drop cross-identity, find-in-page, picture-in-picture, service-worker notifications, `chrome://` pages, autofill UI, tab search; T7 promotion probe: same identity model but a dedicated OTR *Profile* (Fortress) coexists cleanly with partition identities; T8 write ADR: chosen seam + fallback trigger criteria + patch estimate; T9 if falsified: execute fallback plan (identity=BrowserContext, per-window) and re-cut §4 P14 scope (documented, not improvised).
- **Touches:** throwaway branch of chromium/src + `//xr/spike/` (deleted after ADR); results recorded in `docs/spike-identity/`.
- **Contracts out:** measured shared-state table; `IdentityProvisioning` request surface informed for P5.
- **Deps in:** P2. **Decisions locked:** DR-06/DR-09-equivalent identity model *final*; patch estimates accepted.
- **Security req:** spike results include "what an attacker could observe cross-identity" notes feeding §9.
- **UX req:** none (no UI). **Tests:** probes 1–5 scripted, re-runnable, output diffable (they graduate into §11.4 isolation matrix).
- **Manual:** none beyond probe logs. **Perf:** process-count delta per identity ≤ +2×tabs; context-creation cost recorded.
- **Rollback:** spike branch never merges.
- **DoD:** ADR approved by Platform+Security leads; measured tables published; P5 contracts updated to match reality; no open P0 papercut without owner+phase.
- **Artifacts:** `docs/spike-identity/*` (probes included), ADR-0042 "identity seam," updated patch estimates.
- **Feeds:** P5 freeze, P14, P17, §11.4 fixtures, §1.13 copy.

### Phase P5 — Contract freeze (`//xr/mojom`, schemas, fakes)
- **Objective:** Every subsystem's *interface* exists, versioned, reviewed, with fakes and fixtures — before feature code.
- **Why:** The brief's "full product from day one" is enforced here: later phases integrate against frozen contracts, enabling 7-track parallelism without retrofit.
- **Prereq:** P1 (S0 review rules), P4 measured model.
- **Tasks:** T1 author IDLs: `policy_resolver.mojom` (`Resolve(IdentityId, Origin, TrustContext?, RequestClass) → EffectivePolicy` + `PolicyVersion` + determinism note), `identity.mojom`, `shield.mojom` (+`BlockEvent`), `route_manager.mojom` (`Bind/Unbind/Status/LoseAllFailClosed`), `vault.mojom` (item-scoped only; **absence tests**: no `GetDatabase`/`ExportKeys` methods), `guard.mojom`, `downloads.mojom`, `activity_log.mojom`; T2 `EffectivePolicy` v1: fields for blocking/cosmetic/perms/egress/fingerprint/storage-scope/vault-scope/process-policy — **total function: unknown input ⇒ deny** (all three specs' "one resolver" made testable); T3 command-descriptor + settings-schema + theme-token formats; T4 list-bundle manifest (signed envelope, key pin list, delta rules); T5 update-manifest profile (3.1 JSON) + rollback semantics; T6 golden vectors for resolver (table-driven, hand-authored, becomes P6 truth table); T7 fakes for every interface in `//xr/fakes/` + a `xrctl` dev CLI to drive them; T8 contract review (S0) + freeze stamp; T9 `xr-schema` migration tool design (prefs/ledger tables carry versions from creation); T10 write "contract amendment" RFC procedure (binds L14).
- **Touches:** `xr-core/mojom/`, `docs/contracts/`, `xr-core/fakes/`.
- **Contracts out:** all §1.11 items v1. **Deps in:** P4. **Decisions locked:** §1.11 list frozen.
- **Security req:** interface review checklist includes "narrow surface, typed errors, no generic exec, fuzz target required before integration" — *per interface, signed off*.
- **UX req:** command/settings schemas reviewed by Design for tiering/labels/danger-class.
- **Tests:** IDL parse+golden serialization; fake parity harness (fakes satisfy the same contract-test suite written in P9).
- **Manual:** none. **Perf:** message-size budgets declared in IDL comments (Observatory batch ≤ 64 KB/event chunk).
- **Rollback:** amendment process only; no silent edits.
- **DoD:** all contracts reviewed, faked, fixture-shipped, frozen-tagged; dependent teams build v0 flows against fakes.
- **Artifacts:** `//xr/mojom` v1, golden vectors, fake lib, contract docs.
- **Feeds:** P6–P10 immediately; *all* later phases.

## STAGE 1 — SPINE (P6–P10)

### Phase P6 — Policy resolver v1 (pure, total, exhaustively tested)
- **Objective:** The one brain: Standard/Shield/Fortress × Identity × Site (× Extension) → EffectivePolicy, with persistence and site-override storage.
- **Why:** Every phase from P11 onward consumes it; retrofitting = rewrite (all three specs agreed; nobody wrote its truth table — we do).
- **Prereq:** P5.
- **Tasks:** T1 implement `xr/policy/` C++20: pure `Resolve()`, cache (identity,site,trust)→policy with invalidation counters; T2 pref schemas + `xr-schema` migrations for: identity list, trust bindings (per-site, per-identity via ⌥), exceptions registry (scopes once/session/7d/permanent-with-expiry-mechanics), fingerprint/permission sub-policies as *data* (consumers land later); T3 resolver service over `xr.mojom.PolicyResolver` in browser process, snapshot distribution to network service + renderer via versioned blob (incremental, ≤32 KB); T4 golden-vector runner in CI (vectors from P5-T6 + generator: 100% branch coverage, mutation-tested); T5 policy-change event stream (what changed in human terms — feeds the dial strip); T6 `xrctl policy dump` diagnostics; T7 enterprise policy seam (`xr://policy` reads OS-managed policy sources; enforcement *preempts user settings* — minimal now, formal later).
- **Touches:** `xr/policy/`, prefs, mojom impl. **Contracts out:** EffectivePolicy v1 wire format stable.
- **Deps in:** P5 fakes. **Decisions locked:** 3-position dial semantics; per-site default with per-identity ⌥; "never guess" totality; exceptions never "forever" in-flow.
- **Security req:** resolver is S0: dual review, fuzz input handling of prefs (corrupt prefs ⇒ deny-default, no crash); no TOCTOU — consumers hold the version they validated with.
- **UX req:** change strip copy = concrete deltas ("camera, mic, location now blocked · stricter isolation · Undo"), no scores, no auto-reload — codified as the event payload schema.
- **Tests:** golden table; pref-corruption fuzzer 24h; cache invalidation race unit suite; migration round-trips (v1→v2 when it comes: property test).
- **Manual:** dev build flips dial per-site; log proves single source of truth (grep for rogue mode checks fails the build — static lint).
- **Perf:** `Resolve()` p99 ≤ 5 µs cached, ≤ 200 µs cold; snapshot apply ≤ 2 ms.
- **Rollback:** schema versions make downgrade a data-preserving no-op (tested).
- **DoD:** CI matrix green incl. mutation score ≥ 90%; lint bans subsystem-private mode logic (introduced with P7/P8 adoption).
- **Artifacts:** resolver lib+service, policy docs, truth tables in `docs/contracts/policy.md`.
- **Feeds:** P13, P15, P16, P20, P21, P31, P34, P35 consume.

### Phase P7 — Command Registry + browser shell v1 + palette
- **Objective:** The spine UI: one registry, four views (palette, menus, shortcut editor, help index), window chrome skeleton carrying identity/trust slots.
- **Why:** "Any feature that cannot express itself as a command does not ship" is only real if the registry exists first; also builds the WebUI toolchain everything else reuses.
- **Prereq:** P5, P6 (commands toggle policy).
- **Tasks:** T1 registry service: descriptors (id, title, keywords, group, scope, availability predicate, danger class, handler); T2 palette UI (Lit WebUI, ≤50 ms interactive warm / 150 cold — CI bench with synthetic 2000-command corpus); T3 Tools/Overflow menu views generated from registry + tier rules; T4 shortcut editor view + conflict detection + storage in prefs schema v1; T5 wire first 20 commands (new tab/window/identity/disposable/tor-later placeholder, panel open, dial steps, shields toggle stub, settings jump); T6 window/toolbar skeleton: identity pill slot, trust dial slot (visual states), shield chip slot, URL field shell (display logic in P16); T7 per-tab identity color bar in tab strip (layout-agnostic; visual CI asserts); T8 WebUI build toolchain: Lit pin, bundling, CSP policy for all WebUI (no inline JS — theme law preview); T9 command-coverage CI check (every settings section + panel tab maps to ≥1 command).
- **Touches:** `xr/commands/`, `xr/ui/`, `//chrome/browser/ui` hooks (budgeted: ≤12 files now).
- **Contracts out:** command descriptor v1; availability-predicate contract (reads resolver).
- **Deps in:** P5, P6. **Decisions locked:** four-views-one-registry; palette budgets; tier-1 ≤9 controls.
- **Security req:** WebUI CSP strict; palette never executes page-originated commands (cross-process origin check on invocation).
- **UX req:** full keyboard model from day one (tab/enter/esc, SR labels); RTL-safe layout; empty-state discipline (no "coming soon" rails — inherited amendment).
- **Tests:** registry unit (dupes, predicate flips); palette E2E (type→execute); shortcut persistence through crash-kill; visual snapshot of chrome states (identity color × themes).
- **Manual:** keyboard-only walkthrough of Tier-2 by an a11y engineer; power-user dogfood week 1 (engineers as Chrome refugees).
- **Perf:** budgets above; cold start regression vs same-milestone Chromium ≤10% (measured nightly).
- **Rollback:** pure additive UI; feature-flag `xr_command_registry_v1` off ⇒ stock chrome (kept until P13).
- **DoD:** budgets met in CI, toolchain stable for other tracks, first-20 commands wired, a11y pass v0.
- **Artifacts:** palette, shortcut editor, chrome skeleton, WebUI toolchain + its CI caches.
- **Feeds:** P8 (settings uses registry+toolchain), P13 (panel), P22 (tab UI builds on strip), P37 (onboarding drives commands).

### Phase P8 — WebUI platform, settings v0, theme tokens v1
- **Objective:** Settings skeleton (search-first, deep links) + declarative token theming with contrast enforcement + i18n pipeline live.
- **Why:** Every later subsystem needs a settings home and a token contract; theming-as-security-boundary (no CSS/JS) must be platform early so "custom themes" never become an escape hatch retrofit.
- **Prereq:** P7 toolchain.
- **Tasks:** T1 `xr://settings` shell: search index (client-side, fuzzy, aliases include "container(s)"), section registry generated from settings-schema (P5), deep-link router, *extends* upstream `settings/` pages where they exist (no fork of the giant page); T2 token system: 40± tokens (surfaces/text/borders/accents/identity palette/critical-red reserved) consumed identically by C++ views (generated header) and Lit (generated CSS/custom-prop) from one JSON source; T3 theme engine: built-ins Light/Dark/System/HighContrast; loader = validate schema → contrast audit (AA 4.5:1 body, 3:1 large, security-critical AAA where practical) → *refuse failing themes*; T4 custom-theme format v0 (declarative tokens only; parser hardened; no URLs/fonts beyond bundled list; theme import = explicit confirm listing deltas); T5 i18n: Chromium l10n hookup for WebUI, `.xtb` for views, pseudo-locale `qyy` build + RTL smoke in CI; T6 settings search/analytics = local counters only (Attention-budget ledger v0 lives here: tiered counters, no upload); T7 help-deep-link contract (settings ↔ xr://help anchors).
- **Touches:** `xr/ui/settings/`, `xr/ui/themes/`, generated-token build.
- **Contracts out:** token schema v1, theme JSON schema v1, settings-section registry.
- **Deps in:** P7. **Decisions locked:** theme law (no CSS/JS, loader refuses); search-first settings; 4+2 themes.
- **Security req:** theme import path = hostile input (fuzz from first commit); tokens can't reach web content (web-exposed system-color surfaces normalized — formalized P20).
- **UX req:** every setting deep-linkable; every label localizable from day one (string extraction lint).
- **Tests:** contrast validator property tests; settings-search recall fixture (≥95% top-3 for 200-phrase set); RTL snapshot suite; theme fuzzer.
- **Manual:** switch theme mid-window (no reload); High-Contrast + SR walk.
- **Perf:** settings first-paint ≤ 300 ms cold; theme apply ≤ 100 ms.
- **Rollback:** token versioning.
- **DoD:** all gates green in CI; other teams using tokens by mandate (lint in `//xr`).
- **Artifacts:** settings shell, theme pipeline, l10n tooling.
- **Feeds:** P13 (panel theming), P21 (guard UI), P29 (vault UI), P30 (custom themes), P36 (l10n completion).

### Phase P9 — Test & benchmarking infrastructure v1 (the proof machine)
- **Objective:** Every verification surface in §11 *exists as automated infrastructure* before the feature phases need it.
- **Why:** The brief's central demand — "phases are proven, not declared" — is only true if the machinery predates the claims. This is also where each track stops inventing fixtures mid-flight.
- **Prereq:** P5 (fakes to test against), P2/P3 (CI).
- **Tasks:** T1 extend Chromium browser-test harness with XR fixtures (multi-identity windows, ephemeral partitions, controllable network stubs, frozen-clock mode); T2 **isolation-matrix runner** (P4 probes graduate; identity × mechanism × assertion grid, incl. adversarial load mode; new "documented exception" requires §1.13 row in same commit — CI-checked); T3 **xr-leaktest harness** v0: per-route capture (tcpdump/pcap filter language), probes for DNS egress, WebRTC ICE, prefetch, captive-portal, extension-origin requests, `xr://` subresources, update checks, SB lookups, OCSP/CRL path, NTP/geo; results JSON → artifact; T4 **compat corpus runner**: top-500 global + 200 regional + 50 hard-app flows (login, upload, video, conferencing smoke), daily Beta-parity job comparing against same-milestone Chrome; WPT pass-rate bot vs upstream (delta ≤0.5%, tracked per promotion); T5 **perf budget service**: telemetry from dedicated bench rigs (fixed hardware list in `docs/hw.md`), budgets as code (`perf-budgets.json`), PR + nightly gates, regressions auto-assign; T6 **visual regression**: Chromium Gold integration for tab-strip/panel/themes identity-marks ×layouts; T7 a11y CI: axe-core on all WebUI, AXTree snapshot tests for views, keyboard-traversal harness; T8 fuzzing fleet: ClusterFuzzLite targets for `//xr` Rust (kdbx stub, list parser, theme parser, archive sniff stubs) + Mojo interface fuzz harness (contract-driven from P5 fakes); T9 SAST: clang-tidy custom checks (no mode-logic outside `//xr/policy`; no direct pref reads bypassing resolver), rust-clippy+`cargo vet`+`cargo audit` gates, Semgrep rules for banned APIs (`str::crypto*`, raw net in vault client); T10 update-drill lab (P10's acceptance tool): per-OS VM farm with snapshot/restore, "kill mid-update" scripts; T11 crash/recovery drill kit: process-type kill matrix under load w/ assertions (session restore, ephemeral-clean, no identity bleed); T12 evidence conventions: every DoD links a CI run id — "green" defined machine-side.
- **Touches:** `xr/test/`, `ci/`, bench rigs, gold config.
- **Contracts out:** evidence format (machine-checkable phase DoD records — feeds §17 gate tool).
- **Deps in:** P2–P5. **Decisions locked:** §11 automation split; corpus contents; budget set (numbers below).
- **Security req:** test rigs isolated from prod signing keys; leak harness verifies *itself* (loopback-baseline canary).
- **UX req:** none. **Tests:** meta-tests: each runner must fail when fed a deliberately broken fixture (mutation-check the checker).
- **Manual:** quarterly "harness health" review in QA charter.
- **Perf:** corpus run ≤ 6 h nightly; budget noise < 2%.
- **Rollback:** infra versions pinned per branch.
- **DoD:** all runners green against fakes + P2/P7/P8 actuals; CI evidence conventions merged; a feature team can satisfy a DoD *only* via §11 artifacts.
- **Artifacts:** the proof machine; `docs/qa/evidence.md`.
- **Feeds:** literally every subsequent phase's DoD.

### Phase P10 — Update, signing & release engineering v0
- **Objective:** End-to-end *shippable* release machinery: real signing, update server, channels, staged rollout, rollback, transparency log — before any build is given to humans outside the team.
- **Why:** Spec-A/B/C all treat updates as "a system to build" late; the opposite is true — an auto-updating browser without a proven kill-switch/rollback is the fastest way to ship a catastrophe. Reusing in-tree `//chrome/updater` (R11 ruling) shrinks scope by an engineer-year.
- **Prereq:** P2, P3, P9-T10.
- **Tasks:** T1 integrate `//chrome/updater` client build; T2 write `xr-updateserver` (stateless: version graph, channel→cohort policy, signed manifests in 3.1 JSON; no personal data beyond coarse install-count sampling, *opt-in per platform repo*, documented); T3 key hierarchy + ceremony docs (offline root, per-platform signing keys, HSM for stable key, rotation runbook); T4 Windows: EV-equivalent code signing + SmartScreen reputation program started (long lead — begin now); macOS: Developer ID + notarization + stapling in CI; Linux: deb/rpm repos with in-repo metadata signatures, AppImage with embedded update metadata; T5 staged rollout controls (cohort %, crash-rate auto-halt hook consuming P38 telemetry contract early — dev channels only until then), **rollback to prior version** verified; T6 transparency: every release artifact hash → sigstore/rekor; release-notes automation (consumed upstream security advisories table — per-train CVE mapping); T7 SBOM attach + license-report generation per release (SBOM-tool from P2-T9); T8 update *UX contract*: About page states version/chromium-base/build-hash/sig-status/rollback availability + **failed state with manual-download pointer** (no silent failures — law); T9 "manual-update drill" as release-gate artifact.
- **Touches:** `xr/update/` (client glue), `xr-browser/release/`, update server repo.
- **Contracts out:** update-manifest v1 consumed; channel/cohort semantics; transparency format.
- **Deps in:** P2/P3/P9. **Decisions locked:** in-tree updater client; our own server; per-platform packaging matrix; *no component update of the browser binary itself* (only via full signed releases).
- **Security req:** sig verification independent of TLS; manifest replay/downgrade protections (monotonic versions + epoch key); update server compromise ⇒ still requires valid sig; key ceremony witnessed.
- **UX req:** About + failure surfaces + notification policy (T1 ambient only).
- **Tests:** server fuzz (API), rollback/downgrade/forged-manifest negative suite; kill-mid-update VM drills on 3 OS × per-system/per-user layouts; repo GPG/ostree-ish signature tests.
- **Manual:** red-team: attempt to force a bad update in staging end-to-end (logged, findings closed).
- **Perf:** update check ≤ 2 KB, ≤ 1/6h backoff-adaptive; delta packages ≥ 60% size win (measure, don't claim before).
- **Rollback:** server-side epoch revocation (kill any client line); client refuses downgrade.
- **DoD:** three OSes auto-updated through a real version bump in staging, including rollback drill; transparency entries verifiable externally; SmartScreen/notarization paths live.
- **Artifacts:** release engineering handbook v1, update server, signing infra, nightly/beta/stable channels (dev-only until P16 exit).
- **Feeds:** P13 (breakage-report channel rides it), P11 list updates (component updater config), everything shipping anything.

## STAGE 2 — SHIELD & IDENTITY v1 (P11–P16)

### Phase P11 — XR Shield v1: native network blocking + list pipeline
- **Objective:** `adblock-rust` in the network service: real blocking of ads/trackers with signed list bundles, before any renderer exists.
- **Why:** The table-stakes half of the product; the MV3 landscape (DNR's caps/dynamism limits — verified by Spec-C's math and made moot here because *we are the browser*) makes native the only honest answer; and observatory/exception/firewall/Guard-egress all ride this engine, so it lands early.
- **Prereq:** P6 (resolver consults), P10 (list component channel), P9 (corpus + fuzz).
- **Tasks:** T1 vendor `adblock-rust` pin + `cargo vet`; T2 embed in network service via URLLoaderFactory interception: classify(request context: identity, site, request class) → allow/block/redirect/resource-replace; performance path (compiled flat buffers per list set, shared across contexts — Brave's −75% memory work **[VERIFIED public]** informs sizing); T3 list pipeline: `xr-lists/` tooling compiles upstream lists → normalized bundle (ABP/uBO syntax superset incl. scriptlet + $replace directives) → signs via P10 channel → client verifies (pinned keys), applies atomically, falls back LKG; license attribution embedded (EasyList dual GPL/CC data posture recorded in legal appendix); T4 resolver-coupled exception scopes + per-site toggle mechanics (dynamic rule add/remove, expiry sweep job); T5 BlockEvent emission → ring + Activity Ledger; T6 kill switches: `xr://shield` debug page (engine status, last-apply, memory, list versions; dev builds only) + enterprise force-disable path; T7 perf instrumentation: p99 per-request decision; T8 corpus parity job vs reference uBO config on 1,000-site capture set (fix expectations in-repo, upstreamed where they're *engine* bugs — §12.7 upstream-first list).
- **Touches:** `third_party/rust/adblock`, `xr/shield/`, network service seams (budget: ~8 files), `xr-lists/`.
- **Contracts out:** list-bundle manifest consumed v1; BlockEvent schema live.
- **Deps in:** P6, P10. **Decisions locked:** adblock-rust (no custom engine — unanimous); lists as signed data (no GPL link); engine death ⇒ **fail-open** browsing (amber chip), route loss ⇒ fail-closed (different subsystem, do not conflate).
- **Security req:** parser fuzz from commit #1 (P9 fleet) 10⁹ execs before stable; bundle signature rotation drill; no list-executed logic beyond engine-supported scriptlet sandbox (scriptlets run with page privileges — documented and *bounded to scriptlet-ABPF sandbox semantics*, i.e. no page access, per adblock-rust's own model).
- **UX req:** shield chip count = the *only* passive security counter (silent otherwise — Attention Budget T0); "why blocked" text from P13 (events now).
- **Tests:** engine conformance (upstream fixtures + corpus); LKG fallback (corrupt bundle injected); update-atomicity under load; per-identity scoping (rule X applies to identity A exceptions ≠ B); resource-replace fixtures.
- **Manual:** dogfood 2 weeks full-time; breakage-triage rota live (median <48h SLA — the pipeline is P13-T5 but rota starts here).
- **Perf:** p99 decision ≤ 1 ms/request; memory ≤ 80 MB default sets (budget in P9 service); list apply ≤ 1.5 s background.
- **Rollback:** client pins last-2 bundle versions; bad upstream list hot-pinned out via XR manifest (no re-fetch).
- **DoD:** parity ±2% on corpus w/ FP ≤0.5%; budgets green 14 days; fuzz clean; signed channel drill incl. rotation.
- **Artifacts:** Shield v1, `xr-lists` release, conformance reports.
- **Feeds:** P12 cosmetic, P13 observatory/panel, P34 firewall-rules UI & extension egress, P16 phishing interplay.

### Phase P12 — Cosmetic filtering + scriptlet injection (renderer seam)
- **Objective:** Hide-and-fix the ads the network layer can't (injected content, soft walls, element-level junk) at document-start, degrading safely.
- **Why:** Cosmetic filtering is half of uBO's real value; a Blink seam is one of XR's most expensive patch classes — built once, paid per train, so it ships with kill-switches and *no* page-visible failure modes.
- **Prereq:** P11 (rule infra), P4 (partition awareness for per-identity rule sets).
- **Tasks:** T1 Blink hook: on document creation, request compiled cosmetic key-set for (site, identity-trust) via mojom, apply via inline-styles + `#if`/`#?` selector engine + scriptlet injection at document-start (isolated world; no main-world access for scriptlets beyond what ABPF allows); T2 per-page rule *blob* cache in network service (avoid re-IPC per frame; identity-aware keys); T3 generic hide set always-on (no rules ⇒ no work — perf posture); T4 scriptlet registry (uBO-compatible subset; each scriptlet documented w/ capability note) + *degrade test* (each scriptlet disabled individually never breaks page render); T5 exception interplay: shields-down site disables cosmetic *and* network atomically (single scope object); T6 Blink patch stays within budget category (≤25 files; measured), each with patchinfo + "hook-death = cosmetic off, never blank page" assertion suite; T7 upstream-first check: file any engine limitations as adblock-rust/Blink issues (recorded in §12.5 ledger).
- **Touches:** `xr/renderer/cosmetic/`, Blink (budgeted), mojom.
- **Contracts out:** cosmetic-blob format v1.
- **Deps in:** P11. **Decisions locked:** degrade-safety law; no main-world scriptlet injection; exceptions atomic with network.
- **Security req:** scriptlets = the dangerous bit: registry-reviewed, fuzz the rule compiler, page-origin can't inject into the isolated world (asserted), CSP untouched (no eval in engine path).
- **UX req:** zero chrome (T0 silent); "why blocked"/"shields down" cover cosmetic too; soft-wall scriptlets listed in Observatory as *page-modifying* (honest categorization).
- **Tests:** cosmetic fixtures (known ad layouts), SPA mutation churn, 3rd-party frame edge (OOPIF cosmetic applies in frame's partition, not embedder's), breakage diff on corpus ≤ baseline +0.5%, kill-switch suite.
- **Manual:** corpus spot-check w/ design (no layout corruption on 50 hard apps); dark-mode + high-contrast theme × cosmetic interaction check.
- **Perf:** document-start add ≤ 4 ms p95 (budgeted), DOM-poll (abpc) cost ≤ upstream reference uBO measurement.
- **Rollback:** feature off ⇒ network-only Shield (still coherent product).
- **DoD:** corpus deltas within budget; Blink patch count under category cap; fuzz clean; scriptlet suite green.
- **Artifacts:** cosmetic module, scriptlet registry docs.
- **Feeds:** P13 (full "why" incl. cosmetic events), P20 (shares injection plumbing), P35 (letterbox reuses same hook).

### Phase P13 — XR Panel v1 (Site) + Tracker Observatory + breakage pipeline
- **Objective:** The accountability surface: what's blocked, why, what's connected, what is *not* isolated — one panel, tabbed, exportable.
- **Why:** Transparency is the brand; four proposed dashboards (Spec-A/B/C all converged) collapse into one; and breakage reports decide whether Shield's defaults are shippable — the pipeline must exist *with* the feature, not after.
- **Prereq:** P7 (panel host + commands), P11/P12 (events).
- **Tasks:** T1 Panel frame (360 px, right docked; keyboard-first; focus trap correctness); T2 Site tab: TLS/cert basics, trust dial inline, per-site exception controls (scopes), permissions summary (links to P15), **Isolation Card** = measured §1.13 table (data-driven, not prose — from P4 output), blocked-by-category + "why" drill to rule/list/source; T3 Observatory: ring→virtualized list (2k cap; filter by type/origin; export JSON/CSV — redaction rules: no query params by default, opt-in full); T4 breakage report: one-click from any blocked row ⇒ redacted context (origin, UA-LESS browser version tag, rule id, list version — *never* page content/cookies; schema-enforced) → P10 channel → public GitHub queue w/ SLA labels; T5 update-available UX + channel state surfacing (T1 tier only); T6 local "what would be sent" viewer v0 (telemetry/crash previews — privacy guarantee #1 begins here); T7 panel perf hardening (lazy tabs, 150 ms open budget).
- **Touches:** `xr/ui/panel/`, ledger query APIs.
- **Contracts out:** report schema v1; panel tab registration API (subsystems add tabs declaratively).
- **Deps in:** P7, P11/12. **Decisions locked:** one panel; "no scores"; export formats are contracts (stable).
- **Security req:** report path is a data-leak audit item (schema review + redaction fuzz); panel never reflects vault material (only item *titles* from P27+ via mediated, per-identity allowlisted query).
- **UX req:** every row answers *what happened / why / what can I do / undo*; empty states honest ("nothing blocked — this page is clean or Shields are down: [Show why]"); offline state (Amendment #5 from Spec-A §3.9 adopted: routes/latency stale visibly).
- **Tests:** virtualized 2k list; export redaction; "why" 100% event coverage (fuzzed no-null-rule); report schema negative suite (attempts to smuggle content rejected pre-send).
- **Manual:** SR pass (labels on ring list rows); breakage triage drill w/ upstream list owners.
- **Perf:** open ≤150 ms; ring render ≤16 fps worst-case scroll.
- **Rollback:** panel-only additive.
- **DoD:** panel shipped in beta builds; corpus-linked breakage pipeline live w/ 48h median proven on 20 seeded reports.
- **Artifacts:** Panel v1, observatory, public breakage tracker.
- **Feeds:** P15 (permission surface), P18 (Network tab), P21 (Extensions tab), P26 (Downloads tab), P29 (Activity grows), P37 (onboarding references panel).

### Phase P14 — Identity v1 (provisioning, templates, disposables, visual chrome)
- **Objective:** The moat, usable: create identities, bind tabs, see it everywhere, disposable plural, history/ledger scoping, hibernation.
- **Why:** Everything network/vault/Guard keys off this; Spec-A/B/C unanimous on identity-per-window *at minimum*, our P4 spike decides how far past that v1 goes.
- **Prereq:** P4 (measured seam), P6, P8 (settings home), P13 (Isolation Card data).
- **Tasks:** T1 `xr/identity/`: provisioning (partition domain mint, overlay rows, icon/color/glyph, per-identity prefs namespace), lifecycle (activate/hibernate/destroy with purge-and-verify), concurrency cap + hibernation (discard renderers, preserve state, "wake ≤ 200 ms to first paint" budget); T2 templates engine: Personal/Work/Research/Banking/Shopping + Disposable/Tor (Tor = template *now*, route binding lands P31 — the shape exists: violet border, disabled-by-default until route manager binds) with creation ceremony listing every default applied (transparency amendment from Spec-A §3.9); T3 window/tab binding: default-identity per window; move-across-identity = confirm + reload (destructive law); right-click "Open tab in identity…"; site→identity suggestion (no auto-switch); T4 visual system in *all* layouts: 2 px tab color bar + identity glyph/text, pill (name/color/route summary), ephemeral full-window border (amber dashed), SR-announced on tab focus; T5 history/bookmarks identity tagging via ledger overlay (upstream history untouched; omnibox results filterable); T6 Disposable: in-memory partitions, close ⇒ zero-bytes FS-diff assertion wired to P9 matrix, "no vault access" policy row active; T7 `xr://identities` manager (create/rename/recolor/archive, per-identity stats: tabs, storage size w/ purge button, permission count); T8 crash/restore integration: session store carries identity binding, restore never bleeds (P9-T11 drill); T9 papercut closure from P4 census (each: test + owner + budget); T10 memory accounting: per-identity RSS attribution (feeds P34 perf + docs honesty).
- **Touches:** `xr/identity/`, content/UI seams (budgeted), session restore.
- **Contracts out:** IdentityProvisioning internals frozen against P5 contract; ledger `identity_id` everywhere.
- **Deps in:** P4/P5/P6/P8/P13. **Decisions locked:** R2 seam (or documented fallback shipped); vocabulary table §1.4; "never auto-switch"; groups can't span identities (enforced at T3 move logic).
- **Security req:** dual senior review on provisioning + session paths (S0); identity state never in URL/IPC-visible strings (partition domains are opaque UUIDs — brute-force isolation probes in P9 suite); cross-identity process assertion in every build.
- **UX req:** onboarding-adjacent copy frozen now (P37 builds on it): "Identities separate your logins" four-word rule surfaces at first use, teach-on-use mark #1 (second account on same provider detected ⇒ offer identity, once).
- **Tests:** full §11.4 isolation matrix green-or-documented; lifecycle chaos (kill -9 each process type w/ identities live: restore correctness + ephemeral zero-residue); hibernation wake budget; 500-tab × 5-identity memory soak within cap; color-bar visual snapshot per layout×theme.
- **Manual:** mixed-identity window walkthrough ×3 themes; move-tab destructive-confirm usability on 6 non-engineers; SR announcement audit.
- **Perf:** window open +6% vs baseline identity-per-window; idle-identity overhead ≤40 MB; switch ≤200 ms.
- **Rollback:** identities are additive; destroy purges cleanly (tested) — plus `xr://identities` "reset all" dev escape.
- **DoD:** isolation matrix 100%; budgets green; papercut census closed or explicitly deferred-with-owner (no silent); visibility assertion in visual CI.
- **Artifacts:** Identity v1, measured shared-state table (updates §1.13), papercut ledger.
- **Feeds:** P15 (per-identity perms), P16 (per-identity site settings), P17/18 (route bind), P20 (farbling keyed by identity+site), P21 (availability), P22/P23 (workspace binding), P27 (credential scope), P29 (vault scope), P31/32 (route templates), P34 (mixed split), P35 (promotion).

### Phase P15 — Permission Firewall v1
- **Objective:** Per-identity permission defaults + one-time grants + audit + revoke-all, over upstream PermissionManager/HCMS.
- **Why:** Upstream already mediates grants and ships one-time for cam/mic/location (Spec-C's correction of audit.txt stands); XR's delta is *scoping, expiring, auditing* — a modest, honest scope, not a re-implementation.
- **Prereq:** P6, P14.
- **Tasks:** T1 overlay store: per-identity default state per capability (cam/mic/location/notifications/clipboard-read-write/geolocation/sensors/midi/pics…, incl. Fortress deny-list) consulted *inside the resolver* (no second brain); T2 one-time grants surfaced uniformly across all prompt-capable permissions (extend upstream presentation, not plumbing); T3 expiring grants engine (once/session/7d) + background sweep; T4 permission audit log (grant/revoke/expiry rows in ledger, filterable in Panel Site-tab, per-identity); T5 revoke-all-per-identity + revoke-by-site; T6 "hidden grants" honesty: a site's permissions view shows per-identity state + global fallback, labeled (no invisible widening); T7 prompts respect Attention Budget (T3 anchors only; never stacked); T8 XR Panel permission card + settings section `xr://settings/permissions` (search-indexed).
- **Touches:** `xr/policy/` (data), `xr/permissions/`, permission prompt UI hooks (≤4 files).
- **Contracts out:** capability enum stable; audit row schema.
- **Deps in:** P6/P14. **Decisions locked:** no runtime *usage* auditing (DROP preserved — registry row keeps re-check evidence duty).
- **Security req:** overlay store integrity (corrupt ⇒ deny); prompt spoof resistance (page can't self-grant — inherits upstream, asserted in permission suite).
- **UX req:** one-time as *first* button order on sensitive caps; copy explains identity scope inline ("Only in Work").
- **Tests:** state machine (grant×scope×expiry×identity: property-based), expiry sweep under clock change, prompt ceiling, revoke propagation to live tab (no stale token grants — upstream behavior asserted).
- **Manual:** SR prompt walkthrough; Fortress identity = zero prompts? (deny means *no prompt* — verify).
- **Perf:** grant check ≤ 200 µs path.
- **Rollback:** disable overlay ⇒ upstream defaults (safe degrade).
- **DoD:** matrix green; Fortress banking-identity demo (cam/mic/location prompt-less blocked) in CI; audit rows complete.
- **Artifacts:** permission overlay v1, settings/panel surfaces.
- **Feeds:** P35 (Fortress default-deny list), P21 (Guard uses prompt ceilings).

### Phase P16 — Site protections v1 (HTTPS-First, SB local-list+OHTTP, URL honesty, upstream privacy defaults)
- **Objective:** The "don't get phished, don't be downgraded, don't be confused about where you are" layer.
- **Why:** All three specs: Safe Browsing removal is malpractice; HTTPS-First and upstream partitioning are free and must be *locked on and asserted* — plus the URL field is security UI, not chrome.
- **Prereq:** P6 (policy inputs), P10 (component channel for SB list blobs), P13 (panel integration).
- **Tasks:** T1 assert upstream defaults in CI: 3P cookie blocking phase-out policy, storage partitioning, CHIPS, referrer default (XR configures, never re-implements — inherited ruling); T2 HTTPS-First mode default-on w/ styled interstitial (opt-out per-site via exception scopes); T3 SB v5 **Local-List** integration + **OHTTP relay** config (default relay: Cloudflare-provided, user-visible & swappable — *no RRRTX proxy needed*, §0.1-R6); Real-Time mode opt-in; Enhanced **never built** (build-flag scan asserts absence); download protection hook API for P26 (hash lookup through same path); T4 URL display: eTLD+1 emphasis, path de-emphasis, never-truncates-registrable-domain, punycode/mixed-script caution chip w/ copy ("looks like `apple.com`, is `xn--pple…`"), per P4 IDN corpus; T5 interstitial policy class (T4 tier, friction attractor for proceed-anyway, permanent bypass only from Settings); T6 per-identity site-settings view in panel (exceptions scoped!); T7 help docs: what SB local list is/not, why no Enhanced (honesty pack).
- **Touches:** network service config, `xr/ui/url_field/`, interstitials.
- **Contracts out:** relay config format; URL-signal rules published to other UI (search results etc.).
- **Deps in:** P6/P10/P13 + **LG-2 verdict from P1** (ship-gate).
- **Decisions locked:** SB posture final (Local+OHTTP default; Web Risk as commercial fallback noted for enterprise plan).
- **Security req:** OHTTP privacy properties documented + verified by packet capture (Google sees relay IP only); bypass friction (typed domain) not a button; interstitial can't be framed.
- **UX req:** warning habituation budget honored (T4 ceiling ≤1/week median — measured in beta); copy: consequences not tech.
- **Tests:** phishing corpus (held-out recent sets) detection ≥ upstream Chrome parity −2%; homograph suite; HTTPS-upgrade fixtures (incl. loop guard — no upgrade storms); OHTTP config tests; per-identity scoping of exception storage.
- **Manual:** phishing-corpus day with security team; SR reads interstitials in order.
- **Perf:** URL-bar parse budget ≤ 2 ms/frame; SB list check ≤ 50 µs (hash-prefix local).
- **Rollback:** toggles per sub-feature; list channel LKG like P11.
- **DoD:** corpus parity; capture-proves privacy; interstitial ceilings instrumented; LG-2 signed.
- **Artifacts:** protections pack, OHTTP config tooling.
- **Feeds:** P26 (download reputation), P37 (onboarding explanation of what stays off), P31 (SB traffic must not bypass Tor — leak case defined now, passes in P19 suite).
## STAGE 3 — NETWORK SOVEREIGNTY & EXTENSIONS v1 (P17–P21)

### Phase P17 — Per-identity DNS & Secure DNS
- **Objective:** DNS is identity-scoped: DoH/DoT presets + custom, policy-enforced, leak-proved.
- **Why:** Cheapest deep win in the product (Spec-C verdict, all concur); also *the* prerequisite shape for proxy/Tor binding — RouteManager's first real route.
- **Prereq:** P14 (partition→NetworkContext), P9 leak harness.
- **Tasks:** T1 RouteManager binds DoH/DoT config at NetworkContext creation (per identity partition; provider presets Quad9/Cloudflare/Mozilla/AdGuard/CleanBrowsing + custom template w/ validation); T2 per-trust policy: Shield=secure-DNS-always, Standard=system (disclosed), Fortress=+`disable_host_resolver_when_proxied`-style strictness; T3 DNS cache scoping measured (what follows NetworkContext vs OS cache — update §1.13 rows with numbers); T4 UI: `xr://settings/network/dns` + Network-tab live view (resolver, per-identity, staleness per P13); T5 leak cases: system-resolver bypass attempts, IPv6 route, prefetch, DoH-down fallback policy (**fail-closed to "no DNS" vs degrade-to-system = user choice, default no-DNS under Fortress**); T6 captive-portal + `:53` reachability probes per-route policies; T7 enterprise policy hook (mandate resolver).
- **Touches:** `xr/net/`, network service config plumbing (≤5 files), settings/panel UI.
- **Contracts out:** RouteManager `BindIdentity/Status` v1 stable beyond fakes.
- **Deps in:** P14. **Decisions locked:** DNS binds at context creation (never hot-swap without tab reload — visible rule); fail-closed default policy per trust.
- **Security req:** DoH server authentication only via standard TLS (no custom pinning theater); template parser = hostile input (fuzz).
- **UX req:** one paragraph per provider ("what they see"); preset picker shows privacy posture honestly.
- **Tests:** pcap suite: no plaintext :53 egress under Shield/Fortress for {browsing, WS, WebRTC-stun-disabled path, update check, captive portal}; identity A resolver change never touches B.
- **Manual:** hotel-WiFi (DNS-poking middlebox) field day; Pi-hole-lab cross-check.
- **Perf:** resolution p50 within +15% of Chrome+DoH baseline; context creation ≤ +2 ms/identity.
- **Rollback:** resolver preset "system" one click; feature-flag off ⇒ upstream behavior.
- **DoD:** leak suite green for {Direct, DoH×4} × {Standard, Shield, Fortress}; §1.13 updated with measured cache-sharing facts.
- **Artifacts:** DNS module, field-test report.
- **Feeds:** P18 (adds proxy on same binding), P31 (Tor = another route class), P19 (suite grows).

### Phase P18 — Per-identity proxy + fail-closed routing + Network tab
- **Objective:** SOCKS5/HTTPS proxy per identity with auth, fail-closed on route loss, live Network view; exit-label ("region") as pure metadata.
- **Why:** 70% of "VPN" value without a system tunnel, root, or entitlements (Spec-A's ruling we keep; WireGuard rides this exact rail in P32).
- **Prereq:** P17.
- **Tasks:** T1 proxy config per identity (SOCKS5 + HTTP CONNECT, creds in OS keystore — never prefs), endpoint test button (measure: latency, TLS-fingerprint sanity, IP echo **only to user's own endpoint**, disclosed); T2 route-fail semantics: any error on bound context ⇒ requests fail + chip turns amber + one T3 strip ("Work's proxy is down — [retry] [switch to direct]"); no silent fallback (law); T3 Network tab v1: per-identity {route, resolver, proxy, latency, last error}, live connection list (top origins, counts only, redaction per P13), offline state card (Amendment #5); T4 "exit location" free-text label per endpoint (dropdown only when user supplies multiple; never XR-operated claims — DR-20 inherited); T5 WebRTC policy binding: `disable_non_proxied_udp` auto-on when proxied (measured + documented); T6 per-site rule hooks for Network Firewall UI later (rule storage exists, engine applies via Shield — P34 gets the authoring UI); T7 export diagnostics (redacted route config) for support.
- **Touches:** `xr/net/`, panel Network tab, keystore glue.
- **Contracts out:** RouteManager semantics frozen (Torus/WGD reuse verbatim).
- **Deps in:** P17. **Decisions locked:** fail-closed; no system proxy manipulation (Chromium may *read* it, never write).
- **Security req:** proxy credentials at-rest in keystore; endpoint test can't be page-triggered (browser-UI-origin only).
- **UX req:** config form is *boring and small*; "Proxy on" state visible in pill + status strip (auto-enabled by this phase per design system).
- **Tests:** leak matrix {proxy-down, DNS-while-proxied, WebRTC ICE, QUIC-over-proxy, large-upload stall recovery}; auth-retry loop guard; identity cross-talk (A proxied, B direct, same site → cookie jar A never reachable from B network path).
- **Manual:** Mullvad-style SOCKS + self-hosted Squid + corporate NTLM-proxy labs; captive-portal hotel rerun with proxy on.
- **Perf:** per-request route overhead ≤ 0.2 ms; fail-closed detection ≤ 2 s from first error.
- **Rollback:** disable per identity instantly; global kill in `xr://shield`.
- **DoD:** xr-leaktest proxy profile green ×3 OS; usability session (5 users configure proxy unaided) passed.
- **Artifacts:** proxy routing v1, Network tab.
- **Feeds:** P19 (full route matrix), P32 (WG plugs into same interface as endpoint provider), P31 (same).

### Phase P19 — Leak-suite v1 complete (all current routes) + published results
- **Objective:** Make "leak protection" a *CI artifact with published results*, not adjectives; close every leak class catalogued by the three specs.
- **Why:** Spec-A's core demand; also the cheapest trust asset: publish the run, not the promise.
- **Prereq:** P9 harness, P17/P18 routes (Direct/DoH/Proxy), P16 SB path.
- **Tasks:** T1 complete probe set: DNS egress (all resolvers), WebRTC ICE, QUIC/HTTP3 direct-path attempts, DNS prefetch, speculative connections, captive-portal probes, `xr://` page subresources, extension-origin requests (stub extension fixture), update+component fetches, SB OHTTP path, OCSP/CRL fetches, NTP/geo (should be *absent*), crash-upload (off by default ⇒ absent), favicon preloads, SW push registration; T2 matrix = route×trust×layout(tab/window)×{clean, crash-resume, cold-start}; T3 results publication: per-release `leak-report.json` + human summary on `xr://help/leaks` and repo transparency dir; T4 *canary discipline*: harness self-tests (loopback route must "leak" if probe lies ⇒ proves probes real); T5 policy gaps ⇒ P6 resolver fields or named drop-list with owner; T6 runbook for new features: "add leak case or file exemption with written reason" (CI-checkable registry).
- **Touches:** `xr-leaktest/`, CI infra, docs.
- **Contracts out:** leak-case registry (machine-readable, versioned).
- **Deps in:** P9/17/18. **Decisions locked:** Tor ships only when its row passes (already DR; *mechanized* here).
- **Security req:** pcap retention policy (test artifacts scrubbed, 7-day).
- **UX req:** none user-facing except help page.
- **Tests:** meta (T4); regression on every P20/21/31/32 change via required-suite label on PRs touching `xr/net|shield|extensions`.
- **Manual:** quarterly red-team: bypass hunt outside the probe set (paid-freelance or bounty-scoped).
- **Perf:** suite ≤ 45 min nightly.
- **Rollback:** n/a.
- **DoD:** green on all shipping routes ×3 OS ×2 weeks continuous; published; canary suite proves probes.
- **Artifacts:** xr-leaktest v1, first public leak report.
- **Feeds:** P20/21 (regressions block merge), P31 (gates Tor), P32 (gates WG), §17 gates.

### Phase P20 — Fingerprint reduction v1 (farbling, clamps, normalization)
- **Objective:** Brave-proven reduction: per-(identity×site) deterministic canvas/WebGL/audio farbling, API clamps, font-surface limits — with *honest* framing and zero anonymity claims.
- **Why:** Fingerprinting is the unsolved hole every security browser markets around; XR's stance (reduction+partitioning, published limits) is the differentiator *and* the truth. The plumbing is one more consumer of P12's document-start injection + P6 policy.
- **Prereq:** P12 (injection), P6 (policy fields), P14 (identity keying).
- **Tasks:** T1 noise seeds: per-origin-per-identity-per-session (deterministic within, opaque across — key derivation in C++ `xr/fingerprint/seed.cc`, constant-time, no page influence); T2 surfaces: canvas 2D/getImageData+toDataURL(+Blob), WebGL readPixels/extension list, AudioContext getChannelData/offline, `navigator.deviceMemory/hardwareConcurrency` clamp, `screen`/`window` rounding to normalizable buckets, timezone/locale under Fortress, fonts: enumeration reduction + standard list only; T3 web-exposed system-color surface (`AccentColor` family) neutralized when theme ≠ default (Spec-C §2.1 note → formalized); T4 breakage policy: farbling off *automatically* where fingerprint is security-functional (WebAuthn? — no: it's not page-observable; but *captcha-adjacent and banking device-binding* exceptions measured on corpus; per-site opt-out uses P11 exception scopes, no new mechanism); T5 `xr://help/fingerprinting` honesty pack + Isolation-Card row ("reduction, not resistance"); T6 measurement suite: Am-I-Unique/CreepJS-class fixtures as *regression baselines* (scores tracked internally; never advertised as a number in product); T7 perf mode: farbling only on first-read per surface per session (cache), budget below.
- **Touches:** `xr/fingerprint/`, Blink hooks (reuses P12 seam; budget +6 files).
- **Contracts out:** EffectivePolicy.fingerprint object frozen.
- **Deps in:** P12/14/6. **Decisions locked:** no "resistance" claims anywhere (copy gate); Fortress adds letterbox *later* (P35) on same policy field.
- **Security req:** seed derivation audited (no PII inputs: no clock ms, no entropy leaks across identities); constant-time compare to avoid cross-origin timing oracle; hooks must not weaken V8 JIT correctness (upstream fuzzer runs include XR builds — §12.4).
- **UX req:** zero chrome; one onboarding mention (teach-on-use mark).
- **Tests:** determinism matrix (same identity+site same, cross-identity different, cross-site different, session-stable); corpus render parity ≤+0.5% breakage vs no-farbling; performance fixtures (canvas-heavy: figma-class, maps, games); 10 known fingerprint *detectors* regression (improve or neutral — measured, unpublished).
- **Manual:** webgl demos + audio apps (audacity-web) + canvas editors spot check; SR unaffected (no UI).
- **Perf:** first canvas read ≤ 4 ms; steady-state ≤ 0.5 ms; memory ≤ 4 MB/context.
- **Rollback:** resolver field ⇒ off per-site/identity/global instantly; degrade-safe like P12.
- **DoD:** all budgets green in CI 14 days; no P0 breakage on corpus; help/Isolation-card copy reviewed by legal (no overclaim).
- **Artifacts:** reduction v1, measurement baselines.
- **Feeds:** P35 (letterbox), P37 (onboarding honest-limits screen), marketing site (published *after* beta data).

### Phase P21 — Extension Guard v1 + extension availability
- **Objective:** Trust-but-verify extension UX: manifest review, A–D grade, capability denials, **per-identity availability**, sideload path. (Observability lands P34 with engine hooks.)
- **Why:** Extensions are the #1 supply-chain risk users invite, and "Banking runs zero extensions" is a moat feature — the *enforcement* is the feature, not the warning.
- **Prereq:** P14 (identity scoping), P6 (policy), P11 (later egress rides it), P13 (Extensions tab host).
- **Tasks:** T1 static review engine: manifest+store-metadata parsed → permissions-as-outcomes copy (curated map, human-reviewed; **no intent statements** — banned-vocabulary list enforced by copy lint); T2 A–D grade (host-pattern breadth × capability class × update-diff history × provenance) shown pre-install + in `xr://extensions` (grade + rationale expandable); T3 default-deny `nativeMessaging`/`debugger`/broad `<all_urls>` host grants (pre-set to safer toggle — Spec-A's review-dialog posture); T4 per-identity availability: UI (checkbox grid per identity, Banking default-off for all extensions) + **enforcement: `ExtensionFunction::Dispatch` consult + content-script injection filter** (budget ≤2 upstream files, S0 dual review) + policy applied to *background* service-worker behavior (API denial before dispatch); T5 install/update review modal (T5 tier w/ friction for `<all_urls>`+password-field class), provenance line (CWS / .crx sideload / XR Verified) from Spec-A amendment; T6 sideload tooling: .crx/unpacked install path w/ signature display + XR Verified metadata client (small signed JSON catalog, not a store — DR-13 fallback kept *warm*: quarterly install drill); T7 CWS health monitor: automated install/update E2E against CWS on all channels; breakage ⇒ runbook (status page copy + curated-catalog pivot) — treat as external dependency (DR-13 registry row gets its own on-call); T8 top-100 extension compat corpus in CI (install/enable/grant/revoke/uninstall, incl. 1Password/Bitwarden/LastPass vault-extension *coexistence* with P27 — they must not fight); T9 update-permission-diff storage (P34 alerts consume).
- **Touches:** `xr/extensions/guard/`, extension service chokepoints (budgeted), `xr://extensions`.
- **Contracts out:** guard-ledger row schema; grade reproducibility (rule table versioned).
- **Deps in:** P14/6/11/13. **Decisions locked:** observation-only; no store; no MV2 (re-check per §12.6); friction for full access.
- **Security req:** dispatch chokepoint is S0: fuzzed (malformed identity ids), tested that *no* API bypasses (reflection audit — all `ExtensionFunction` subclasses funnel through; CI grep asserts); availability revocation propagates to live SW (terminate+recreate, verified).
- **UX req:** install dialog = "what this means in English" with pre-checked safer options; per-identity grid skimmable; *no* scary-by-default (Standard sites grade D only when facts warrant — grade distribution reviewed quarterly).
- **Tests:** from disallowed identity: API call denied + content script not injected + ledger row; CWS breakage drill (mock 403); sideload signature-forgery negative; 100-extension corpus ≥95% green; e2e: "disable uBlock-Lite in Banking" ⇒ its DNR rules *absent* in Banking requests (verify via P11 event log).
- **Manual:** grade spot-audit of top-100 vs human judgment (deviation log → rule tweaks); install a real uBO Lite & KeePassXC-Browser on 3 OSes.
- **Perf:** dispatch consult ≤ 3 µs; injection filter ≤ 0.1 ms/frame.
- **Rollback:** guard off ⇒ stock upstream behavior; availability enforcement degrades to "all identities enabled" loudly (amber chip, never silently).
- **DoD:** corpus + chokepoint proofs green; CWS monitor live; docs: "what Guard can and cannot see."
- **Artifacts:** Guard v1, grade ruleset v1, sideload tooling, catalog format.
- **Feeds:** P34 (egress observation+update diffs), P37 (onboarding: extensions import→review), P26? (no), P28 (nativeMessaging allowlist for external managers documented).

## STAGE 4 — DAILY-DRIVER UX (P22–P26)

### Phase P22 — Tabs v2: vertical/rail/compact + groups + search
- **Objective:** All layouts with identity/trust marks; groups that can't span identities; tab search that knows identity/workspace.
- **Why:** Chrome 146 shipped vertical tabs (verified) — layout is table stakes; the differentiator is *what the strip knows* (Spec-A framing adopted).
- **Prereq:** P7 (chrome skeleton), P14 (identity data).
- **Tasks:** T1 layout engine in views: Top (default) / Vertical (240 px) / Rail (56 px hover-expand) / Compact (40 px chrome) — *one* model, four renders (no forked logic); T2 identity marks per layout (2 px bar + glyph/text as space allows; rail = colored dot + first-letter) + trust underline + shield count chip in vertical header; T3 groups: restyled native groups, cross-identity group move blocked with explanation (uses P14 move-confirm); T4 tab search (⌘⇧A): identity/workspace/trust filters, fuzzy, ≤ 60 ms at 1k tabs; T5 hover-preview + pinned sites row in NTP (pinned *only* — no feed: DR-22 test asserts zero NTP network beyond search); T6 layout migration + per-workspace layout prefs; T7 visual CI snapshots: layout×theme×identity (60+ states).
- **Touches:** `xr/ui/tabs/`, `//chrome/browser/ui/views/tabs` (budgeted: subclass-first, patch-last).
- **Contracts out:** layout model v1; tab-search query grammar.
- **Deps in:** P7/P14. **Decisions locked:** group≠cross-identity; NTP permanent minimalism.
- **Security req:** tab previews never render vault/permission material (preview = screenshot of *rendered* page — document limitation: hold-to-reveal fields may flash in preview *of others*? previews are local-only, noted in §1.13; sensitive-identity option: "hide tab previews for this identity" — cheap toggle, ship it).
- **UX req:** layout switch ≤ 150 ms; keyboard model parity across layouts (a11y gate).
- **Tests:** 500-tab perf matrix (open/close/scroll/drag) ×4 layouts; drag-across-identity = confirm (no silent move); group ops stress.
- **Manual:** heavy-Tab-Minimalist dogfood week; SR traversal per layout.
- **Perf:** scroll 60 fps @500 tabs mid-range laptop; startup +2%.
- **Rollback:** layouts additive; default Top untouched.
- **DoD:** budgets + visual suite green; design sign-off per layout.
- **Artifacts:** tab system v2.
- **Feeds:** P23 (workspaces live in side layout), P34 (mixed split reuses), onboarding (vertical-tabs teach-on-use mark — first prompt *after* tab overload, never onboarding itself).

### Phase P23 — Workspaces v1 + session save/restore
- **Objective:** Named tab sets + window layouts, optional default-identity binding; honest session store; crash recovery as card.
- **Why:** "Workspaces organize tabs; identities separate logins" needs the second half or the four-word rule is a lie; session restore is where per-identity assumptions (spec-acknowledged "papercuts") actually surface.
- **Prereq:** P14, P22.
- **Tasks:** T1 workspace store (tabs, windows, layout, optional default identity, trust per-tab snapshot) in XR session store (SQLite, versioned); T2 switcher (sidebar chip row — hidden until a 2nd workspace exists (amendment preserved); ⌘⇧W; palette view); T3 save/restore with identity re-binding + ephemeral never restored (law: ephemeral can't survive crash — assert); T4 crash-recovery card (T2 toast-anchored, never modal) with per-identity summary ("Work had 12 tabs"); T5 workspace export bundle (encrypted, w/ identity refs — pairs with P30 backup format); T6 auto-archive (close ⇒ snapshot; reopen from history panel); T7 startup policy: last / pinned-workspace / choose-per-identity (per-OS login semantics documented).
- **Touches:** `xr/ui/workspaces/`, session service seams (budget ~6 files).
- **Contracts out:** session-bundle format v1 (stable across upgrades — tested in §11.11).
- **Deps in:** P22. **Decisions locked:** workspaces enforce nothing (registry); hidden-until-second.
- **Security req:** bundles encrypted at rest (keystore-wrapped); restore never widens a permission's scope (grant state comes from ledger, not bundle).
- **UX req:** zero-cost default: one invisible unnamed workspace until user creates a second (design-system rule); switching ≤ 200 ms perceived.
- **Tests:** kill-matrix (each process type, mid-save): restore integrity; 50-workspace × 40-tab memory ceiling w/ hibernation interplay (P14); cross-version bundle fixtures (P31-era reads P23-era — forward-compat tests live in §11.11).
- **Manual:** multi-monitor + Spaces (macOS)/Task View (Win) edge pass.
- **Perf:** switch ≤ 250 ms ≤20-tab.
- **Rollback:** disable ⇒ tabs only (stores remain valid).
- **DoD:** matrix + kill-tests green; hidden-until-used assertion; SR naming pass.
- **Artifacts:** workspaces v1, session format.
- **Feeds:** P34 split (splits are workspace state), P37 (import maps browser sessions here).

### Phase P24 — Universal Search v1 (engines, bangs, research providers)
- **Objective:** Search as a first-class, identity-aware, zero-surveillance surface.
- **Why:** Daily-driver lock-in; the revenue honesty (switchable default, no deals — Spec-A's noted tradeoff accepted once); research bangs cost nothing after this.
- **Prereq:** P7 (palette adjacency), P8 (settings).
- **Tasks:** T1 engine manager over TemplateURLService: curated starter set (DDG default, Startpage, Brave Search, Wikipedia, Qwant, Mojeek + regional), add custom from any site (right-click "Add as search engine" via OpenSearch + manual template), per-identity default engine + engine memory per site? (no — per identity only, simple); T2 bang syntax `!g maps !arxiv q` (bang table file, XR-owned; DDG's *list* not copied — syntax lineage noted), bang CRUD + import/export; T3 results UX: address-bar engine switcher strip, search-in-new-identity; T4 privacy defaults: no search-prefetch/async suggestions **on by default** (opt-in per engine w/ disclosure of what's sent), no keylog of queries anywhere; T5 research provider presets (arXiv, Semantic Scholar, PubMed, Google Scholar excluded-on-principle? no—include as bang, disclose; GitHub, man7, MDN, RFC-editor); T6 enterprise: forced default engine policy; T7 first-run: default engine chooser shown once (no silent DDG).
- **Touches:** `xr/tools/search/`, omnibox provider (≤3 files).
- **Contracts out:** bang-table format; suggestions-policy flags.
- **Deps in:** P7/8. **Decisions locked:** default DDG (privacy-respecting) + explicit chooser; "Research Mode" stays DROP (this is it + templates).
- **Security req:** template injection checks (`{searchTerms}` expansion sanitized — fuzz); suggestions TLS+identity-scope asserts.
- **UX req:** bang hints in palette when typing site-name (teach-on-use, once).
- **Tests:** conformance corpus (50 engines CRUD + 300 bang fixtures); suggestion opt-in/off capture diffs (nothing sent when off — P9 pcap); omnibox provider ordering edge (file://, IP-literals, punycode — interacts P16).
- **Manual:** power-user week as sole search surface (team), typo-tolerance review.
- **Perf:** bang resolve ≤ 1 ms; engine switch ≤ 1 frame.
- **Rollback:** trivial (upstream defaults remain).
- **DoD:** all tests green; no-egress proof for suggestions-off.
- **Artifacts:** search v1, bang table v1 (public, editable).
- **Feeds:** P25 (reading list/search integration), P37 (onboarding engine step), P21? (no).

### Phase P25 — Knowledge tools v1: bookmarks, notes, highlights, reading list, reader, screenshots (visible+full page)
- **Objective:** The "keeps daily users" cluster, per-identity scoped, local-first, exportable.
- **Why:** Individually trivial, collectively the difference between a security tool and a browser you *live in*; all three specs concur; ledger-backed so identity scoping is free.
- **Prereq:** P13 (ledger), P14 (scoping), P8 (theming for reader).
- **Tasks:** T1 bookmarks: upstream store + identity tags in ledger; smart folder "Unsorted" + move-with-scope-change confirm; import (P37 heavy here); T2 notes: SQLite per-identity (page-scoped auto-title+URL bind, workspace-scoped), Markdown, export-all (folder of .md), full-text search in palette; T3 highlights: text-fragment `#:~:text=` anchors + provenance record (quote, title, ts); honest failure: fragment-miss ⇒ "couldn't re-find highlight" state (never silent); T4 reading list: upstream + identity tags + mark-done + note link; T5 Reader: extend upstream Reading Mode (typography/width/line-height/theme, save-to-list, font family incl. Inter; never distiller *fork*); T6 screenshots v1: visible-tab capture (CopyFromSurface), full-page (capture-beyond-viewport via compositor path, scroll-stitch fallback w/ "may capture ads" honesty note on long SPA), save/copy/annotate-later(P26 region)/copy-path; privacy note (captures include *what's on screen* — vault holds reveal state excluded: capture while vault field focused → redaction overlay? simpler: **block capture entirely during hold-to-reveal**, documented); T7 everything exports: `xr://export` JSON/Markdown bundle per identity (users can leave — interop principle).
- **Touches:** `xr/tools/`, bookmarks/history glue, reading-mode component usage.
- **Contracts out:** ledger tables (notes/highlights/bookmark-tags) v1.
- **Deps in:** P13/14. **Decisions locked:** Pins-as-highlights (no bespoke anchoring research); reader = extend, not rebuild.
- **Security req:** fragment parser = hostile (fuzz); full-page capture bounds (memory ≤ 2× viewport pages, cap 20k px default, user-adjust).
- **UX req:** zero new chrome — all via palette/panel/context-menu; note auto-save (500 ms debounce) with visible micro-state.
- **Tests:** round-trip export/import; 200-page reader corpus render quality rubric (scored); fragment-anchor success rate tracked on corpus (≥85% same-session, honest degradation measured); capture memory ceilings; SR labels for all.
- **Manual:** writers'-room session (notes+reader+highlights, 3 users); screenshots on hidpi/dark-mode.
- **Perf:** reader open ≤ 400 ms p95; screenshot ≤ 250 ms visible; palette search ≤ 60 ms @10k items.
- **Rollback:** per-tool flags; data survives (ledger versioned).
- **DoD:** suites green; export verifiable on clean install.
- **Artifacts:** knowledge tools v1; export format.
- **Feeds:** P26 (downloads panel joins), P37 (import), P30 (note/vault link later? no — vault never stores notes; secure notes live IN vault, P30; keep boundary crisp).

### Phase P26 — Downloads: manager v1 + security pipeline + xr-inspect + direct-media affordance
- **Objective:** Downloads that *protect*: pipeline, quarantine, verdicts, hashes, VT-by-link, sandboxed inspection, honest media affordance.
- **Why:** S12 of all three specs; the sandboxed-inspector decision (never parse hostile archives in-browser) is cheap and load-bearing; media affordance closes the "downloader" argument by shipping the defensible 80%.
- **Prereq:** P10 (component channel for blocklists? none — verdicts are local + P16 SB hook), P13 (Downloads tab), P25 (screenshot overlap none).
- **Tasks:** T1 manager UI: queue, speed, pause/resume, per-identity tag/filter, "show in folder" OS-native, retention policy; T2 pipeline hooks: filename safety (path traversal, reserved names per OS), magic/MIME/extension mismatch matrix, dangerous-type table (per-OS: .exe/.msi/.bat/.command/.desktop/…), SB download protection via P16 hash path; T3 quarantine-until-acknowledged (file parked in `~/Downloads/.xr-quarantine` w/ copy-to-Downloads gesture; MoTW on Windows via zone.identifier, mac xattr quarantine), code-signature *display* (Authenticode publisher, Apple notarization status — verify chain, never assert safety); T4 hash display (SHA-256/1/MD5 shown, copy) + "check on VirusTotal" = **opens vt hash URL, never uploads** (law); T5 `xr-inspect` process: archive listing (zip/tar/7z/rar via Rust crates — pinned+vetted), zip-bomb limits (ratio+ceiling), executable metadata (PE/Mach-O/ELF parse) — sandboxed (no fs except temp file), verdict struct only; archive-peek *inside* quarantined file's context menu; T6 direct-media affordance: on `<video>/<audio>` with direct `src` or plain (unencrypted) HLS/DASH manifest w/o DRM signals (no Widevine license path) ⇒ "Save media" in media context menu; manifest resolver rejects anything touching CDM/EME (lint + unit test: "if EME involved, affordance absent"); T7 legal-review row per media host-class? no — blanket: we detect *protectability*, not permission (posture documented in help: users own their compliance — mirrors yt-dlp CLI norms while we ship no circumvention); T8 crash-safe resume (partial files + hash continue).
- **Touches:** `xr/downloads/`, `xr-inspect/` (new Rust crate), download-core seams (≤6 files).
- **Contracts out:** DownloadSafety mojom (real, not fake) + verdict schema; quarantine dir contract.
- **Deps in:** P10/13/16/25. **Decisions locked:** no AV engine; VT-link-only; sandboxed inspection or not at all; no DRM.
- **Security req:** xr-inspect = untrusted-input parser → fuzz from first commit, 72h clean before beta; path-traversal suite; SB proxy (OHTTP) for hash lookups (no direct phone-home, packet-asserted in P19 suite).
- **UX req:** verdicts = facts + actions ("Unsigned .dmg from example.org — [Keep (move out of quarantine)] [Move to Trash]"), no red fear-mongering (Attention T3 only; permanent block = Settings).
- **Tests:** verdict fixtures (500 samples: mismatch/malformed/oversize/signature states), quarantine E2E ×3 OS (Windows MoTW propagation to Explorer, macOS Gatekeeper coexistence not broken), resume-under-kill matrix, affordance correctness corpus (protected streams never offered), zip-bomb ceilings.
- **Manual:** AV-lab cross-check of *verdict consistency* (VirusTotal referenced, not embedded); large-file (10 GB) + flaky-network day; media sites day (Archive.org direct files — legal-safe test targets).
- **Perf:** sniff ≤ 30 ms/file (bounded read), peek ≤ 500 ms/10k-entry archive; no main-thread > 16 ms (assert).
- **Rollback:** inspect off ⇒ heuristics only (still useful).
- **DoD:** suites green; fuzz clean; affordance lint passes; quarantine drill in CI.
- **Artifacts:** downloads v1, xr-inspect v1, media affordance.
- **Feeds:** P37 (onboarding explains quarantine honestly), P38 (docs).

## STAGE 5 — VAULT (P27–P30)

### Phase P27 — Credential hardening v1 (launch-grade passwords)
- **Objective:** Users never credential-less: upstream password manager made safe (keystore, scope, no sync) + generators + external-manager coexistence, while `xr-vaultd` is built.
- **Why:** All three specs' bridge decision; also the *autofill mediation* machinery is the hard part shared with P29 — build the mediation layer once, against the frozen `VaultService` fake first, real later (contract-first payoff).
- **Prereq:** P14 (scope), P6 (policy), P5 (vault contract + fake).
- **Tasks:** T1 per-identity credential scope: index `(origin, identity) → visible` atop LoginDatabase (XR-side table; upstream untouched); T2 OS-keystore wrap: DPAPI/Keychain/Secret Service·KWallet + **documented password-only fallback on broken Linux keystores** (no silent downgrade — explicit choice screen); T3 autofill mediation layer: origin binding, eTLD+1 exact + IDN check, iframe policy (top-frame or same-origin child; sandboxed/opaque blocked), redress/focus rules, visible cross-origin mismatch chip (impostor shown side-by-side), cross-identity explanation row ("3 logins hidden — Personal"); T4 re-auth gates: sensitive-origin list (per-identity config) + before-copy; T5 password generator v1 (length/charset/diceware modes, strength meter honest — entropy bits, not gamification); T6 import: browsers + **KDBX + CSV** (parse in vault-side code from day one → same parser P28 reuses; loss reports); T7 export w/ confirm (encrypted bundle, passphrase-protected); T8 external managers coexist (nativeMessaging allowlist documented; conflict guards — e.g. 1Password's own fill must not double-trigger); T9 platform passkeys pass-through QA: WebAuthn platform/hybrid/security-key matrix untouched-but-tested per OS; T10 help: "your passwords live in this profile, wrapped by your OS key; RRRTX has no copy; P30 adds your own storage sync."
- **Touches:** `xr/vault/client/` (against fake now, real at P29), autofill/credentials seams (≤10 files).
- **Contracts out:** mediation decisions are `VaultService` semantics — *frozen surface exercised for real*.
- **Deps in:** P14. **Decisions locked:** no browser-resident software passkeys (ever without hardware binding); cards NOT here (registry row, P39).
- **Security req:** full autofill attack suite (see P29 list) runs against mediation layer *now*; keystore failures never fall back to plaintext (fail = refuse+explain).
- **UX req:** inline dropdown fill, never modal; hold-to-reveal + 45 s clipboard auto-clear with countdown ring (the ring is the point — user sees safety working); lock at start = off-by-default? **on**: locked-vault-at-browser-start default with per-identity "unlock with biometric" where OS supports.
- **Tests:** cross-origin/homograph/about:blank/iframe fill negatives; scope leakage; generator entropy vectors; import lossless matrices; crash during write (DB journal asserts).
- **Manual:** 3-OS keystore matrix incl. locked-Linux (no daemon) degrade; SR pass on fill dropdown (this is a security flow — labels mandatory).
- **Perf:** suggestion lookup ≤ 10 ms @5k items; clipboard clear timing ±50 ms.
- **Rollback:** mediation off ⇒ upstream autofill behavior, loudly (amber chip "identity-scoped protection OFF") — never silently weakened.
- **DoD:** suites green on 3 OS; external-manager coexistence certified; help copy legal-reviewed.
- **Artifacts:** credentials v1, import tooling, mediation lib (shared with P29).
- **Feeds:** P29 (swap fake→real vaultd), P30, P33.

### Phase P28 — xr-vaultd: KDBX engine in a sandbox
- **Objective:** The vault's core as its own audited-by-design component: process, crypto, KDBX-4.1 reader+**XR-written writer**, TOTP, memory hygiene — fuzzed, bench'd, design-reviewed, *then* audit engagement starts.
- **Why:** Existential-risk subsystem (all three specs agree); Spec-A/B/C under-specified the *write-loss* danger — verified keepass-rs write path is experimental/lossy for unknown fields (R10), so XR owns the writer and proves fidelity on corpus.
- **Prereq:** P5 contract, P9 fuzz fleet; independent of Stages 2–4 (Rust crate can progress in parallel from P5 — parallelization plan exploits this).
- **Tasks:** T1 crate `xr-vaultd` (Rust): KDBX-4.1 read via vendored keepass 0.13.x + own **loss-preserving writer** (round-trip: unknown XML nodes, custom fields, attachments, history, meta, icons preserved — design: read into DOM-ish tree + targeted mutation, not model-rebuild); T2 golden corpus: files generated by KeePass 2.5x/2.57, KeePassXC 1.8x/2.x, strongbox, mini (120+ files × mutations) → byte-fidelity + logical-parity assertions (writer never silently drops — fuzz-corpus differential vs KeePassXC CLI); T3 crypto posture: Argon2id (params: mem ≥ 64 MiB default, calibrated slider), AES-256-GCM + ChaCha20-Poly1305 + KDF variants per KDBX; HMAC block protection; primitives only from libsodium/RustCrypto-audited crates; **no custom primitives (law; dep-graph lint)**; T4 process posture: sandbox (linux seccomp: openat only within vault dir + read-only libs; mac seatbelt profile; win: restricted token + no-win32k), mlock best-effort + `zeroize` on lock/drop (property-tested), no logging of contents (log-lint: `tracing` subscriber strips payloads; test asserts); T5 Mojo glue: implements frozen `VaultService` (unlock/list-for-origin/get-field/totp/lock/change-master…), per-request item-scoped grants with TTLs, deny-unknown; T6 TOTP RFC 6238 w/ drift window + vectors; T7 file-level crypto self-tests (KATs) + corruption/wrong-password semantics: *never* overwrite damaged DB, `.recover` copies; T8 bench: unlock ≤ 350 ms @default params (8 GB laptop), search ≤ 15 ms @10k items, DB open stream-parallel; T9 fuzz: format (input corpus + grammar seeds), IPC (P9 Mojo harness), 7-day campaigns CI-resident; T10 design-review packet for external auditor (threat model + API + memory doc + FFI surface) + RFP out (engage by P29 mid); T11 threat-model doc for the *sync/pairing* key ceremony (consumed by P30 — designed early because it constrains formats).
- **Touches:** `xr-vaultd/` (own repo → vendored), mojom impl. **Contracts out:** KDBX fidelity matrix (regression asset), vaultd sandbox policies.
- **Deps in:** P5/P9. **Decisions locked:** XR-owned writer (R10); zero custom crypto; no-network capability until P30 (then user-endpoint-only), sealed by policy not trust.
- **Security req:** dual S0 review of process+policy; supply-chain: crates vendored + `cargo vet` audited-diff policy (upstream advisory review within 72 h).
- **UX req:** none (headless) — but *latency budgets are UX*: P29 enforces.
- **Tests:** everything above incl. 10⁹+1 fuzz execs per week; downgrade tests (vaultd killed mid-op ⇒ no corruption visible to UI).
- **Manual:** none until P29 integration. **Perf:** budgets T8.
- **Rollback:** format versioned in KDBX meta; vaultd version-negotiates with client (min/max); no silent migration.
- **DoD:** corpus byte-fidelity 100%; fuzz clean 14 days; KAT+perf green; **auditor engaged, contract signed** (audit executes during P29–P30).
- **Artifacts:** vaultd v0.9, fidelity suite, sandbox policies, design-review packet.
- **Feeds:** P29 (real), P30 (sync uses same engine), P33 (passkey bridge interface stub reserved in IDL — *implement nothing* yet).

### Phase P29 — Vault UX + autofill integration + audit remediation
- **Objective:** `xr://vault` as a real manager you'd keep open all day; mediation wired to vaultd; external audit closes the gate.
- **Why:** The moat's credential half becomes *usable*; audit-gate (DR-11) sits between "stores toy passwords" and "stores your life."
- **Prereq:** P28, P27 (mediation), P8 (theming).
- **Tasks:** T1 vault UI: three-column (collections/rows/detail), search (fuzzy, ≤ 10 ms), per-item scope editor (identities), copy-with-countdown, hold-to-reveal, lock-state = full replacement (no blurred preview — leak of item count/favicon is the point), idle auto-lock (configurable 1–30 min), biometric-unlock via platform where safe (never stores a weaker unlock path than the master password); T2 autofill wiring: fake→real swap, TOTP suggestion in code fields (fill TOTP only when field is focused+origin-matched), credential create/capture prompts (T3, one per site per identity, "Save for Work?" + scope preview); T3 secure-notes type (T28 storage exists; UI now); T4 batch ops (move between collections, tag, bulk export *of scope-selected* items w/ confirm); T5 audit response loop: auditor findings triaged, highs/criticals fixed *in this phase's window*, re-test report attached; T6 recovery ceremony UX (kit generation/print, w/ mandatory acknowledgment reading — friction *on purpose*); T7 performance on low-end (8 GB RAM, HDD): budgets re-verified; T8 crash/lock races: vaultd kill ⇒ UI shows "Vault unavailable — [retry] [continue locked]" (fail-safe law #14), zero plaintext leaks on restart (memory-inspection test); T9 help + threat-model page for Vault ("we cannot help you"; "sync never stores plaintext"; audit summary embedded w/ date+firm).
- **Touches:** `xr/ui/vault/`, `xr/vault/client`, mediation.
- **Contracts out:** UI-driven scope editor semantics stable for P30/33.
- **Deps in:** P28. **Decisions locked:** audit-gate mechanics (release tooling blocks stable builds where `vault_stores_real_credentials=true` without audit-token artifact).
- **Security req:** SR labels on all reveal/copy controls (security flows must be screen-reader complete — §11.6 gate); paste-behavior: never into password fields from other apps while locked.
- **UX req:** feel = native app (virtualized lists, optimistic UI around IPC latency ≤ 50 ms p95 target).
- **Tests:** full autofill suite (cross-origin, iframe ×3 classes, clickjacking, redress, homograph, `about:blank`, download-page spoof), capture-prompt frequency (Attention ceiling), lock-race stress, audit-fixture corpus re-run (nothing regressed post-UI).
- **Manual:** audit report published (firm + scope + date in §17 docs); 12-user "move from LastPass" study (import→fill→share-nothing flows timed).
- **Perf:** list open ≤ 250 ms cold; fill menu ≤ 80 ms.
- **Rollback:** client can drop to P27 store (data preserved; vaultd file remains valid for KeePassXC).
- **DoD:** **audit-closure artifact filed; KDBX interop verified with current KeePassXC release; suites green.**
- **Artifacts:** Vault 1.0 (audit-cleared), published audit, help pack.
- **Feeds:** P30 (sync/recovery already designed — now deployed), P33 (passkeys bridge), §17 stable gate.

### Phase P30 — Vault sync, BYOK & backup + custom themes + settings v1 completion
- **Objective:** Multi-device without a service: BYO-storage E2EE sync; recovery kit live; backup bundles for everything; custom theme framework GA (declarative); settings IA complete.
- **Why:** Sync is the only *new* crypto ceremony left (designed in P28-T11 — now implemented); backups round out "users can leave, never lose"; Spec-A's themes amendment (4+2 now, framework+gallery later) completes here as *framework*, gallery stays community-post-GA.
- **Prereq:** P29 (vault stable), P23 (session bundles), P8 (theme tokens).
- **Tasks:** T1 sync format: manifest-of-blobs per KDBX file (versioned, content-addressed), client-side E2EE envelope (per-vault key + per-device key wraps, X25519+ChaCha via age-style crate — audited libraries only), conflict = per-entry merge UI (never last-writer-wins on secrets — diff view w/ both values masked until revealed); T2 backends: WebDAV + S3-compatible (test-button, path safety, no telemetry about endpoints); local-folder sync = free win; T3 pairing ceremony: 6-digit short code (time-boxed, one-device-approves), revoke-device flow (key rotation with re-wrap, offline-tolerant); T4 recovery kit generation/print (seed + master-password instructions + "test your kit" flow); T5 backup bundles (profile: identities + settings + notes/highlights + vault file, encrypted, integrity manifest, restore-on-clean-machine drill); T6 custom-theme framework: token JSON schema v1 (public), import w/ validator+contrast-refusal (already), per-identity theme assignment, theme docs page; T7 settings IA completion (all sections incl. vault/network/guard; deep-links final; enterprise policy surfacing); T8 sync *stress*: 2 devices × airplane-mode chaos × 48 h mutation fuzz (lossless property test).
- **Touches:** `xr/vault/sync/` (within vaultd), `xr/ui/settings`, backup tooling.
- **Contracts out:** sync blob format v1 (spec published — interop-friendly), bundle format.
- **Deps in:** P29. **Decisions locked:** one backend abstraction; no RRRTX storage (DR-10); conflict policy "human merge" (never silent).
- **Security req:** pairing = S0: replay/MITM tests, code entropy, rate-limit; sync path re-enters **audit addendum scope** (auditor reviews ceremony before GA — contract covers it).
- **UX req:** every failure explainable ("webdav 409 on blob 7" surfaced w/ retry, not spinner-trust); sync-state in vault titlebar dot w/ hover last-sync.
- **Tests:** lossless property suite, backend matrix (5 servers incl. self-hosted MinIO/Nextcloud), pairing ceremony fuzz, contrast-validator (theme fuzzer), bundle version-forward matrix (P9 §11.11 harness).
- **Manual:** 2-device real-life week (laptop+desktop), recovery-kit drill by 6 naive users (must succeed unaided), corporate-WebDAV day.
- **Perf:** sync convergence ≤ 3 s typical; pairing ≤ 60 s E2E.
- **Rollback:** per-device sync disable (file remains authoritative local), conflicts never destructive.
- **DoD:** ceremony audit-signed; matrix green; drill passed; docs published.
- **Artifacts:** sync v1, recovery/backup program, theme framework, settings v1.
- **Feeds:** P33 (device keys reuse ceremony), P37 (onboarding: "import + optionally pair"), P39 (gallery uses framework).
## STAGE 6 — THE ADVANCED TIER (P31–P35)

### Phase P31 — Tor identity (`xr-tord`): engine, isolation, disclosure
- **Objective:** Tor *networking* as an identity class, gated entirely behind the leak suite; `.onion` reachable there and only there; honest failure states.
- **Why:** Restored against Spec-PDF (all three reconcile at "build it, defer it, gate it on evidence"). Arti 2.6.0 verification (R3) flips engine default; C-tor fallback keeps anti-censorship completeness in reach.
- **Prereq:** P18/19 (routes+leak suite), P14 (identity templates exist), P5 (`RouteManager` frozen since P5 — tord implements it).
- **Tasks:** T1 `xr-tord` daemon: default engine = Arti embedded as a library inside the helper process (its native RPC gives bootstrap events + config without any control-port parsing); fallback engine = upstream C-tor spawned with a generated torrc + cookie-auth control port (minimal client written in Rust, fuzzed hard from commit one — the parser cost is precisely why Arti is default); engine selectable per identity with restart, both shipped, both leak-gated; T2 bootstrap state machine surfaced in UI (Connecting x% · Bootstrapped · **Failed w/ recovery card: Retry / Bridges / Diagnostics** — the anti-Brave lesson, Spec-A amendment #2); T3 `RouteManager` binding: SOCKS5 endpoint w/ **stream isolation per first-party** (SOCKS username/password scheme per Whonix-documented pattern; isolate creds derived from (identity, eTLD+1, session)); T4 `.onion` policy: non-Tor contexts hard-fail (resolver-level, P19 case exists); Tor context: DNS *only* via tunnel; T5 policy bundle: WebRTC off, no QUIC, no prefetch, captive-portal off, update-checks **paused w/ visible notice** ("XR does not call home on this route"; update while non-Tor window open), extensions default-off (template), SB checks via OHTTP *through Tor* or off (choice disclosed), NTP absent, font/locale normalization auto-on (Tor template inherits Fortress-ish posture); T6 circuit UX: circuits list (identity-scoped), "New circuit for this site"; T7 bridges UX: pluggable transports minimal set (obfs4; Snowflake **only when C-tor engine selected** — honest matrix in UI); T8 first-run disclosure: non-dismissible T5, scroll-to-end (Spec-A §5.5 approved copy verbatim), recorded acceptance (local only); T9 leak profile "tor" added to xr-leaktest = ship-gate; T10 engine update channel (component: pinned Arti/C-tor builds, kill switch per-version); T11 handoff fallback path (P19-era affordance): "Open in Tor Browser" remains for anonymity-grade needs, promoted *from* disclosure copy.
- **Touches:** `xr-tord/` (own repo), `xr/net/` (route provider), Tor UI (panel Network + modal).
- **Contracts out:** tord IPC v1 (engine-swap stable); leak "tor" profile.
- **Deps in:** P19. **Decisions locked:** DR-09/DR-20 (networking ≠ anonymity; no system tunnel); Arti default w/ measured fallback.
- **Security req:** tord sandbox: net-only-egress, no fs (config in-memory), seccomp; IPC fuzz; bootstrap config never contains user identifiers; clocks/entropy notes in threat model.
- **UX req:** all states in §10 map; violet border (identity); *never* auto-enter; entry only via pill/palette/new-window.
- **Tests:** leak profile green ×3 OS incl. crash-resume (tord dies mid-session ⇒ tab errors, no direct fallback — law #14); circuit churn; bridge modes; `.onion` matrix; isolation property test (two sites in one identity ⇒ separate circuits, two tabs same site ⇒ same).
- **Manual:** censored-network simulation lab (TLS- MITM box, DNS poisoning) + real-world field test week (team on hotel/conference WiFi); disclosure-modal readability on 6 users.
- **Perf:** bootstrap p50 ≤ 8 s fresh / ≤ 2.5 s warm; throughput floor measured & published honestly (no "fast Tor" claims).
- **Rollback:** disable Tor template (identities migrate to Disposable w/ warning); engine flip Arti↔Ctor is a setting, each fully tested.
- **DoD:** **leak suite green is the gate — no flags, no beta escape hatch** (Spec-A rule adopted); disclosure reviewed by external Tor-adjacent reviewer; docs final.
- **Artifacts:** Tor identity 1.0, xr-tord v1, published leak profile, field-test report.
- **Feeds:** P35 (Fortress partition parity for Tor rows), P37 (never in onboarding), §17 (RC gate).

### Phase P32 — WireGuard route (`xr-wgd`) + exit labels
- **Objective:** User-config WireGuard as a first-class per-identity route via local SOCKS5 — no TUN, no root, no entitlements, permanently.
- **Why:** R4 ruling (wireguard-go over unstable boringtun) + Spec-A's restored architecture, which is *simpler* forever than system-tunnel code on any OS.
- **Prereq:** P18 (route binding machinery).
- **Tasks:** T1 `xr-wgd` (Go, wireguard-go): config import (wg `conf` file parse w/ key validation + endpoint reachability test), local SOCKS5 listener, UDP-framed-through-tcp? **no** — plain UDP to endpoint; DTLS-free design, MTU auto (1280), keepalive; T2 key lifecycle: generate/rotate ceremony (keys never in prefs — keystore; export requires re-auth), peer allowed-IP semantics *ignored except endpoint/auth* (we're a client — documented); T3 route binding: `RouteManager` provider = local SOCKS endpoint (identity-scoped like proxy); fail-closed identical to proxy (kill behavior: identity traffic stops, never system-wide anything); T4 exit-label dropdown (free text/emoji per endpoint — "region" word *banned* from XR-authored strings unless user-supplied); T5 connection health UI in Network tab (handshake age, latency, transfer counters *aggregated only*); T6 leak cases added: proxy-down race, route-mixed (one identity WG, one direct — no cross-bleed), IPv6 policy (disable-if-not-tunneled), DNS over WG path (system DNS never used); T7 perf: userspace tunnel throughput floor (≥ 300 Mbps modern CPU wireguard-go userspace, target; published measured); T8 packaging: wgd binary signed+updated on component channel; sandbox posture = same as tord.
- **Touches:** `xr-wgd/`, `xr/net/`, settings UI (proxy-family).
- **Contracts out:** conf-format subset + versioned config envelope.
- **Deps in:** P18. **Decisions locked:** R4; never-a-system-tunnel (law).
- **Security req:** conf parser fuzz (72h), key material zeroize-on-lock, no log of endpoints at info level (privacy of config).
- **UX req:** "Paste a WireGuard config" — one screen; nothing else.
- **Tests:** fail-closed matrix (endpoint unreachable, half-open, NAT rebind), leak profile "wg", mixed-route identity cross-talk, key-rotation live (rebind w/o losing session more than reconnect), 48 h soak (no fd/mem growth).
- **Manual:** Mullvad/Proton/WireProxy self-host configs day; CGNAT environment capture.
- **Rollback:** disable route ⇒ direct (warned) or proxy (chain preserved).
- **DoD:** wg profile green; throughput floor met on reference HW (published).
- **Artifacts:** wgd v1, config UX, perf report.
- **Feeds:** P34's Network tab polish; VPN-adjacent support docs.

### Phase P33 — Passkeys: XR-resident, hardware-bound authenticator
- **Objective:** The vault *can be* a passkey provider — only when backed by TPM/Secure Enclave/Hello; platform pass-through (P27) remains the default path.
- **Why:** Registry row honored with its hard condition (Spec-A F41, Spec-C D8): software-only browser-resident passkeys are a downgrade — so we build the *hardware-anchored* version, late, gated, or not at all if platform constraints refuse.
- **Prereq:** P29 (audit-cleared vault), P30 (device key ceremony reused).
- **Tasks:** T1 capability spike per OS (Chrome already supports "cross-platform authenticators"; the open design question is hosting a **CTAP2 authenticator surface** bound to the platform's signing hardware, discoverable to RP flows): TPM2 (Win/Linux via tss2), Secure Enclave (macOS `LocalAuthentication` + `CryptoKit`), Hello (Windows platform key w/ UV); T2 architecture: *separate process path* — `xr-vaultd` never touches the hardware key (it gets only a wrapped handle); authenticator logic in `xr-authd` (new tiny helper, same sandbox posture), resident-key store = per-identity scoped in vault metadata (RP ID, user handle binding, counters monotonic w/ crash-safe storage); T3 flows: create/assert (user-verification via platform biometric/PIN), discoverable-credential list UX in vault UI, per-identity gating (a Banking identity's keys never assert on Personal RP sites — same origin+identity rule as passwords, enforced at authd consult); T4 attestation/MDs: "XR authenticator (software-verified, hardware-rooted)" AAGUID + metadata statement published (conformance with FIDO2 CTAP2.1 + W3C level 3 — test with FIDO alliance conformance tools + WebAuthn conformance suite); T5 backup-eligibility handling: passkeys *synced by us?* **no** — export via user storage = wrapped by device keys, ceremony designed (audit addendum); T6 fallback honesty: any platform where hardware binding can't be *proven* (e.g., Linux w/o TPM): feature hidden, doc explains; T7 security-key (external) flows regression-tested w/ identity scope; T8 docs + disclosure: "hardware-backed; losing this device without a backup means losing this key — print the kit".
- **Touches:** `xr-authd/`, vault metadata, WebAuthn glue (≤4 files, hooks not surgery).
- **Contracts out:** `authd` IPC; credential envelope format.
- **Deps in:** P29/30. **Decisions locked:** hardware-bound-only; RP-side nothing exotic (no fake attestation, no tracking additions — privacy note in metadata).
- **Security req:** full CTAP fuzz surface review; UV bypass matrix (page can't forge presence); re-enrollment ceremony revokes device keys via P30 rotation.
- **UX req:** sheet flow matches platform expectations (users already trained by OS passkeys — *deviating is a security bug*: consistency mandate).
- **Tests:** FIDO conformance subset (documented pass-list), WebAuthn level-3 WPT parity (no regression for platform path), 50-RP real-world matrix (Google/GitHub/Apple/Microsoft/Okta/auth0/keycloak), counter persistence under kill-9, per-identity scope negatives.
- **Manual:** TPM-less Linux *refuses* (assert); enroll→revoke→re-enroll on 3 OSes; passkey-only account day (team lives on XR passkeys 1 week).
- **Perf:** assert p95 ≤ 400 ms (UV included).
- **Rollback:** hide flag; platform pass-through unaffected; created keys remain usable via export ceremony (no lock-in — spec-law of the product).
- **DoD:** conformance artifacts + audit addendum for the new process; per-OS capability table in docs (shipped/hidden honestly).
- **Artifacts:** authd v1, metadata statement, conformance pack.
- **Feeds:** P37 onboarding optional mention (only if user imported passkey-using providers), P38.

### Phase P34 — Mixed split, Focus/Compact/sidebar, Network Firewall UI, extension egress, translation, DevTools panel, perf tools
- **Objective:** The last big interaction surface (split with mixed identities — the highest-risk UI per Spec-A amendment #3) + consolidation features that *view* existing engines instead of new ones.
- **Why:** These items are UI/views over machinery already frozen; sequencing them here (not earlier) keeps the patch budget concentrated, and the usability gate on mixed split needs identity maturity (P14+) first.
- **Prereq:** P11 (egress/filters), P13/14/18/21/22/23.
- **Tasks:** T1 Split View: 2–4 panes (2 default; 3–4 power layout), **focused pane owns toolbar** (Spec-A rule), per-pane identity chip *permanent* in mixed mode + window carries union border treatment (amendment), cross-pane drops = identity-confirm (no silent moves), saved per workspace (P23 format); T2 usability gate before enable: 12-user mixed-split study (task completion + "which identity is the left pane?" recall unaided ≥ 90%) — **fails ⇒ split ships same-identity-only until design fixes** (Spec-A's own failure-condition pattern, applied here); T3 Focus View (explicit enter/exit, chrome retract, 3 recovery routes: top edge, ⌘. + palette, Escape — security UI overlays+auto-exits (camera indicator etc.), never entered automatically); T4 Compact mode + sidebar container (Vault/Notes/Observatory dockable; sidebar hosts panels — no second source of truth); T5 Network Firewall *view*: per-site/identity allow-deny rules authored via deliberate sub-dialog (scope ladder once/session/site/identity; typed pattern confirm for wildcard denies — "a firewall you click blindly is worse than none"), stored as Shield dynamic rules (engine = P11, no new engine — all specs concur), rule list w/ usage counters + last-hit; T6 extension egress observation: extension requests tagged (id) in network service → declared-host diff → log (observable only) + optional suspend-undeclared policy (default log-only, enterprise can deny); update-diff alerts (P21-T9) surface here w/ Attention ceilings; T7 Translation framework v1: provider registry (user-add: LibreTranslate URL, DeepL key, self-hosted bergamot container instructions — *browsermt libs untouched as a service dependency*), inline provider disclosure before first send per origin, per-origin allow memory, page-text egress **never** by default; on-device component: **evaluated only** (P39 register: ship if Google-free + offline + non-conversational — DR-16's sole exception, gate remains); T8 DevTools XR panel (internal extension: identity/partition view, Shield decisions w/ rule provenance, permission overlay state, per-identity storage sizes; reads via `chrome.debugger`? **no** — DevTools-extensions protocol w/ dedicated xr domain exposed *read-only*; no DevTools core patches — asserted in patch ledger); T9 Performance panel: Task Manager re-skin + Memory Saver/hibernate controls + per-identity aggregation + "what's using my RAM" (data from process manager, no new telemetry); T10 Screenshot region+annotate+redact v2 (P25 base): region capture (magnifier+snap), arrows/text/blur-rect (blur is *destructive pixelization at export* — redaction irreversibility test), quick-share to panel/notes.
- **Touches:** `xr/ui/split/`, `xr/net/firewall-ui/`, `xr/tools/translate/`, devtools extension, screenshot v2.
- **Contracts out:** firewall rule format (subset of Shield dynamic rules — same object!), translate provider schema (frozen early at P5 as stub — now real).
- **Deps in:** the listed phases. **Decisions locked:** views-over-engines law (nothing new here computes a verdict alone); same-identity fallback if T2 fails.
- **Security req:** split focus/toolbar ownership audited (URL-bar-targeting spoofing is the classic split-view bug — dedicated test class: "typing while pane B focused must not act on pane A"); translate = content-egress consent per-origin; redact irreversibility property (no underlying pixels in output — PNG pixel-diff assert).
- **UX req:** split pane headers w/ identity+trust visible; Focus never hides security; devtools panel read-only.
- **Tests:** split matrix (focus routing, resize persistence ×workspace, 4-pane 3-identity ×themes visual), egress-vs-declared fixtures, translate capture proof (nothing pre-consent; disclosed provider after), redact suite, DevTools panel works against 3 consecutive Chrome betas (drift test — it's unpatched, so just compat).
- **Manual:** 12-user mixed-split study (T2); firewall-authoring day w/ sysadmin users; devtools panel with real web-app debug sessions.
- **Perf:** split focus-switch ≤ 50 ms; egress tagging ≤ 0.1 ms/req.
- **Rollback:** each view disable individually (engines remain).
- **DoD:** T2 gate passed or fallback recorded; all views green in §11 suites.
- **Artifacts:** split/focus/sidebar v1, firewall UI, translate v1, devtools panel, redaction v2.
- **Feeds:** P35 (letterbox joins the fingerprint family), P36 (split a11y), P37 (onboarding mark: split on window resize habit).

### Phase P35 — Fortress grade: letterboxing, promotion, partition parity
- **Objective:** Make "maximum daily-driver hardening" real: letterbox, default-deny perms (already), session-scoped storage option, extension allowlist-only mode, and the *measured* per-identity hardening of shared network state (HSTS/TLS-session/DNS) via promoted profiles where the partition seam can't reach.
- **Why:** Fortress existed as a dial position in all three specs; it earns the label only with concrete, tested differences — and honest "still shared" rows closed or documented (Spec-A F28).
- **Prereq:** P14, P20, P17/18, P21.
- **Tasks:** T1 Letterboxing (Fortress/Tor opt-in): min/max viewport pad, deterministic w/ identity color? **no**: fixed size buckets from *policy* (uniformity within population where feasible: same-bucket quantization), layout-corpus regression; T2 default-deny list (cam/mic/location/notifications/clipboard/sensors/fullscreen-w/o-gesture?) + *audited prompt suppression* (deny = silent, not nag); T3 extension allowlist-only mode (Fortress: allowlist or none — pairing w/ P21 availability); T4 per-identity storage scope option: "session-only storage" (partition marked in-memory w/ explicit persistent exceptions list); T5 promoted-profile flow: identity promotion to dedicated OTR profile (P4-T7 machinery) w/ data-copy ceremony + revocation; post-promotion, *per-profile* DNS cache/HSTS/cookie jar all separate (measured, added to isolation matrix as "Fortress" row); T6 shared-state final table: for non-promoted identities publish residual shares (OS DNS cache, GPU) — §1.13 updated by measurement; T7 security-inspection surfaces: per-identity cert-store/CT behavior documented; T8 "Fortress day" QA script formalized as recurring (login-heavy apps incl. two banks w/ test accounts, web conferencing, SSO flows).
- **Touches:** `xr/policy/` (new fields), `xr/identity/` promotion, fingerprint family.
- **Contracts out:** EffectivePolicy.fortress object frozen; promotion ceremony contract.
- **Deps in:** stages prior. **Decisions locked:** promotion is *explicit* (never auto); letterbox never default.
- **Security req:** promotion data-copy = S0 review (no residue from source partition post-copy — FS-diff); letterbox doesn't leak via `devicePixelRatio` mismatch exploits (measure suite).
- **UX req:** Fortress copy = what it costs (sites break — "Some sites may break: [undo]") in the change-strip.
- **Tests:** matrix adds "Fortress" ×all; letterbox corpus (500 layouts); prompt suppression; session-only-storage close-purge; promotion round-trip (promote→demote w/o loss).
- **Manual:** Fortress day ×2 weeks dogfood (mandatory for 4 engineers incl. on-call) — breakage reports triaged daily; enterprise pilot ask (policy-forced Fortress).
- **Perf:** letterbox layout delta ≤ 3 ms/frame on corpus; promoted profile ≤ +180 MB worst-case (documented, budgeted).
- **Rollback:** demote; dial down; each control per-site.
- **DoD:** matrix green; §1.13 updated with measured rows; docs ship with breakage list.
- **Artifacts:** Fortress 1.0, promotion tooling, updated disclosures.
- **Feeds:** §17 Beta gate (Fortress must be *real* before beta); enterprise policy pack (P38).

## STAGE 7 — FULL PRODUCT & RELEASE (P36–P39)

### Phase P36 — Accessibility & localization completion
- **Objective:** WCAG 2.2 AA everywhere (AAA for security copy where practical), en+9 locales incl. RTL, screen-reader contracts for every security surface.
- **Why:** Legal/ethical floor *and* the trust story (a browser that lies about protection to a screen-reader is worse than none); also the only phase where "done" means *external* audits, not internal suites.
- **Prereq:** all user-facing phases.
- **Tasks:** T1 axe-core zero-violation gates on all WebUI (waivers registry w/ expiry dates — no permanent `//eslint-disable` equivalents); T2 AXTree snapshots for views (tab strip, dial, panel, split) per release; T3 screen-reader full passes: NVDA+Firefox? no—NVDA, VoiceOver, Orca against onboarding, browsing, panel, vault, settings, split-focus, permission prompts — findings logged as P0-P1 blockers; T4 keyboard completion: the 12 core tasks list (in `docs/a11y/tasks.md`) only-keyboard timing baseline; T5 reduced-motion: every animation has off-path; T6 l10n: string freeze mechanics, pseudo-loc build always-on in CI, RTL full-suite (layouts incl. split & tab-strip), security-copy human review per locale (bilingual reviewer sign-off recorded); T7 high-contrast theme ×farbling ×letterbox interactions; T8 help-center l10n parity (missing-locale policy: fall back w/ banner, never machine-translate legal copy).
- **Touches:** UI everywhere (fixes), l10n infra. **Contracts out:** a11y waiver registry; locale matrix.
- **Deps in:** all. **Decisions locked:** §11.6 gate numbers.
- **Security req:** SR announcements never read secrets (vault copy confirmations mask values; tested).
- **UX req:** n/a (this *is* UX). **Tests:** all T1–T5 automated except T3 manual passes.
- **Manual:** the audits (T3) by hired specialists (budget line — not internal goodwill).
- **Perf:** a11y trees cached; no layout thrash on focus change.
- **Rollback:** n/a.
- **DoD:** external SR sign-off; locale coverage ≥ 92% strings on the 9 non-en; RTL green; waiver registry all-dated.
- **Artifacts:** a11y report, locale drop, docs.
- **Feeds:** P37 copy lock, §17 alpha/beta gates.

### Phase P37 — Onboarding, migration, help, crash & first-run program
- **Objective:** First-run = Chrome-familiar in 10 s, migration of real lives (bookmarks→vault→engines→extensions→identities), teach-on-use marks, help/threat-model surfaces complete, crash UX (card, not modal) proven.
- **Why:** First-run abandonment is where hardened browsers die (Spec-A: "decided here"); also where the moat's *comprehension* must be validated (§17 usability gate).
- **Prereq:** P14, P21, P25–P27, P30, P36 copy lock.
- **Tasks:** T1 onboarding: 4 screens max (Welcome / Import / Default protection / Identities), skippable everywhere, <60 s, **no tours after**; default state = one unnamed invisible workspace + one default identity (zero-cost start); T2 importers: Chrome/Edge/Firefox/Brave/Vivaldi (bookmarks, history, engines, **passwords re-encrypted into P27 store w/ per-source loss report**, extensions → Guard review queue not auto-enabled, sessions → workspace mapping), KDBX/CSV vault import front-and-center (amendment #4), duplicate-collision policy (keep-both w/ tag); T3 teach-on-use engine: 6 lifetime marks max (vertical-tabs offer, identity offer on same-provider second login, first block explanation, first vault save, first quarantined download, split offer), one-time-ever, disable-all switch; T4 `xr://help`: per-feature "does NOT protect against" sections (parity CI: every §2 S0/S1 row has a help anchor — machine-checked), interactive threat-model browser (adversary cards w/ current status), diagnostics export (redacted bundle); T5 crash/restore UX: session-restore card w/ per-identity summary + "restore later", crash-loop guard (safe-mode prompt after 2 consecutive), ephemeral-never-restored law asserted in CI (P9 drill); T6 first-run privacy posture screen: telemetry OFF visualized (viewer preview), search default chooser (P24), Shield defaults summary; T7 "import and continue where you left off" polish pass: window/tab order preservation best-effort w/ honest note.
- **Touches:** `xr/ui/onboarding/`, `xr/tools/import/`, help content, session paths.
- **Contracts out:** import-format versions; mark-registry (each mark = content-reviewed copy + trigger rule + dismissal state).
- **Deps in:** stages 2–5 + P36. **Decisions locked:** 4-screen cap; no tours; marks budget 6.
- **Security req:** importer = hostile-source parser (browser DBs from other apps): fuzzed; password import never lands in plaintext temp files (stream into encrypted store, verified by FS-watch test); extension import never auto-enables (Guard gate only).
- **UX req:** migration completes ≤ 10 min median on Chrome-100k-bookmarks worst case (measured, bounded, progress honest).
- **Tests:** importer corpus (12 browser versions × 4 formats incl. corrupt), mark-trigger logic (no repeats, off-switch), restore-card states incl. double-crash loop, help parity CI.
- **Manual:** 12-participant first-run study (recruited non-employees; §17 gate: ≥90% can name their identity unaided after 15 min use); dogfood transfer day (team migrates real profiles).
- **Perf:** first-run to usable-browser ≤ 45 s median incl. import of typical profile.
- **Rollback:** import is additive; per-section undo (import log lists what landed).
- **DoD:** study gate passed; import loss reports verified; help parity bot green.
- **Artifacts:** onboarding, importers, help center v1, first-run study report.
- **Feeds:** §17 beta; P38 program.

### Phase P38 — Beta program, external assurance, hardening closure
- **Objective:** Take the near-complete product through real adversarial exposure: closed beta w/ staged updates, external penetration test, independent-rebuild verification, crash program, bounty expansion — and *fix everything it finds*.
- **Why:** "Security browser" claims need third-party evidence, not self-scored suites; also the phase where perf budgets, memory ceilings, and leak posture survive contact with 1,000+ diverse machines.
- **Prereq:** P1–P37 DoDs green (this phase *blocks* on all suites being real).
- **Tasks:** T1 public-beta build hardening: default settings audit pass, kill-switches verified remotely (component-level; **nothing auto-behaviors remotely** — disclosure), update cohorts (25/50/75/100 staged w/ crash-rate auto-halt wired to opt-in crash infra); T2 crash program: Crashpad → self-hosted (GlitchTip/Sentry-self-hosted class), symbolication per release, scrubbing (URLs/paths redacted by client *before* upload, k-anon on build ids; local "what would be sent" viewer extended to crashes), auto-halt thresholds defined numerically (e.g., 30-day crash-rate delta >1.2× prior stable ⇒ halt rollout — CI-checkable artifact); T3 **external penetration test** (scope: identity isolation, Vault+sync+pairing, tord/wgd boundaries, Guard chokepoint, update channel, list channel; two firms, findings under NDA→published after remediation; P0/P1 = release-blocking); T4 independent rebuild program: 2+ external builders rebuild release from docs; diffs triaged to toolchain-level explanations (provenance rung — *not* bit-identical claims); T5 SBOM/advisory/licence final: consumed-upstream-CVE map published per release (P3-T6 output), license audit incl. list attributions; T6 privacy review external (telemetry-free claims re-verified by capture); T7 bug-bounty program v1 live (scopes: `//xr` + helpers + infra; payouts; triage SLA 3 business days — staffed); T8 2-week full-dogfood internal (all teams, primary browser, 3 OS) with breakage + perf + attention-budget counters reviewed daily; T9 **usability: identity comprehension final gate** (Spec-A's rule: ≥12 non-employee users can state which identity they're in unaided — 100% recall at task-end or release blocked); T10 release-candidate build cut w/ evidence bundle (all suite links per DoD format).
- **Touches:** infra, docs, all (fixes). **Contracts out:** none new — everything *verifies*.
- **Deps in:** everything. **Decisions locked:** no feature work during P38 except remediation.
- **Security req:** this phase *is* the security acceptance; findings triage board is the authority.
- **UX req:** beta feedback micro-surface (panel footer, optional, redacted).
- **Tests:** T1–T8 are tests. **Manual:** the studies (T8, T9) + pen-test debrief sessions.
- **Perf:** fleet-wide budgets (P9 service) green on beta cohort hardware spread incl. 8 GB RAM tier.
- **Rollback:** beta cohort pinned; rollout halt authority = on-call (documented, drilled).
- **DoD:** pen-test high/criticals closed w/ retest; rebuild variance explained; T9 gate passed; beta cohort ≥1,000 with 2-week clean-ish metrics (crash-rate ≤ target, breakage triage ≤48h median held).
- **Artifacts:** pen-test reports (remediation log), rebuild attestations, beta metrics report, RC build + evidence bundle.
- **Feeds:** P39.

### Phase P39 — GA, community launch, and the long-horizon register
- **Objective:** Public stable 1.0 + the open-source *machine* (community governance, roadmap process) + the register of deferred-but-real work, each with its entry condition — so "the full product" never quietly shrinks.
- **Why:** The brief demands the complete system accounted for; launch turns the docs into obligations.
- **Tasks:** T1 stable release w/ full evidence bundle (every §17 "Stable" row linked); T2 public repo switch: `xr-core` + helpers public, contribution guide, "good first patch" board tied to patch-ledger *retirements* (§12.5), RFC process dogfooded (first RFC: card autofill format); T3 press/documentation site incl. published threat model + limitations + leak-report archive (radical transparency *is* marketing — all three specs' verdict); T4 enterprise policy pack v1 (admin templates: forced DoH/proxy, identity allowlists, Guard policies, extension allowlist, update channel pin) — first funded-edition substrate (MPL keeps this legal); T5 long-horizon register formally opened w/ entry conditions + owners: **Payment cards** (demand evidence + PCI-adjacency review; format designed w/ vault), **Android** (staffing + platform-specific Vault/Tor/extension story; the `//xr/core` non-desktop-assumption law enforced), **on-device translation** (sole AI-adjacent exception; gate = Google-infra-free + offline + non-conversational re-verified), **theme gallery** (declarative-format-only), **bit-identical reproducible builds ladder** next rung + annual review, **XR Verified catalog expansion** (community nominations + review rota), **MV2 re-check** (per §12.6 evidence clause), **Adaptive Trust v2** (only if v1 usability data justifies richer policy shapes); T6 post-GA cadence: promotion cycle steady-state (§12), SLA publication (real numbers), security review rotations; T7 "v1.0 retrospective" published honestly (what shipped, what deferred, what was right/wrong to promise — brand asset + accountability).
- **Touches:** everything (governance), docs, infra.
- **DoD:** §17 "Stable Production" column green; register rows have owners; public repo live with zero broken CI.
- **Artifacts:** stable 1.0, docs site, enterprise pack, register.
- **Feeds:** steady state.

---

# 5. WORK BREAKDOWN STRUCTURE — TASK SYSTEM & SAMPLES

**Where the WBS lives:** §4 *is* the WBS — every phase's Tasks block is written issue-ready (`XR-Pxx-Ty`). This section defines the grammar so it scales, and gives fully-expanded exemplars (a phase's tasks expand to 1–6 issues each at sprint time; the exemplar pattern is the standard (laws L8/L11)).

**Task grammar (every issue body carries these seven fields):**
1. **Change:** what to implement (one sentence, no adjectives).
2. **Where:** exact paths/annotations (`//xr/policy/resolver.*`, `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance` consult, `xr/ui/panel/network_tab.*`).
3. **Contract:** which frozen interface/schema (§1.11) is consumed/implemented — with version.
4. **Tests:** the named suites in §11 this task must add to (unit/browser/leak/isolation/fuzz/visual/a11y) — test files listed in the PR, not "QA will cover."
5. **Must-not-break:** the invariants (§1.12) and budgets (§11.7) touched.
6. **Evidence:** the CI artifact ids that close the task (link format defined in P9-T12).
7. **S0/S1 review:** flags triggering dual review (paths in P1-T7 list).

**Fully expanded exemplar (the standard):**

> **XR-P15-T1b — policy-enforced per-identity permission overlay**
> **Change:** Implement per-(identity, capability) permission default overlay with persistent storage, browser-process validation at `PermissionContextBase::GetPermissionStatus`, request-time mediation, and expiry; expose via `xr.mojom.PolicyResolver` fields only (no second store).
> **Where:** `//xr/permissions/overlay.{h,cc}`, hooks in `xr/browser/permission/*` (2 upstream lines max at `PermissionResult` return sites — patchinfo required), prefs schema `xr/permissions/schema` v1 with `xr-schema` migrations.
> **Contract:** `EffectivePolicy.permissions` (v1 frozen); ledger row types `permission.grant/revoke/expiry` (P5 §1.11).
> **Tests:** unit: overlay precedence + corrupt-store⇒deny; browser: allow/deny/one-time/7d-expiry × identity-A-vs-B cross-read negatives; property: expiry sweep under clock change; isolation-matrix integration row "permissions" for 2-identity fixture; a11y label pass on prompts; fuzz: overlay record parser (24 h).
> **Must-not-break:** invariants 1, 7 (ledger completeness), resolver totality (unknown capability ⇒ deny), prompt ceilings (§1.10 Attention).
> **Evidence:** CI run ids for the four suites + patch-count delta (≤2).
> **Review:** S0 (policy enforcement point) — two senior reviewers, one from Security.

**Expanded second exemplar (UI-class):**

> **XR-P22-T4 — identity-aware tab search**
> **Change:** ⌘⇧A palette-tab-search view over live tabs + closed history, filters by identity/workspace/trust/shield-state, fuzzy rank, ≤60 ms at 1k tabs.
> **Where:** `//xr/ui/tabsearch/` (Lit view over P7 registry `scope=window` provider), index in `xr/tools/index` (same store as notes/highlights — no new index tech).
> **Contract:** command descriptor v1; ledger `tab.closed` rows for history results.
> **Tests:** bench fixture 1k tabs (CI budget assert); E2E keyboard-only flow; RTL snapshot ×2 themes; SR label suite on results (identity name+color-word, trust-word — no color-only).
> **Must-not-break:** NTP zero-network law; palette budgets (this view shares them); privacy (index is local; no page *content* indexed — titles+URL only, asserted in fuzz corpus).
> **Evidence:** bench numbers + E2E + a11y CI links.
> **Review:** S1 (copy for identity/trust labels per §1.12-9 honesty rules).

**Scaling rule:** at phase start, PM-lead + owning team split each `XR-Pxx-Ty` into issues (one task = 1–5 days); tasks >5 days are definitionally mis-split; cross-phase dependencies get the §3 graph edge as an issue-link (tooling enforced: dependency graph is generated from issue metadata — §13.2).

---

# 6. PARALLELIZATION PLAN

## 6.1 Tracks

| Track | Owns | Phases (primary) | Staff (FTE) |
|---|---|---|---|
| **A — Platform/Chromium** | build, rebase, patch ledger, branding, update/release infra, packaging, signing | P1–P3, P10, §12 machinery | 3–4 |
| **B — Security & Identity** | policy resolver, identity system, permissions, process/isolation guarantees | P4, P6, P14–P16, P35 | 2–3 |
| **C — Vault & Downloads** | credential stack, vaultd, sync, inspect, media affordance | P26–P30, P33 | 2 (dedicated, never shared) |
| **D — Network, Shield & Extensions** | shield engine, lists, DNS/proxy/routes, fingerprint engine, tord, wgd, leak suite, Extension Guard | P11–P12, P17–P21, P31–P32 | 2–3 |
| **E — UX Engineering** | registry/palette, chrome, tabs/workspaces/split, settings/themes, panel, onboarding, tools | P7–P8, P13, P20 UI, P21 UI, P22–P25, P34, P37 | 2–3 |
| **F — Design** | design system, tokens, IA, attention-budget compliance, usability studies | gate roles in P7/P13/P14/P22/P34/P37 | 1–2 |
| **G — QA/Security Assurance/Release** | P9 infra, corpora, leak/fuzz ops, a11y, l10n program, pen-test & audit logistics, beta program | P9, P19, P36, P38 | 2 + contracted firms |

**Track letters here are canonical**; they remap the brief's illustrative lanes as: A=Foundation/Platform, B=Security & Identity, C=Vault & Downloads (brief's D), D=Network, Shield & Extensions (brief's E+D parts), E=UX Engineering incl. Workspaces (brief's C+F), F=Design (gate role, not a shipping lane), G=QA/Security-Assurance/Release. All tables in this document use *this* mapping; the Owner column names the primary track (multi-track shown with `+`).

## 6.2 Concurrency model

- **After P5 freeze (SF-1), all tracks move in parallel against fakes.** E never waits on B (identity UI runs on fakes until P14), C's *vaultd crate* and D's *tord/wgd engines* start as early as P6 (pure components; integrate at their phases), G builds corpora throughout.
- **Serial spine (one team at a time):** P4 (spike gates P14's shape) → P14 (identity v1 gates P15/17/18/21/22 scope of *scoping work* — but E's tab-layout code proceeds layout-only) → P19 (leak-complete gates P31/32 ship).
- **The two gate-phases everyone must staff into:** **P9** (infra: every track contributes a runner) and **P38** (assurance: everyone fixes).
- **Never parallel:** anything touching the same upstream patch (patch ledger conflict = integration order, §12.2); S0 review load (max 2 concurrent S0 PRs per pair of reviewers — queue, not rubber-stamp).

## 6.3 Synchronization points (branches integrate here, nothing floats past)

| SF | Point | Condition | Who converges |
|---|---|---|---|
| SF-0 | End P5 | contracts frozen + fakes shipped; **all tracks rebase onto frozen contracts** | A–G |
| SF-1 | End P10 | build+update+test machinery live; nightly "XR full build" from canary rebase green | A, G |
| SF-2 | End P14 | identity v1 real in product; fakes retired for identity; Isolation Card live | B, D, E (tab/panel), G |
| SF-3 | End P16 | **Internal Alpha cut** (§17 row 2) — first dogfood-everything build; shield+identity+permissions+protections integrated | all |
| SF-4 | End P21 | extension+guard+Fingerprint+network baseline complete; **Public Alpha** possible | B, D, E, G |
| SF-5 | End P30 | vault-audit-cleared, daily-driver UX complete; **Beta** eligible (P38 begins) | C, E, G |
| SF-6 | End P35 | full advanced tier integrated (Tor/WG/passkeys/Fortress); feature freeze | C, D, E |
| SF-7 | End P38 | RC evidence bundle complete → P39 launch | all |

**Integration ritual:** every SF = a week-long "merge train": branches land sequentially per patch-ledger dependency order, compat corpus + leak + perf + a11y gates run *against the merged tip*, not per-branch (per-branch gates run subsets; SF runs full). An SF that fails = the responsible phase fixes forward; **no SF slips without a re-plan memo in the register** (L11 + Decision Register entry).

## 6.4 What cannot be parallelized (state it so juniors stop trying)

P4 before identity-scope lock. P6 before any mode logic. P10 before shipping anything. P19 before Tor/WG ship. P28 fuzz+design-review before audit engagement; audit before real credentials in stable. P36's external a11y sign-off before §17 beta. Copy/honesty review (F+G) before any claim ships. The rebase bot never pauses for a deadline (§12.1).

---
# 7. REPOSITORY & MODULE PLAN

## 7.1 Topology (two repos + helpers; deliberately not a sprawl)

```
xr-browser/                       # META REPO — the build/release/governance surface
├─ DEPS                           # pinned chromium rev + xr-core rev (single source of truth)
├─ docs/                          # threat-model.md · limitations.md · adr/ (RFCs) · hw.md ·
│                                 #   contracts/ (generated from //xr/mojom) · processes/ (signing,
│                                 #   disclosure, release, incident runbooks)
├─ patches/                       # manifest.yaml + per-patch patchinfo + budget ledger tooling
├─ build/                         # GN argsets, toolchain pins, branding inputs, packaging defs
├─ ci/                            # pipelines-as-code: rebase bot, gates, evidence collector, dashboards
├─ release/                       # update server, transparency tooling, channels config, SBOM glue
└─ scripts/                       # fetch/apply/rebase/release entrypoints (python, typed)

xr-core/                          # checked out at chromium/src/xr — MPL-2.0, THE product
├─ BUILD.gn / OWNERS / CODEOWNERS
├─ common/                        # shared value types (IdentityId, OriginKey, PolicyVersion…), no logic
├─ mojom/                         # frozen contracts + fixtures/ + fakes/ (P5) — changes need RFC
├─ policy/                        # THE resolver (pure), prefs schemas, golden vectors
├─ identity/                      # provisioning, lifecycle, templates, promotion, overlay stores, session
├─ shield/                        # adblock-rust embedding, rule scoping, events, scriptlet registry
├─ net/                           # RouteManager, dns/proxy config, onion guard, leak policies, SB glue
├─ fingerprint/                   # seeds + surface shims (consumes shield's injection plumbing)
├─ permissions/                   # HCMS overlay + expiry sweep + audit hooks
├─ extensions/                    # guard: manifest engine, grades, availability enforcement, ledger
├─ vault/                         # client of xr-vaultd + autofill mediation + import/export
├─ downloads/                     # pipeline hooks, quarantine, verdict mapping, media affordance
├─ commands/                      # registry, palette glue, shortcuts
├─ tools/                         # screenshots, notes/highlights store, reader glue, translate providers, search/bangs
├─ ui/                            # views/: chrome, tabs, split, panel shell · webui/: panel, settings,
│                                 #   vault, onboarding, themes, help  (Lit; CSP-strict; generated tokens)
├─ components/                    # small reusable pieces (ring buffer, xr-schema migrations, redaction)
└─ test/                          # browser_tests/, unit/, isolation/ (matrix), leak/ (probes),
                                  #   fixtures/, bench/

xr-vaultd/    (Rust; own repo)    # KDBX engine, crypto, TOTP; vendored by xr-core DEPS pin
xr-tord/      (Rust; own repo)    # Arti default / C-tor fallback host; same
xr-wgd/       (Go;   own repo)     # wireguard-go → local SOCKS5 host
xr-inspect/   (Rust; own repo)    # archive/binary sniffing
xr-lists/                         # filter-list bundling, signing, attribution, delta gen
xr-leaktest/                      # route-leak suite (CI-resident; results published)
xr-update-server/                 # minimal signed manifest server (+ tests, runbooks)
xr-web/                           # docs site, threat-model publication, help sync
```

**Why this shape:** one product repo (atomic `//xr`↔Chromium pin moves), one meta repo (release/governance never drifts from build), five process-separable components get their own repos because they're *independently fuzzable, signable, and updateable* (and Rust/Go toolchains stay out of Chromium's dep graph via vendored pins). No artificial package zoo: subsystems are directories with OWNERS, not npm-style sprawl. `//xr/common` exists once so types can't fork.

## 7.2 Ownership & boundaries

- **CODEOWNERS:** every top-level `//xr/*` dir + every helper repo + `patches/`, `ci/`, `release/` has named owners + deputies; `//xr/policy`, `//xr/vault*`, `//xr/net`, `//xr/identity`, `//xr/extensions` are **S0** (dual senior review, L13); `xr-mojom` changes additionally require an approved RFC.
- **Import law:** `//xr/a` may import `//xr/common`, `//xr/mojom`, `//xr/policy` (read-only consumption) — *never* another subsystem's internals; the GN check script enforces in CI.
- **Upstream-contact ledger:** every file in chromium proper touched by XR is registered in `patches/manifest.yaml` with owner, category, risk class, rebase notes — the same file the budget meter reads (§12.2).
- **Chromium checkout policy:** never commit into `src/` outside `src/xr` except via patch manifest (CI blocks stray diffs).

## 7.3 Source-of-truth artifact map

| Artifact | Lives | Consumed by |
|---|---|---|
| Feature registry (§2) | `docs/registry/` (machine-readable YAML + rendered table) | phase planning, DoD checks, help-parity bot |
| Decision register (§18) | `docs/decisions/` | CI: PRs touching a DR row require its RFC id |
| Contract docs (generated) | `docs/contracts/` | all tracks |
| Isolation matrix results | G's evidence store (linked per build) | §17 gates |
| Leak report | `xr-leaktest` publishes per release | help page, §17 |
| Patch ledger + budget | `patches/manifest.yaml` + CI meter | rebase bot, §12.5 metrics |
| ADR/RFC history | `docs/adr/` | governance |

---

# 8. TECHNOLOGY SELECTION

**Format:** decision verb (use/don't/integrate/fork/adapt/wrap/build) + why + rejected-alternative note. Research status per Appendix A.

## 8.1 Engine & core

| Item | Decision | Why |
|---|---|---|
| **Chromium** | **USE, overlay-fork (`xr-core` @ `src/xr`)** | Only base with web-compat + MV3 ecosystem + Site Isolation + StoragePartition seam (R1/R2). *Rejected:* Firefox ESR (correct only under a solo-maintainer premise the three specs rejected; loses MV3 compat + the partition story is what we build anyway); Ladybird (not a product base this decade); WebKit fork (all the treadmill, none of the ecosystem). |
| Milestone policy | **USE even-numbered/Extended-Stable-equivalent for shipping promotions; daily-canary rebase on `main`** | R9: two-week trains (verified, Chrome 153+ Sep 8 2026) make full tracking unstaffable and pointless; CEF's public adaptation is the precedent; security releases decoupled (§12). *Rejected:* Spec-A's "ship canary-weekly" (users get churn; QA can't absorb 26 trains); Spec-C's "stable-only" (conflicts discovered at worst time). |
| Blink/V8 | **INTEGRATE as upstream; ~25-file hook budget (cosmetic, fingerprint, seed plumbing)** | Never V8-internal patches (all specs concur; security review + JIT correctness risk). |
| Sandbox/Site Isolation/Process model | **INTEGRATE; never weaken; XR adds *policy* (partition-per-identity) not machinery** | Invariants §1.12-2/8; the "we didn't break Chromium's sandbox — here's the audit" claim is the credible one. |
| Safe Browsing | **ADAPT: v5 Local-List + OHTTP relay default; Real-Time opt-in; Enhanced never built; Web Risk as commercial fallback (LG-2)** | R6 — obsoletes both "drop it" (unsafe) and Spec-C's self-operated proxy (ops liability, unnecessary now). |
| Widevine | **INTEGRATE user-initiated download path (in-tree component flow, Brave-model), default OFF, disclosed** | R13; never bundled; Linux packaging nuance documented; LG-3 gate. |

## 8.2 Filtering, fingerprinting

| Item | Decision | Why |
|---|---|---|
| **adblock-rust** | **INTEGRATE (vendored, pinned, `cargo vet`); upstream fixes contributed** | Best-maintained option; uBO-syntax compat; now field-proven by Brave + *bundled experimentally by Firefox 149* + Waterfox + Perplexity Comet **[VERIFIED]** — the cross-vendor validation no in-house engine would earn for years. *Rejected:* own engine (multi-year for negative differentiation), DNR-based (caps + no document-start). |
| Filter lists | **INTEGRATE as signed runtime data** (EasyList, EasyPrivacy, uAssets, Peter Lowe, AdGuard sets) via XR bundling channel | GPL/CC lists never linked (DR-04); signature+pin, LKG fallback; Disconnect **excluded** (BY-NC-SA — R8) unless commercially licensed post-GA decision. |
| Cosmetic/scriptlets | **BUILD thin Blink seam + engine's cosmetic path** | Above budget; degrade-safe law. |
| Farbling surfaces | **BUILD in `//xr/fingerprint`** (per-eTLD+1×identity seeds) | No upstream primitive exists; Brave-proven shape; *no resistance claims* (law §0.3). |
| uBlock Origin / uBO Lite bundled | **DON'T** (GPL3 code; and XR *is* the blocker) — users may install uBO Lite themselves | All three specs concur; registry re-check only. |

## 8.3 Network / Tor / WireGuard / DNS

| Item | Decision | Why |
|---|---|---|
| Tor engine | **INTEGRATE Arti (default) + upstream C-tor (fallback), both behind `xr-tord`** | R3: 2.6.0 full-client+onion verified; Rust, embed-designed; C-tor keeps bridge/Snowflake completeness one toggle away. *Rejected:* implementing any Tor logic ourselves; embedding Tor Browser's whole stack (that's a *browser*, §1.13 honesty). |
| WireGuard | **INTEGRATE wireguard-go (MIT) inside `xr-wgd` → local SOCKS5 only** | R4. *Rejected:* boringtun default (restructuring warning + port-deprecation evidence **[VERIFIED]**), TUN/system tunnels (per-OS entitlement hell — permanent ban DR-20), kernel modules. |
| Proxy | **ADAPT** (Chromium per-NetworkContext proxy config) | The supported seam; no custom socket stack. |
| DNS | **ADAPT** upstream secure-DNS stack + per-identity binding | Custom stub resolver = invented risk. |
| Network Firewall engine | **BUILD as rules-over-Shield** (no second engine) | Views-over-engines law. |
| VPN service / XR-operated relays of any kind | **DON'T — permanently** | Unanimous across A/B/C; DR-10. |
| GeoIP/PSL/CA data | **INTEGRATE upstream component data** (public datasets w/ attribution) | Don't fork Mozilla's PSL curation. |

## 8.4 Vault & crypto

| Item | Decision | Why |
|---|---|---|
| Vault format | **ADAPT: KDBX-4.1 (spec)**; reader via **keepass-rs (MIT, vendored)**; **writer = XR-owned** | Interop w/ KeePassXC = escape hatch (all specs); R10 verified: upstream write path experimental/lossy ⇒ we own writes + golden corpus; `kdbx-rs` (GPL) banned. |
| Crypto primitives | **INTEGRATE libsodium + RustCrypto (Argon2) + BoringSSL in-Chromium** | Zero custom crypto (law). |
| Key storage | **ADAPT OS keystores** (DPAPI/Keychain/Secret Service+KWallet) w/ explicit password-only fallback | Honest Linux fragmentation (Spec-A note). |
| Vault process | **BUILD `xr-vaultd`** sandboxed utility proc | Attack-surface isolation; the strictest boundary (§1.3). |
| Password manager code reuse | **DON'T copy** KeePassXC/Bitwarden code (GPL/AGPL); study architectures only | License law DR-04; Spec-C's Bitwarden-incident verification (no "40M breach" — that audit.txt claim is fabricated; *local-first argument stands on its own merits* **[VERIFIED correction in Spec-C]**). |
| TOTP | **BUILD (RFC 6238 vectors)** | Trivial + high value. |
| Passkeys | **INTEGRATE** upstream WebAuthn (platform/hybrid); **BUILD `xr-authd`** hardware-bound resident path only | F41-condition preserved (all specs). |

## 8.5 Storage / IPC / data

| Item | Decision | Why |
|---|---|---|
| Web storage | **INTEGRATE** (StoragePartition machinery) | Never re-implement isolation. |
| XR stores | **BUILD atop SQLite** (`xr-schema` versioned migrations; WAL) | Chromium-bundled, boring, auditable; *rejected:* adding LevelDB-paraphernalia or a new KV engine (migration burden across three OS without payoff). |
| Preferences | **ADAPT PrefService** (+ XR schema for structured stores) | One prefs brain; no shadow-settings DBs (would drift — the resolver's whole point). |
| IPC | **INTEGRATE Mojo**; `//xr/mojom` review regime | Native boundary + built-in fuzzability (P9-T8 harness drives it). |
| Sync blob crypto | **INTEGRATE age-style crate suite** | Ceremonies reviewed in audit; no bespoke envelope. |

## 8.6 UI / themes / i18n

| Item | Decision | Why |
|---|---|---|
| Native chrome | **ADAPT Views** (subclass-first per §7.2) | Only way tab-strip/identity marks survive GPU oddities; layout fork rejected (perpetual conflict). |
| Panels/settings/vault/onboarding | **ADAPT WebUI + Lit (pinned)** | Chromium-standard (Lit already in-tree); *rejected:* React/Vue/svelte (second toolchain = tax), "all-native" (iteration speed dies on a11y+theming). |
| Themes | **BUILD declarative JSON tokens; NO CSS/JS themes, ever (security boundary)** | Unanimous; loader contrast-refusal enforced. |
| Icons/fonts | Inter/JetBrains Mono (OFL) + bundled SVG set (no icon fonts) | License-clean (verified by specs; re-checked in dep audit). |
| i18n | **ADAPT** Chromium l10n + `.xtb`; en + 9 (ar/he/fa included → RTL early not "later") | Spec-B lesson; parity CI. |
| DevTools | **INTEGRATE untouched; XR panel = internal DevTools extension** | All specs; zero patch tax. |

## 8.7 Testing / fuzzing / perf

| Item | Decision | Why |
|---|---|---|
| Unit/browser | **INTEGRATE** gtest + Chromium `browser_tests` + P9 fixtures | Fork-native, upstream-bot friendly. |
| WPT | **INTEGRATE** + parity bot (vs Chrome Beta *and* Stable — R9 churn) | Compatibility law needs data. |
| Visual | **ADAPT** Chromium Gold (skia-gold tooling exists in-tree) + XR snapshot set | Don't buy Percy-class SaaS for a security brand. |
| Fuzzing | **BUILD on** libFuzzer + ClusterFuzzLite (in-repo continuous); upstream targets contributed (list parser, IWA-partition interactions where applicable) | OSS-Fuzz inclusion is a §13 stretch goal (upstream trust signal). |
| Perf | **INTEGRATE** Telemetry-core bench rigs (fixed HW list) + Speedometer/JetStream/MotionMark + XR budgets service | Budgets are law (§11.7); self-scored marketing numbers banned. |
| Leak/privacy | **BUILD `xr-leaktest`** (own probe language) + pcap infra | The brand artifact. |
| E2E (WebUI) | **INTEGRATE** ChromeDriver-class via existing `//chrome/test` e2e + Lit-view unit tests | No new framework. |

## 8.8 Build / CI / release / updates

| Item | Decision | Why |
|---|---|---|
| Build | **INTEGRATE** GN/Ninja/autoninja/depot_tools; RBE-class cache | Non-negotiable; *rejected:* Bazel (upstream removed; never return). |
| Rust toolchain in-tree | **ADAPT** `cargo_crate` + `third_party/rust` pattern (Chromium's own) | adblock-rust + helpers vendored consistently. |
| CI | **BUILD on GitHub Actions + self-hosted Chromium-class builders (bare-metal, 3 OS)** | Chromium builds are brutal on shared runners; capacity plan §13.1. |
| Rebase automation | **BUILD** (P3) on top of `git` + patchinfo model (Brave's tooling shape; their public repo is the reference *pattern*, not code-copy) | R9. |
| Updater | **INTEGRATE `//chrome/updater` client + BUILD tiny signed update server** | R11 ruling. *Rejected:* Omaha fork (dead upstream), Sparkle (adds a second platform stack where in-tree already handles 3), "Linux only = repos suffice" (false — component channel needed). |
| Component updates | **INTEGRATE** `components/update_client` w/ XR endpoints | Lists/tor/wgd/CRL/PSL share it. |
| Signing | **BUILD on** EV-equivalent HSM-backed Windows + Apple notarization + minisign/debsig for Linux; **sigstore/rekor for transparency + attestations** (in-toto/SLSA-style) | SLSA L3 target for helpers; browser provenance documented per release; *bit-identical never promised* (§0.3). |
| SBOM | **BUILD** CycloneDX from GN + cargo metadata (P2-T9) | CI diff-gate. |
| Deps audit | **BUILD**: license scan (GPL-link = hard fail), advisory feeds, `cargo vet` policy | P9-T9. |
| Telemetry/diagnostics | **BUILD**: none-by-default; opt-in aggregate w/ local viewer; Crashpad client + self-hosted intake (GlitchTip-class), client-side scrubbing | All specs; viewer is the trust artifact. |
| Update server | **BUILD tiny stateless** (Go/Rust), no user accounts, coarse install cohort data only (opt-out documented) | Operator minimalism. |

## 8.9 Languages & runtime

C++20 (Chromium-native code), Rust (vault/tord/inspect/list parsing glue in network service — memory-safety where hostile bytes live; **no async runtime inside network service FFI path — synchronous engine calls w/ our off-threading**, learned from adblock-rust's own threading model), Go (wgd only — wireguard-go embedding), TypeScript (WebUI only, strict; never in browser process logic), Python (tooling only, typed, pinned). One `lit` pin, one `rust-toolchain` pin, one clang pin — all recorded in DEPS/`build/`.

---
# 9. SECURITY ENGINEERING PLAN

Security is a *cadence*, not a phase. Every artifact below is owned by someone named in §6 and enforced by CI or a gate in §17 — nothing here says "we will try."

## 9.1 Threat model lifecycle

Published `docs/threat-model.md` (v0 at P1) enumerates adversary classes T1–T11 (commercial trackers; cross-identity linkage of the user's own personas; malicious sites [inherited Chromium posture — XR must not weaken, does not strengthen]; phishing/downloads; malicious/over-privileged extensions; passive network observers; fingerprinters [reduction only]; local malware/compromised OS [**out of scope, stated**]; state-level deanonymization [**out of scope — route users to Tor Browser/Tails**]; XR's own update/list channels [in scope: signing, pinning, staged, transparency]; dependency supply chain [SBOM+provenance+vetting]). Every S0/S1 feature row in §2 cites its model entry. **Rule: shipping a feature that changes the model without updating the model is a blocked merge.**

## 9.2 Privilege & sandbox architecture

- **Least privilege per process:** helpers get policy-sealed capabilities (vaultd: fs=vault-dir, net=none→P30-endpoint-only; tord/wgd: net=egress-only, fs=none; inspect: fs=temp-file, net=none). Enforced via seccomp (Linux), seatbelt (macOS), restricted-token+no-win32k (Windows); *capability drift is detected by a CI probe that greps syscall logs in a golden run*.
- **Renderer posture:** inherited; XR's only *added* guarantee is cross-identity process non-sharing (§1.4/§1.12-2) — asserted, never assumed.
- **Egress discipline:** all network leaves via network-service contexts or named processes; a static check ("no `net::` use in `//xr/ui`/`//xr/vault/client`") + pcap leak CI (§11.8) keep it true.

## 9.3 Data-class boundaries (what may live where)

| Class | Examples | Where it may exist | Never |
|---|---|---|---|
| **K1 secrets** | master key, item plaintext, TOTP seeds, WG private keys | vaultd/authd memory (+ keystore-wrapped disk blobs) | browser proc, renderers, prefs, logs, crash dumps, IPC tracing |
| **K2 site state** | cookies, storage, tokens (HTTP) | StoragePartition | cross-identity reach (§1.12-1) |
| **K3 identity metadata** | names, colors, rules, availability | XR prefs/ledger (OS-protected profile dir) | network, telemetry |
| **K4 activity** | ledger rows (blocked, granted, quarantined) | local ledger, export user-gated | auto-upload, *any* — **never** page content |
| **K5 config secrets** | proxy creds | OS keystore | plaintext prefs (lint-enforced) |

K1 rules are testable (memory-inspection suite §11.5); K5 linted (P9-T9). Crash handler: pre-upload scrubber runs *in-product process* with its output shown in the local viewer — user (not policy) is the last gate.

## 9.4 Vault security program (the product's existential component)

Written design review (P28-T10 packet: threat model, API, memory model, FFI surface, KDBX fidelity corpus) → **external cryptographic audit before real credentials in stable** (engagement starts P28-mid, P29–P30 remediation; P30 adds sync-ceremony addendum; P33 adds passkey-process addendum — each addendum *before* the corresponding GA) → zero custom primitives (dep+code lint) → memory hygiene suite (zeroize/lock/crash-residue tests) → KDBX interop matrix (KeePassXC + KeePass both directions) → recovery ceremony usability (naive-user drill, §11.5). Fuzz floor: format+IPC 7-day clean per release, permanent CI fleet.

## 9.5 Extension & supply-chain posture

Guard = observations (permissions, breadth, updates, endpoints), never intent (§1.12-11); availability enforced at the single `Dispatch` chokepoint (tested per-API class). Third-party code path summary: filter lists (data; pinned sigs; fuzzed parser), themes (data; schema-validated), extensions (upstream platform + XR policy), Widevine (user-consented download; isolated CDM process), Rust/Go deps (vendored, pinned, `cargo vet`/govulncheck + advisory SLA: critical 72 h triage), upstream Chromium itself (§12 security lane). Each item names its *owner + kill switch + LKG semantics* in the dependency-eval file (P1-T8 template).

## 9.6 Network leak-prevention doctrine

Route integrity is per-NetworkContext-at-creation, fail-closed on loss (identity traffic halts visibly; never silently reroutes), verified by the published leak suite across every route class ×{browsing, WebRTC, DNS, prefetch, captive portal, extensions, xr:// pages, update, SB, OCSP/CRL}. New features touching egress require a leak case or a CI-registered exemption with written reason (P19-T6). Tor adds stream isolation + `.onion` confinement + disclosure; WG adds key lifecycle + "no system route changes" assertion (probed in CI).

## 9.7 Download & content protection posture

Verdicts from local heuristics + SB reputation (via OHTTP); quarantine-until-ack; signature *display* not "trust"; all hostile parsing in `xr-inspect`; archive-peek with bomb ceilings; media affordance constrained by "no CDM/EME interaction" lint (structural, not policy). VirusTotal link, never upload. No AV claims (DR: we are not an AV vendor).

## 9.8 Static analysis & review regime

clang-tidy custom checks (resolver-totality, no-mode-logic-outside-policy, no-direct-HCMS-bypass), clang analyzer + MSan/ASan/UBSan bot builds (nightly fuzz+sanitizer matrix), rust clippy -Dwarnings + unsafe-block budget (`#![forbid(unsafe_code)]` everywhere except vendored FFI pins w/ justification comments), `cargo vet`, govulncheck, Semgrep ruleset (K1-in-logs, `eval` in WebUI, telemetry without consent-gate, AI API classes banned), API surface lint (no new `mojom` method without review tag). **S0 paths:** 2 senior reviewers incl. Security; written rebase-notes updated; sandbox-adjacent changes get the upstream-security-style "intent doc".

## 9.9 Security regression testing & red team

Every fixed CVE-class in XR-owned surfaces gets a permanent regression test (naming convention `SEC-*` — e.g. `SEC-crossidentity-process-01`, `SEC-onion-resolve-01`, `SEC-vault-ipc-tracing-01`); `docs/security/regressions.md` auto-generated list. Two red-team weeks per year (one before each major public milestone; P38 = first, findings published after remediation); bug bounty scoped to `//xr`+helpers+infra (upstream Chromium vulns belong to VRP — we forward + track our exposure; **XR never hides upstream issues**).

## 9.10 Incident response & disclosure

Runbooks (P1-T3, rehearsed annually): embargo triage (24 h ack, severity ladder, patch-window math vs our 72 h SLA), forced-out-of-band release via update epoch revocation (P10-T9), post-incident publication template (we publish even when embarrassing — the brand *is* this), supply-chain compromise playbook (list channel, update channel, dep backdoor: kill-switch matrix, pinned-key rotation drill), law-enforcement/data requests posture (we hold nothing — zero-knowledge claims each re-verified against the release's actual endpoints, §9.13 privacy guarantee 2).

## 9.11 Claims discipline (anti-theater law, machine-checked)

Banned-vocabulary list (anonymous · unbreakable · military-grade · invisible · "% protected" · "stealth mode" · security scores · extension *intent* statements) enforced by copy lint in UI strings, help docs, release notes, and marketing site templates. Every shipped protection's help page auto-requires its "does NOT protect against" section (parity bot). Isolation Card data-driven from measured suites (P4/P14/P35 outputs) — *the disclosure surface is a test artifact, so it can't drift from reality.*

## 9.12 Phase security acceptance criteria (per S0/S1 phase — the "security-specific acceptance" the brief demands)

| Phase | Security DoD addition beyond tests |
|---|---|
| P4–P6 | ADRs reviewed by Security lead; resolver totality property proven; contract "narrow surface" checklist signed |
| P10 | Update server red-team (P10-T9) closed |
| P11–P13 | List-fleet 10⁹ fuzz before stable; BlockEvent carries no content; redaction schema proof |
| P14 | Cross-identity process assertion in CI; promotion/purge FS-diffs; papercut census w/ Security sign-off on every "accepted shared state" row |
| P15–P16 | Deny-store corruption fuzz; OHTTP capture proof; interstitial bypass-friction audit |
| P17–P20 | Leak matrix per feature; seed-derivation audit (no PII inputs); fail-closed drills |
| P21 | Chokepoint bypass audit (reflection); sideload forgery negatives |
| P22–P26 | Preview-leak posture documented; import-fs residue test; quarantine E2E ×OS |
| P27–P30 | Audit + addenda; K1 memory-inspection suite; ceremony fuzz; backup restore drill |
| P31–P33 | Tor/WG profiles green; conformance artifacts; UV-bypass matrix |
| P34–P35 | Split focus-spoof suite; promotion data-copy audit; letterbox side-channel measure |
| P36–P39 | Pen-test P0/P1 closed; rebuild attestation published; a11y *of security UI* external sign-off |


## 9.13 Privacy guarantees (binding, machine-checkable)

1. **No telemetry leaves the device without opt-in**, and the local viewer shows byte-accurately what would be sent (extended to crash reports verbatim).
2. **No account is required for any feature — and XR operates no account system at all**; nothing about the user is knowable by RRRTX by design, not by promise (the *endpoint-audit diff* §11.8 proves which servers a shipped build can even speak to; §13.8 defines the change procedure for that set).
3. **No page content, URL, hash, or file byte crosses the network** except through a per-feature, inline-disclosed, user-consented action (search, translation, VT-link, SB OHTTP lookups via hash-prefix protocol, update check) — each named in the published endpoint set (§9.13) and asserted by P19 probes.
4. **New Tab Page performs zero network requests** beyond the user's own chosen search interaction (CI packet-assert, inherited design-system rule).
5. **No ads, rewards, tokens, sponsored tiles, or feeds — permanently** (DR-22); copy lint + build-flag scan enforce at release.

---

# 10. UX/UI IMPLEMENTATION MAPPING

**Binding design system:** the XR Design Language (UI/UX Spec, inherited via Specs A/B/C) is *the* design source of record — tokens (§8), components (buttons/toggles/chips/lists/sheets with SR contracts), motion rules (≤320 ms + reduced-motion), spacing, focus rings, dark-mode discipline — with the amendments all three specs ratified: 4-screen onboarding cap, Attention Budget tiers, 4+2 themes, no "coming soon" rails, mixed-split permanent identity chips. **This section maps its surfaces to the engineering plan; where UX and architecture disagree, §1 wins and Design fixes the UX (not vice versa) — recorded as an ADR.**

| UX surface | Phase(s) | Owning track | Key architecture notes / gates |
|---|---|---|---|
| Onboarding | P37 (exists as skeleton P7) | E | 4 screens; import step drives real importers; no tours after; <60 s study metric |
| Browser shell / chrome tiers | P7, P8 | E | ≤9 Tier-1 controls; identity pill + trust dial + shield chip slots; ≤96 px default / ≤40 compact / 0 focus |
| Tabs (top) / vertical / rail | P22 | E | one layout engine; identity marks in *every* layout (visual CI); Chrome-146-parity layouts as floor, *identity-aware* as differentiator |
| Tab groups | P22 (B) | E | cannot span identities (P14 move-law) |
| Tab search | P22-T4 | E | exemplar task; ≤60 ms @1k |
| Workspaces | P23 | E | org-only; hidden until 2nd; session store v1; never a security claim |
| Split view (same-id → mixed) | P23→P34 | E | focused-pane-owns-toolbar rule; mixed gated by 12-user study |
| Focus View | P34 | E | explicit entry; security UI always wins; 3 recovery routes |
| Compact mode | P22/P34 | E | chrome-preserves-URL-identity-trust (never strips security signals — the "clean look" temptation is a law) |
| Sidebar | P34 | E | panel host only; no second truth-source |
| Command palette / shortcuts | P7 (+everything registers) | E | budgets 50/150 ms; every capability = command (CI) |
| **Shield UI** (chip, per-site toggle, "why blocked") | P13 (engine P11) | D+E | chip count = the only passive counter; exception scopes w/ expiry |
| **Security Center → XR Panel·Site tab** (TLS, isolation card incl. *what is not isolated*, permissions) | P13–P16, P35 | E | Isolation Card = generated from measured matrices — not prose |
| **Tracker Observatory** (Panel·Site/Activity views) | P13 | D+E | 2k ring; categorize by list provenance; export redaction |
| **Network Firewall** (rules UI over Shield) | P34 (engine P11) | D+E | deliberate sub-dialog authoring; usage counters; no separate engine |
| **Extension Guard** (install review, per-identity grid, update diffs, egress log) | P21 → P34 | D+E | outcomes-as-copy; pre-set safer; friction attractor on `<all_urls>` |
| **Vault** (xr://vault: list/detail/capture/prompts/lock state) | P27 (mediation) → P29 | C | locked = full replacement; hold-to-reveal; countdown ring on clipboard clears |
| **Identity switcher / pill popover** | P14 | E | name·route·counts; new-window/disposable/tor entries; "manage" → xr://identities |
| **Containers** (word resolves to Identity in palette) | — | — | *vocabulary is law* (§1.4): palette alias, docs never introduce "container" as second concept |
| **Disposable sessions** | P14 | B+E | amber dashed window border; close-purge proof in docs; zero-disk law surfaced |
| **Tor** | P31 | D+E | states incl. **Failed w/ recovery card** (no dead "Disconnected" — Brave's documented failure avoided); non-dismissible disclosure; violet border; circuit viewer + "new circuit for this site" |
| **VPN/WireGuard/config import** | P32 | D+E | one-screen conf paste; "XR does not operate servers" copy; exit-label = user metadata |
| **Network tab / status strip** | P17–P19 | E | route+resolver+latency live; **offline/stale states explicit**; strip auto-enables at 2nd identity/any routing (design-system rule) |
| **Tools: Universal search UX** | P24 | E | bang hints (teach-on-use once); suggestions OFF default w/ per-engine opt-in |
| **Bookmarks / pins→Highlights / reading list / notes** | P25 | E | ledger-backed; honest anchor-miss state; no chrome added |
| **Downloads (manager UI + verdicts)** | P26 | C+E | quarantine copy = facts+actions; VT-link-only |
| **Screenshot tools** | P25→P34-T10 | E | redact = destructive (tested); capture-blocked during hold-to-reveal |
| **Reader mode** | P25 | E | typography controls theme-aware; never a fork of distiller |
| **Translation** | P34-T7 | E | provider named inline *before* send; default-off; per-origin memory |
| **Performance tools** | P34-T9 | E | Task-Manager re-skin + identity aggregation; no new telemetry stack |
| **Developer mode / DevTools XR panel** | P34-T8 | G | read-only domain; no DevTools patches |
| **Settings** | P8 (v0) → P30 (full IA) | E | search-first, deep-links, every section = command + help anchor; no forked upstream page |
| **Themes** (built-ins + custom framework) | P8 → P30 | E | loader validates contrast, refuses failures; declarative-only law |
| **Help / threat-model browser / diagnostics** | P37 | E | per-feature "does NOT protect" mandatory; diagnostics export redacted |
| **Accessibility program** | P36 (+every phase gates) | G | SR contracts for *security* flows specifically (prompts, dial, isolation card, vault) |
| **Localization** | P36 | G | RTL from day one; security copy human-reviewed per locale |
| **Migration / import UX** | P37 | E | loss-report honesty UI; extension-import → Guard queue (never auto-enable) |
| **Update / about / failure states** | P10 | A | visible failed state w/ manual download; build hash + sig status on About |
| **Crash / recovery UX** | P37-T5 | E | card never modal; per-identity summary; safe-mode after loops |

**Attention Budget is a UI *system*:** every row above that interrupts must declare its tier (T0–T5) in the component registry; the ledger service (P8-T6) counts and demotes overflow; design's per-release audit (§17) checks ceilings with local counters (never uploaded).
# 11. TESTING & VERIFICATION SYSTEM

**Governing principle (the brief's, restated as engineering law): a feature is not complete because it compiles.** Completion = the named CI artifacts linked in that phase's DoD record. "Green" is machine-defined (§17); human judgment sits only at studies, audits, and claims review.

## 11.1 Unit tests
Chromium-gtest for `//xr` C++ (all subsystems; resolver at 100% branch + mutation ≥90%); Rust `#[test]` + property tests (vaultd format — KAT vectors + corpus; seed derivation determinism; list-bundle parsing), Go (wgd conf/key lifecycle), TypeScript+Vitest for every WebUI component (state snapshots; label/a11y assertions baked into component tests, not only E2E). Contract fakes are *shared* with subsystem teams — a subsystem that tests only against its own stub is not done.

## 11.2 Integration (browser tests)
P9-harness over `browser_tests`: navigation×policy matrices (per-site trust ×identity × exception state), permission state machines, prompt/attention tier behavior, bookmark/history/ledger cross-scoping, import loss-reports, update-client state machines against P10 test server, session restore (kill each process type). Golden-file driven so *fixtures are the spec* (corrupt-prefs and corrupt-store fixtures mandatory per S0 store).

## 11.3 E2E
Palette→action flows across every shipped feature (headless where possible, headed on mac for keychain/notary realism), onboarding completion incl. importers, split focus ownership, vault capture/fill round trip on real target sites in a sandboxed local harness (public staging mirrors of login flows; no production bank sites in CI — legal), extension install→grade→revoke→delete (fixture extensions + CWS-live subset run *nightly outside PR gate*, breakage filed not blocking).

## 11.4 Isolation matrix (the signature suite)
Every **pair of identities** (incl. ephemeral, Tor-template-offline, promoted) × **mechanism**: cookies (3P/1P/CHIPS), localStorage, sessionStorage, IndexedDB, Cache API, ServiceWorker registrations + push subscription state, Blob storage, Quota, BroadcastChannel, SharedWorker, MessageChannel-to-opener, `window.name`, favicon cache, HTTP-auth cache, downloads metadata, notification prompts + granted origin state, clipboard (permission-level), HSTS/expect-CT visibility, TLS session resumption ticket reuse, DNS cache observable, GPU texture side channel (documented, not asserted-closed), permission overlay rows, autofill/vault scope, extension availability state. Result = **PASS / FAIL / DOCUMENTED-EXCEPTION**; a new exception requires a §1.13/§9.1 disclosure row in the same commit (CI). Adversarial mode: 50 tabs × 5 identities, cross-navigation attempts, `window.open` relations, tab-join (drag), restore — with process-attachment assertions from `chrome://process-internals` parses. Runs per promotion + nightly.

## 11.5 Vault suite
KDBX golden corpus round-trips (byte + logical, vs KeePassXC CLI + KeePass reference both directions, incl. upgrade paths 3.1→4.x); KATs (Argon2id params, AEAD, HMAC-block); wrong-password/corruption/truncation = never-destructive; lock/unlock races (IPC storm fuzzer); memory inspection (attach+dump while locked: no plaintext/key; sanitizer builds); clipboard auto-clear timing; **full autofill attack suite**: cross-origin fill, nested/sandboxed/opaque iframes, clickjacking (focus-delay), redress (fill-menu + navigation race), IDN-homograph lookalikes, `about:blank`/`view-source:`/PDF-container fields, capture-prompt manipulation; recovery-kit ceremony with naive users (manual, recorded); fuzz floors (format+IPC 7 d/week permanent).

## 11.6 UI/a11y/copy
axe-core gates (waiver registry with expiries); AXTree snapshots per novel surface; keyboard-only completion of the 12 core tasks; SR passes (NVDA/VoiceOver/Orca) on security surfaces (prompts, dial, panel, vault, split headers) *every release*; visual regression (Gold) across themes × layouts × identity marks; RTL + pseudo-locale builds; **copy lint** (banned vocabulary §9.11; intent-claim patterns; "no score" numeric-similarity check) — *accessibility and honesty failures block the release exactly like a crash would*.

## 11.7 Performance budgets (CI-enforced, regressions = release blockers)
Cold start ≤ Chromium-same-build +10%; NTP→interactive ≤300 ms; palette ≤50/150 ms; panel open ≤150 ms; identity switch ≤200 ms; filter decision p99 ≤1 ms/request, memory ≤80 MB (default list sets; shared-engine posture per §8.2); per-idle-identity ≤40 MB, ≤5 active w/ hibernation (P14); farbling ≤4 ms first-read; 500-tab scroll 60 fps mid-tier; Speedometer/MotionMark/JetStream within 3% of same-milestone Chrome; leak-suite and fuzz runtimes inside §4 ceilings; `perf-budgets.json` in repo, service asserts, delta published per release (a budget raised = an ADR + design sign-off, never a silent edit).

## 11.8 Privacy & leak tests (automated, published)
xr-leaktest matrix (§4 P19): routes × probes; plus **endpoint audit** per release: full-traffic capture on fresh profile + after import + after each S0 feature toggle flip ⇒ *set of contacted hosts must equal the documented set exactly* (diff blocks release); zero-default-telemetry proof; crash-upload absent unless opted-in; DoH/OHTTP posture capture-verified; NTP/geo absent proof; search-suggestions-off proof.

## 11.9 Extension compat & update-diff QA
Top-100 CWS corpus (install/run/revoke/permission-diff/uninstall) nightly-soft / gate-at-promotion; DNR-heavy adblocker coexistence test (uBO Lite + native Shield = no double-block perf collapse); password-manager-extension × XR autofill conflict suite; guard chokepoint fuzz; MV2-sideload attempt = clean refusal w/ explanation (evidence R5's DROP is *implemented*, not accidental).

## 11.10 Crash / restart / recovery
Process-type kill matrix under load (browser/renderer/network/vaultd/tord/wgd/inspect/gpu) w/ session-restore correctness, ephemeral-zero-residue post-crash (FS-diff), fail-closed route behavior on helper death, no identity bleed on restore, crash-loop safe-mode, update-interruption drills (kill mid-payload per OS). Metrics: beta cohort crash-rate ≤1.2× prior stable (auto-halt wired).

## 11.11 Upgrade / downgrade / migration
`xr-schema` property suite: every historical schema version migrates (fixtures per version *frozen at first use*); bundle formats (session, workspace export, backup) read by newest and *tolerate-unknown* round-trip; **downgrade posture:** older builds must refuse-newer data cleanly (never corrupt); updater: staged→halt→resume→rollback matrix per channel; policy-forced settings survive upgrades; KDBX file written by newest opens in KeePassXC then edited there → back to XR (three-way).

## 11.12 Compatibility
WPT pass-rate parity vs Chrome stable & beta (delta ≤0.5%, tracked per promotion, expectations diffs reviewed); top-500 global + 200 regional corpus w/ visual+console+login-flow smoke; 50 hard apps (Google Workspace, Teams/Meet-class, Figma, Salesforce, two bank sandboxes, web-cam conferencing incl. WebRTC policy interplay, PDF viewer, printing) *manually scripted where automation can't*; media codec matrix (H.264/HEVC/AAC/VP/AV1 feature-detect honesty; Widevine path when LG-3+installed); WebAuthn matrix (platform, hybrid, security key); per-trust-context variants of the corpus (Fortress breakage documented as *expected-and-listed*, not hidden).

## 11.13 Fuzzing program
Permanent CI fleet (ClusterFuzzLite in-repo): filter list+bundle parser, KDBX reader/writer, tord/wgd IPC + control parsers, inspect archive/binary, theme/settings bundle parsers, *all* Mojo contract surfaces via P9-T8 harness, farbling seed input space, importer DB parsers. Regressions from findings = `SEC-*` tests (§9.9). Campaigns: 72 h before each gate; 10⁹ exec milestone recorded per release (Spec-B's bar adopted).

## 11.14 What cannot be automated (named, staffed, scheduled)
SR/keyboard human passes (P36 + per-release sampling), 12-user studies (identity comprehension — §17 gate; mixed-split gate; recovery-kit ceremony), pen tests (P38 + annual), red-team leak weeks, phishing-corpus *freshness* review, Widevine/streaming service real-world checks, captive-portal/hotel/conference field days, enterprise-policy interop with MDM vendors, theme-gallery curation QA (post-GA), and every §9.11 *claims* review. All get named owners in G + F; findings land in the same evidence store as CI links.

## 11.15 Evidence standard (mechanical)
`evidence.json` per phase DoD: `{suite, run_id, commit, artifact_url, verdict, links}`. The §17 gate checker reads registry rows × evidence records × budget files and *computes* readiness; no human may edit a verdict without an attached ADR. This is what "proven, not declared" means in this project.

---

# 12. CHROMIUM UPSTREAM & MAINTENANCE STRATEGY

Designed for a decade, not a demo. The failure mode of every Chromium fork is *divergence debt*; every mechanism below attacks it.

## 12.1 Cadence (R9)
- `xr-core@main`: **daily** rebase onto Chromium canary (bot). Conflicts ⇒ auto-issue to owning team with context (§4 P3-T2); the queue is the *truth* of fork health, public.
- **Shipping lines:** follow the 8-week Extended-Stable-equivalent (even-milestone) series — user-visible promotions ~6–7/yr; between promotions, *security-only* builds cherry-pick from Chromium's weekly (pilot: twice-weekly) security tags **without milestone promotion**. Beta-tracking job runs compat early (R9 note #6).
- Never pause the bot for deadlines; never merge a feature branch onto an un-rebased tip.

## 12.2 Patch organization & documentation
Manifest `patches/manifest.yaml`: `{id, files[], category, owner, risk(S0..), upstream_bug?, rebase_notes, retirement_plan}` per patch file (`patchinfo` pattern, Brave-validated). Categories + budgets per §1.2; count **published in every release note**; new patch PRs must include retirement plan (hook→upstream-issue→delete someday, or "permanent product surface" w/ justification). Tooling: `xrctl patches audit` (drift, orphans, budget), CI-blocks unregistered diffs in `src/` outside `src/xr`.

## 12.3 Merge strategy & conflict handling
Rebase-merge onto pinned chromium rev; conflicts resolved in *patch semantics*, never by dropping hooks ("disable & TODO" is forbidden — a patch that can't be carried is *retired with a user-visible consequence* + review entry). Component-level upstreams (adblock-rust, keepass-rs, Arti, wireguard-go) update via pins + `cargo vet` diff reviews; breaking upstream API changes: **vendor-and-pin for max 2 promotions, then adapt or replace** — no immortal forks of other people's repos unless the *Decision Register* says otherwise.

## 12.4 Security-fix consumption & assumption protection
Security fast-lane (P3-T5): 72 h critical/IIT / 14 d high SLA from *tag publication*; drill twice/year synthetic; missed window ⇒ feature freeze (§15 R1's kill-switch — Spec-A/B's rule, kept). **Upstream-assumptions suite:** XR depends on behaviors upstream may change — Site Isolation partition-suitability rule, `GetStoragePartitionConfigForSiteInstance` contract, per-partition NetworkContext, HCMS mediation points, extension dispatch funnel, component-updater signature path, Safe Browsing v5 mode APIs. Each gets an *assumption test* (asserts the invariant holds in *this* Chromium rev) that runs per rebase; failures = P0 to the owning team *before* the promotion lands. This is how XR "verifies patches haven't broken Chromium's security assumptions" in both directions.

## 12.5 Anti-divergence program
Metrics published per promotion: patched-file count (budget meter), **seams retired** (upstreamed/obsoleted patches — the reward metric; Spec-A's law "every upstreamed patch is one we stop maintaining"), WPT delta, crash-rate vs Chrome, SLA adherence. Upstream-first register: cosmetic hook, partition-config ergonomic improvements, farbling-surface standardization interest (tracking only, don't bet on adoption), Guard's `Dispatch` consult (candidate for a native extension-availability policy API — the *right* long-term fix is upstream; a proposal lands in Chromium design review once our shape is battle-tested), `xr-schema` lessons into prefs. Maintained relationships: adblock-rust (upstream everything that isn't product-specific), Arti (embedding-API feedback loop — their explicit goal), Tor leak-test methodology review by community experts, Mozilla translation-adjacent (network only — Bergamot *as a running service* is our fallback if users demand offline).

## 12.6 Per-train review & the MV2 clause
Every promotion: patch-by-patch "still necessary?" checkbox on the S0 list; MV2 re-check (evidence clause: if upstream *re-introduces* an MV2-compatible seam AND demand persists AND uBO-class need resurfaces — all three — it's a registry amendment, not code); DNR caps re-check (moot-but-cheap). This is Spec-C's "MV2 removable if liability" instinct generalized to *all* patches.

## 12.7 Never-list (contractual)
V8 internals · sandbox internals (tightening-only) · Mojo core · DevTools internals · cert verifier · Origin Trials/field-trial *machinery* (only endpoints re-pointed) · enterprise policy engine internals (XR adds providers, not forks). Any PR touching these needs a board-level exception — none planned.

---

# 13. CI/CD & RELEASE ENGINEERING

## 13.1 Pools & pipelines
Self-hosted builders: 3-OS signing-capable agents (Linux x86-64 + arm64, macOS x86-64 + arm64, Windows) sized for *daily canary rebases × 3 OS × debug/release* + per-PR subset builds; Rust/Go helper lanes (fast, containerized); bench fleet (fixed HW list `docs/hw.md`, thermal-locked, camera'd for visual); fuzz fleet; pcap-safe leak lab (VLAN-isolated). CI-as-code in `ci/` (no GUI pipelines). PR tiers: tiny (tooling/docs) = subset; UI = subset+visual; S0 paths = full relevant suites + dual-review label gate; release branches = everything, always.

## 13.2 Repository checks per PR
fmt (clang-format rustfmt prettier), lint (§9.8), type/strict checks, unit+integration subsets, **license gate** (GPL in link graph = fail), DCO, patch-manifest diff validation (budget meter), evidence-format check, dependency-graph lint (§7.2 import law), help-parity bot (registry↔docs), and *auto-generated dependency links* (issue metadata ⇒ graph — prevents §3 from rotting).

## 13.3 Chromium build validation
Per PR touching `//xr` that can affect the browser: compile matrix (Win/Linux debug+release; mac release) — full chromium on *nightly per rebase* (P3) + per promotion; component builds (vaultd/tord/wgd/inspect) per-PR always; **assumption-suite** (P12.4) in nightly-rebase job; sanitizer/ASan bot builds + fuzz smoke nightly.

## 13.4 Platform packaging
Windows: per-user default (auto-update via task) + per-machine MSI (enterprise); SmartScreen reputation program tracking (started P10); signing in HSM. macOS: Developer ID + notarization + staple, dual-arch (universal) dmg/zip; hardened runtime; *updater helper per in-tree conventions*. Linux: signed deb/rpm repos + AppImage (embedded update metadata) tier-1; **Flatpak tier-2** with an explicit capability note (nested sandbox interactions w/ our helper processes and keystores are distro-specific; supported = "known constraints" doc, not silence — §0.2#5); Arch/others community-maintained with our CI fixture tests. **Linux keystore fragmentation:** auto-detect Secret Service/KWallet; absent ⇒ documented password-only mode with an honest banner in settings (no silent DPAPI-less crypto theater).

## 13.5 Channels & rollout
nightly (dev, test-signed, *never for users*), beta (opt-in, real-signed, crash-halted auto-rollout), **stable** (staged 5→25→50→100 with kill-criteria numerics wired to opt-in crash stats; auto-halt + human resume w/ written reason), security-series builds on top of stable between promotions (patch-number bumps — R9 policy), enterprise "XR Security Series" (8-week base w/ 6-week extended backports mirroring Extended-Stable semantics, offered in the policy pack P39-T4). Rollback: full-version + epoch-key revocation; "update failed ⇒ manual download path" UX verified per release (P10 drill).

## 13.6 Release verification & artifacts
Every stable: signed artifacts (all formats) + SHA256 + minisign/sigstore attestations + **rekor transparency entry**; SBOM (CycloneDX) + license report + consumed-upstream-CVE table (from P3-T6) + `evidence.json` bundle + leak report + rebuild-instructions hash; external-builder reconciliation (P38-T4 program); announcement links *evidence*, not adjectives. Emergency: out-of-band runbook rehearsed annually (P9.10).

## 13.7 Reproducibility posture (honest, sequenced)
Rung ladder, each rung an *artifact*, none promised beyond current: **R0** pinned inputs (toolchain digests, build cmd exactness, docs) → **R1** deterministic *XR-owned* targets (helpers, vaultd, wgd, lists tooling — bit-identical reproducible *now*, tests enforce) → **R2** reproducible packaging (installer layout determinism) → **R3** independent rebuild reconciliation w/ delta explanations published per release → **R4** chromium-wide bit-identical = **never promised; reviewed annually** (Spec-A DR-21 preserved verbatim).

## 13.8 Diagnostics/crash policy
Default: none leave the device. Crash upload = opt-in, per-report local preview (viewer), client-side scrub (URLs→origins-only, paths→redacted, K1/K2 zero), retention ≤ 90 d (self-hosted), IP-logging-off config, no user IDs. Product-metrics opt-in aggregate (schema published in repo; local counter export "show me"). Updates/check-ins = signed minimal (cohort, version, install uuid) — listed in §9.13's documented endpoint set; **any new default endpoint requires: ADR + threat-model row + leak-suite allowlist update + help-page line** (CI enforces all four exist).

---
# 14. ENGINEERING GOVERNANCE — THE XR LAWS

Permanent rules for contributors and coding agents. Binding; CI or gate enforces wherever an enforcement column exists.

| # | Law | Enforcement |
|---|---|---|
| L1 | **Never invent cryptography.** Primitives and envelopes only from the §8.4 allow-list, via the pinned libraries. | dep-graph lint + S0 review checklist |
| L2 | **Never weaken Chromium's security guarantees for a feature.** Sandbox, Site Isolation, Mojo validation, CORB/ORB, prompt plumbing: configure, never degrade. | assumption-suite + dual review |
| L3 | **One policy resolver.** No subsystem holds private mode logic; unknown/absent policy ⇒ *deny*, never guess. | clang-tidy custom check |
| L4 | **Interfaces before implementation.** Cross-boundary APIs live in `//xr/mojom`, versioned, RFC-amended, with fakes — no side channels, no reflection, no "temporary" direct includes (§7.2). | import-law CI |
| L5 | **Security claims require evidence.** Every claim maps to a suite artifact or is reworded. Banned-vocabulary lint is the floor, not the ceiling. | evidence checker (§11.15) + copy lint |
| L6 | **Fail visibly or fail closed — never silently.** Degrading security posture = amber state + ledger row; route loss = stop, not reroute. | behavior tests per phase |
| L7 | **Least privilege by default; friction is a feature.** T5 confirmations, typed domains, hold-to-reveal, deny-by-default capabilities; the *absence* of friction needs review, never its presence. | design gate (F) |
| L8 | **No feature without tests, no tests without the checker being wrong-proof.** Every suite ships a canary that proves it fails. | P9-T4 |
| L9 | **No dependency without a completed evaluation:** current status, license (link graph!), health/bus-factor, security posture, maintenance burden, alternatives, exit plan, owner. Vendored + pinned + vetted. | P1-T8 form + CI license scan |
| L10 | **No unnecessary Chromium divergence.** Patch budget is law; hooks over in-lines; "upstream or delete" per promotion; every patch has a retirement plan. | patch ledger + budget meter |
| L11 | **No completion claim without verification.** "Done" = linked artifacts in `evidence.json`; prose in PRs has no standing. | gate tool |
| L12 | **UX complexity must earn its pixels.** New always-visible surface = usage-data justification or it stays in palette; Attention Budget ceilings are code. | F-track review + tier ledger |
| L13 | **Security-sensitive code (S0/S1 paths) = dual senior review incl. Security team**, written intent note, updated rebase notes. | CODEOWNERS + CI labels |
| L14 | **Contracts are documented or they don't exist.** `docs/contracts/` regenerated from source; schema changes ship migrations. | docs CI |
| L15 | **Local-first by construction.** Page content, URLs, hashes, file bytes never leave the device except through a documented, user-visible, per-feature consent (and never to XR). | endpoint-audit diff (§11.8) |
| L16 | **No hidden telemetry, no accounts for core function, no feeds, no ads, no tokens.** Permanent. | build-flag + endpoint scans |
| L17 | **Users can always leave.** Formats (KDBX, lists, ledgers, exports) are documented and round-trippable; lock-in features are rejected at design review. | interop tests |
| L18 | **Respect users' machines.** Performance budgets, hibernation defaults, memory ceilings, bounded logs — "great feature, unusable laptop" is a rejection. | perf budgets CI |
| L19 | **AI-free boundary.** No assistant/copilot/agent/chat/LLM surface anywhere; the only permitted adjacent capability is the §0.1-R7 translation utility, non-conversational, disclosed, offline-capable. | feature lint + copy review |
| L20 | **Rebase is oxygen.** No release, deadline, or demo outranks the SLA; a missed window twice in a quarter freezes feature work. | §12.4 kill-switch |
| L21 | **Honesty in naming.** Profile/Identity/Workspace/Ephemeral/Trust (§1.4) mean exactly their definitions in code, UI, docs, marketing. "Container" survives only as a palette alias. | vocabulary lint |
| L22 | **Incidents are published.** Post-mortems for security and user-impact incidents ship redacted-of-persons, always with what-we'd-have-caught-it-sooner. | release gate checklist |
| L23 | **Every phase ends by feeding the next:** artifacts updated, contracts bumped, registries synced, limitations page re-measured. Phases don't "clean up later." | DoD checker |
| L24 | **Agents follow humans' contracts.** Coding agents (and new engineers) work from issue text + this document; inventing new seams/patches/interfaces is out-of-scope by definition — raise an RFC instead. | PR template + triage bot |

---

# 15. RISK REGISTER & RECOVERY PLAN

| # | Risk | Prob. | Impact | Early warning | Mitigation (binding) | Fallback | Owner |
|---|---|---|---|---|---|---|---|
| 1 | **Rebase debt / SLA slip** — the fork killer (Thorium-shaped; R9 doubles upstream pace) | High (structural) | Fatal for a "security browser" | patch-conflict queue age > 3 days; promotion drill person-hours trending up | overlay+pin model; budget meter; daily bot; ≥2-eng platform team; 8-week shipping rhythm (R9) | ship "XR Security Series" on Extended-Stable cadence; freeze features until green | A lead |
| 2 | **Identity seam hits fatal papercuts** (R2 risk) | Med | High (moat weakened) | P4 spike findings list; papercut census grows in P14 | ship-identity-per-window fallback (pre-designed P4-T9); papercuts budgeted not discovered | identity = BrowserContext per window; mixed windows move to P39 register w/ evidence | B lead |
| 3 | **Vault bug with real credentials** (data-loss or leak) | Low-Med | Existential | fuzz findings; interop-matrix flakes; audit interim report | P28 ownership of writer + golden corpus; audit gate; K1 tests; "drop to P27 store" rollback path | published incident + export tooling + hard freeze on vault scope | C lead |
| 4 | **Tor/WG leak in the wild** | Med | Very high (reputation) | field-test anomalies; bounty intake | leak-suite CI gate ("Tor ships only green"); fail-closed + helper isolation; annual re-audit of leak-case registry | disable remote-egress routes (policy kill switch) + published advisory | D lead |
| 5 | **CWS breaks forks harder** (install channel) | Med-High | High (extensions = #1 user complaint) | P21-T7 monitor failures | sideload + XR Verified catalog *kept warm from P1* (DR-13) | status copy + curated fallback + upstream advocacy | B lead |
| 6 | **Safe Browsing license posture** (LG-2) | Med | High (phishing claims hollow) | legal re-review cadence | local-list + OHTTP (Google-operated relay, no XR infra); switchable; docs | list-only third-party feeds (URLhaus family terms — evaluate) / ship honest "SB disabled for terms" mode | A lead |
| 7 | **Widevine unavailable/unlicensed per platform** (LG-3) | Med | High (Netflix-broken perception) | legal verdict; user reports | P1 gate *before* any public build; opt-in download; explicit download-page disclosure matrix | "XR doesn't play DRM video — here's why + which services" page (never let users discover it) | A lead |
| 8 | **adblock-rust upstream drift / perf cliff** | Low | Med | pin-update diff reviews; perf budget trends | vendored pin + ±2% corpus gate; MPL license permits fork cheaply; Mozilla adoption = second consumer | short-term fork; long-term: fund upstreaming (register) | D lead |
| 9 | **Scope > team** (the chronic killer) | High | High (everything ships late & half-tested) | DoD evidence debt; SF slips | §3 critical path; no-skip-DoD law; feature-freeze triggers; registry-first intake (new idea = registry row + phase + owner *before* code) | cut *phase tails* (P34 split-mixed, P33, P39) — never cut contracts or gates | TL |
| 10 | **UI complexity — "96 px of confusion"** (identity/trust/split for normals) | Med | High | P37 study; dial-state recall; attention-ledger overruns | design-system tiering + teach-on-use + four-word rule; **§17 usability gates are hard** | simplify: dial→per-site toggle only; identities window-scoped (fallback already designed) | F lead |
| 11 | **Perf/memory regression (identities × processes × filters)** | Med | High | budget service reds; corpus soak drift | budgets in CI from P9; hibernation by default; per-identity accounting surfaced | raise caps w/ ADR; *never* disable a gate | A+G |
| 12 | **Cross-platform divergence** (keystores, signing, entitlements, Flatpak) | High | Med | per-OS suites failing selectively | §13.4 matrices + explicit degraded-mode docs; mac-notary/Win-rep programs early | ship tier-1 features per OS; publish capability table (honesty is a feature) | A |
| 13 | **Dependency abandonment** (any Rust/Go pin) | Med | Med | release cadence, open CVEs | P1-T8 evals w/ exit plans; vendored pins; max-2-promotion-adapt law (§12.3) | replace behind frozen interface (tord dual-engine proves the pattern) | owning lead |
| 14 | **Update channel compromise** | Low | Catastrophic | key ceremony anomalies; transparency-log diffs | pinned keys, HSM, staged+revocable epochs, transparency log, out-of-band docs | epoch revocation + forced manual path; incident runbook (P9.10) | A |
| 15 | **Media/legal pressure** (extractor-adjacent contributions, DMCA theories) | Med | Med | PRs/press questions | DR-16 posture documented; contribution policy bans circumvention *in this repo*; direct-media affordance lint is structural (no EME interaction) | remove affordance (isolated feature) w/ published reason | TL+legal |
| 16 | **Contributor/agent sprawl** (drive-by complexity, AI-agent code-salad) | Med | Med | PR-size trends; contract amendment attempts | L24 + RFC process + good-first-patch tied to patch *retirements*; CODEOWNERS; evidence-format bot | quarantine S0 paths to core team | TL |
| 17 | **Funding/timeline shock** (DR-01 regression) | Med | Fatal-to-plan | staffing gate review each SF | Stage gates are *also* stop-losses: P10 = hardened-Chromium-distribution MVP exists by then (list: rebase+shield+identity-lite+update = product value) | pivot to "XR Platform" (distribution + companion processes + upstream PRs), preserving roadmap for re-fork | principals |
| 18 | **Beta cohort trust collapse** (breakage storm at P38) | Low-Med | High | attention-ledger, breakage-triage SLA, crash-rate | cohort sizing + staged updates + remote disable *per feature* (component flags) | staged halt + per-feature rollback + publish the ledger | G |

---

# 16. COMPLETE EXECUTION ORDER

Dependency-based; no calendar fiction. "EB" = execution block; teams size them after P1 staffing, gates decide progress.

1. **EB-0 (P1):** stand up governance/legal/registry tooling. *Start here: today's work is the legal briefs (LG-1..3), threat-model v0, and the dependency-eval pack — not code.*
2. **EB-1 (P2+P3, parallel-heavy):** builds green on 3 OS nightly; rebase bot + budget meter live. **Gate G1:** two consecutive synthetic promotions + one 72 h drill; external contributor reproduces a build.
3. **EB-2 (P4 ∥ P5 prep):** identity-seam spike executes with its *own* exit (ADR-0042) — this decides the shape of half the roadmap; P5 authors contracts against both outcomes. **Gate G2 (SF-0):** contracts frozen + fakes usable; P4 verdict recorded (primary or fallback plan).
4. **EB-3 (P6→P7→P8→P9→P10, mostly sequential for 6/7, parallel 8/9/10):** the spine: resolver, registry/palette/chrome, settings/themes platform, the proof machine, and real release machinery. **Gate G3 (SF-1):** "XR nightly" is an installable, auto-updating, signed browser with the test infrastructure *already refusing things*.
5. **EB-4 (P11→P12→P13 ∥ P14→P15):** Shield and Identity become product; observatory and panel make them legible; permission firewall makes them governable. P13 waits on P11 events, P14 waits on nothing in P11 (parallel teams). **Gate G4:** first *dogfood-everything* build (SF-3, Internal Alpha row §17).
6. **EB-5 (P16 → P17→P18→P19 ∥ P20→P21):** protections on, per-identity network lands, the leak suite completes and gets published; fingerprint reduction and Guard ride alongside (P20 needs only P12 plumbing; P21 needs only P14). **Gate G5 (SF-4):** Public Alpha — feature-flagged, breakage pipeline hot, beta cohort eligible.
7. **EB-6 (P22→P23 ∥ P24→P25→P26):** daily-driver layer. No security engine changes; if EB-5 slipped, E-track *swaps internally* (P24 before P22) — dependency graph allows it (check §3: only P23→P22 session tie is hard). **Gate G6:** corpus perf/memory budgets green with all tab/workspace states.
8. **EB-7 (P27→P28→P29→P30):** credentials bridge, vaultd engine (its Rust workstream *began in EB-3 — parallel by design*), audited vault product, sync/backups/themes completion. **Gate G7 (SF-5):** audit addenda closed + Beta eligibility + P38 opens.
9. **EB-8 (P31→P32 ∥ P33→P34→P35):** Tor, WireGuard, passkeys (gated on P29/30), the mixed-split suite of interactions, Fortress realness. P31/P32 integrate only when their leak profiles pass; P34's mixed-split *ships only if* the 12-user gate passes — pre-agreed fallback applies otherwise (no debate, per §4). **Gate G8 (SF-6):** feature freeze; only P38-remediation merges.
10. **EB-9 (P36→P37→P38):** completion of access/i18n, onboarding/migration/help, the full assurance program (beta, pen, rebuild, studies, dogfood, RC evidence bundle). **Gate G9 (SF-7):** every §17 "Stable" row computable-green from `evidence.json`; usability gate passed (identity stateability ≥90% unaided).
11. **EB-10 (P39):** GA, public repo & community machine live, enterprise pack, long-horizon register opened with owners and entry conditions. Then the steady state begins: **daily rebase / 8-week promotions / 72-hour security / published everything.**

**Concurrency summary for a reader:** during EB-3: 6 tracks active; EB-4/5: all seven; vault-rust and tord/wgd engines run *inside* EB-3–6 windows as independent repos (that's the whole point of §7's topology); P36's external a11y work contracts in EB-6 to avoid end-loading; P38's pen-test firm books from EB-7 (audit-adjacent work shares context).

---

# 17. MASTER DEFINITION OF DONE

Each level = prior + its rows. **Verified by the gate checker** (§11.15) against §2 registry rows, §11 suites, §13.7 rung status, and F-track study records. Feature *counts* are not in this table; evidence is.

| Requirement | Developer Build | Internal Alpha | Public Alpha | Beta | Release Candidate | **Stable Production** |
|---|---|---|---|---|---|---|
| Scope gate | P1–P5 green (contracts+fakes) | + P6–P15 integrated (SF-1→G4) | + P16–P21 green (SF-4) | + P22–P30 (SF-5) | + P31–P35 (SF-6), feature freeze | everything except registry-DEFERs (which keep named phases) |
| Upstream health | builds nightly | rebase bot ≥90% green; published budget | 2 consecutive promotions ≤SLA | same + security drill | **4 consecutive promotions ≤SLA; zero open critical** | same, continuously; SLA metrics public |
| Compat | WPT run | ≥99.5% of same-milestone Chrome on WPT | ≥99% top-500 corpus | ≥99.5% top-500 + hard-apps triaged | ≥99% top-1k incl. regional; ≤0.5% FP breakage on Shield corpus | same + external QA confirm |
| Security suites | n/a | isolation matrix v1 green | matrix + leak(Direct/DoH) green | + proxy fingerprint paths | **all leak profiles (Tor/WG) green w/ published reports; fuzz floors met; SAST zero high** | + pen-test retest clean (highs/criticals) |
| Vault | fakes only | P27 real store green | P27 + vaultd pre-release | vaultd fuzz 7 d clean | **audit-cleared w/ addenda (sync, passkeys if enabled); K1 tests green; recovery drill pass** | same + no open high CVEs in vault surfaces |
| Perf/memory | n/a | budgets service live | within +15% | within +10% cold-start, all §11.7 rows ≤+5% drift | all budgets green on 8 GB-RAM tier too | same |
| A11y / i18n | CI harness exists | keyboard+axe gates live | en complete; RTL skeleton | +92% of 10 locales; **external SR pass for security flows** | same + waiver registry all dated | + human security-copy review all locales |
| Telemetry/privacy | none shipped | viewer live (empty-by-default proof) | endpoint-audit = documented set exactly | same | + beta metrics reviewed (attention-ledger ceilings honored) | continuously |
| Update/release | dev-signed | staging end-to-end | beta channel capable | staged+rollback drilled per OS | **RC: rebuild-reconciled by 1 external builder; transparency entries; SBOM+CVE map** | full external-rebuild program active; manual path proven |
| Documentation | ADRs current | threat model = shipped reality (bot-checked) | help parity bot green | limitations page current-to-this-build | audit reports published; disclosure process rehearsed (synthetic CVE exercised) | everything, published, honest |
| Studies/UX gates | — | — | dial-state recall ≥80% | **identity comprehension ≥90% unaided (12 users)**; breakage SLA <48 h median | mixed-split study verdict applied; recovery-kit ceremony 6/6 naive-success | + GA retro published |
| Public trust | — | — | public repo w/ CI evidence links | SECURITY.md + bounty live | transparency site (leaks, CVE map, rebuild notes) | + community governance operating (RFCs merged externally) |

---

# APPENDIX A — EVIDENCE LEDGER (verified 2026-09-07)

Claims marked **[VERIFIED]** in this document rest on the following primary sources / corroborations, checked during reconciliation research:

1. **Brave containers on Chromium (1.92, July 2026):** multiple independent outlets + Brave's own announcement/rollout notes; *containers share extensions, autofill, passwords, permissions, history* (Privacy Guides note) — the exact gaps XR's overlay stores close.
2. **`adblock-rust` cross-industry adoption:** Firefox 149 `third_party/rust/adblock` via Bugzilla #2013888 (experimental, off-by-default; corroborated by The Register, WinAero, multiple 2026 outlets incl. Russian tech press citing Bug 2013888); Waterfox + Perplexity Comet adoption; Brave's FlatBuffers memory work. License MPL-2.0; crate `adblock` on crates.io.
3. **Chromium process model & StoragePartition suitability (the identity-seam foundation):** `chromium/src/docs/process_model_and_site_isolation.md` — "two documents from different profiles or StoragePartitions can never share the same renderer process"; "StoragePartition (which may differ between tabs and Chrome Apps)" — fetched full text, quoted in §1.4.
4. **MV2 extinction timeline:** Chrome 138 disables MV2 everywhere (2025-07-24); enterprise policy sunset; Chrome 150 deletes first dev flag (2026-06-30); **Chrome 151 deletes remaining dev flags + MV2 machinery (2026-07-28)**; **CWS removes all MV2 listings (2026-08-31, now 7 days past)** — cross-corroborated by superchargebrowser/duskbyte/androidauthority/bumbletap analyses against Google's published timeline; the "flags workaround" comment (cyberinsider, July 2026) confirms forks relied on the deleted switches.
5. **Arti status:** Tor Project Arti repo: "full-featured Tor client … can connect to and run onion services … suitable for general client usage"; relay/authority still WIP (Aug–Sep 2026); Arti 2.6.0 released 2026-09-01 (congestion control + CGOpen always-on).
6. **boringtun health:** cloudflare/boringtun README restructuring warning; FreshPorts net/boringtun IGNORE/DEPRECATED history incl. "first and only release deleted from upstream."
7. **keepass-rs / KDBX-4.1 write maturity:** crates.io `keepass` 0.13.6 (MIT, active, MSRV 1.85, owners incl. louib); repo/docs: "experimental support for KDBX4.1 writing"; keepass-ng docs warn unparsed fields lost on save → writer ownership + golden corpus decision (R10).
8. **Chrome cadence change to 2 weeks:** Google announcement via 9to5Google/ghacks/Slashdot (2026-03-03; Chrome 153 = 2026-09-08; weekly security patches continue, pilots of twice-weekly; Extended Stable 8 weeks + 6-week backports); CEF #4114 "adjustments for two-week cycle" (even-milestone strategy, extended-stable alignment) — basis for §12.1.
9. **Disconnect lists license:** GitHub `disconnectme/disconnect-tracking-protection` LICENSE = CC BY-NC-SA 4.0; June-2020 blog announcement (paid commercial licensing offered) — R8.
10. **Bergamot/Firefox Translations sunset:** Mozilla support pages: add-on no longer updated/maintained, users directed to built-in (FF118+) — R7.
11. **Safe Browsing v5:** Google developers docs: modes Real-Time / Local List / No-Storage; **Oblivious HTTP Gateway** for IP privacy; API free for non-commercial, Web Risk for commercial — R6, LG-2.
12. **Widevine for forks:** chromium-dev thread w/ CEF author + Widevine team cc'd: free for *client* use via component-updater download, MLA only for licensing issuance; Brave's user-consent download model (brave-core wiki); Linux packaging nuance (FreeBSD ports split; `silvervine` 2026 helper for Mac/Linux) — R13, LG-3.
13. **Chromium Updater:** `//chrome/updater` in-tree cross-platform client, protocol 3.1 JSON, maintainer guidance for forks (chrome-updates-dev thread); server not provided → XR writes the tiny one — R11.
14. **Chrome vertical tabs GA (146, March 2026; broad rollout April 2026) with *no* workspaces/isolation:** superchargebrowser/itechguides/supasidebar corroborate; basis for §2.8 posture ("layout is table stakes; what the strip knows is the product").
15. **Thorium as fork-maintenance cautionary dataset:** abandoned-through-2025 then LTS-paced revival by a single collaborator, patch-series under `patch_scripts/` — §12/§15 inputs.
16. **Bitwarden incident record:** no vault breach; 2025 ETH-Zürich academic audit + low-severity XSS + April-2026 CLI npm compromise (vaults untouched) — confirms Spec-C's rejection of the "40M accounts" claim (audit.txt fabrications stay fabricated here; do not repeat them in docs or marketing — law L5).

**Open assumptions (named verification tasks, not hand-waving):** A1 `StoragePartitionConfig`-based mixed-identity windows survive the full papercut census → **P4** (fallback pre-designed). A2 Widevine component-updater availability for third-party builds on Win/mac/Linux → **LG-3 before P10 exit**. A3 SB API non-commercial terms cover RRRTX's distribution model (esp. enterprise pack) → **LG-2**. A4 Arti's bridge/transport completeness meets XR's Tor-user threat population → **P31 spike w/ C-tor fallback shipped same-phase**. A5 keystore coexistence with uBO-Lite/1Password double-fill conflict → **P27-T8/P21-T8 corpus**. Each assumption's failure has its mitigation already in §15.

---

# APPENDIX B — DECISION REGISTER (carry-forward; reopen only with written new evidence)

DR-01 funding gate for a fork (else hardened-distribution pivot, §15-R17) · DR-02 Chromium + overlay repo + canary-daily/8-week-promotion cadence + ≤150 patch budget · DR-03 adblock-rust native in network service; lists as signed data · DR-04 no GPL linked ever · DR-05 MPL-2.0 for `//xr` · DR-06 Identity-first vocabulary (Profile/Identity/Workspace/Ephemeral/Trust exact meanings; "container" alias-only) · DR-07 one policy resolver, total & deny-on-unknown · DR-08 three-position dial; Tor/Disposable = identities · DR-09 Tor networking ≠ anonymity, non-dismissible disclosure · DR-10 no operated VPN/sync/store/AV/threat-intel · DR-11 vault: sandboxed proc, KDBX-4 (XR-owned writer), zero custom crypto, published external audit as hard gate · DR-12 no AI assistant/chat/agent/LLM ever (sole R7 translation exception) · DR-13 CWS best-effort + warm `.crx`/XR-Verified fallback · DR-14 Widevine = user-consented download if legally clear; else disclosed absence · DR-15 Safe Browsing kept (Local-List + OHTTP; Enhanced never) per LG-2 · DR-16 no general extractor/DRM circumvention ever; direct-media only · DR-17 no MV2 revival (upstream machinery deleted 2026-07-28; annual evidence re-check) · DR-18 no scores, no intent claims, no anonymity vocabulary (machine-enforced) · DR-19 Attention Budget enforced in code · DR-20 network helpers = local SOCKS endpoints, never system tunnels/TUN/root · DR-21 reproducibility = provenance ladder, bit-identical never date-promise · DR-22 no default telemetry / no feeds / no ads / no tokens · DR-23 iOS out (Android = register, funded separately) · DR-24 Command Registry before features · **DR-25 Identity = per-WebContents StoragePartitionConfig seam (primary) w/ BrowserContext fallback by ADR-0042** · **DR-26 shipping cadence decoupled from Chrome's 2-week train (8-week promotions + 72h security line)** · **DR-27 Tor engine swappable behind xr-tord IPC; Arti default, C-tor fallback** · **DR-28 wireguard-go via local-SOCKS helper (boringtun rejected on maintenance evidence)** · **DR-29 SB = v5 local-list + OHTTP; no XR-operated proxy** · **DR-30 vault KDBX writer is XR-owned behind a golden-fidelity corpus (keepass-rs write path experimental upstream)**.

*End of the Master Implementation & Execution Plan. This document, its registries (`docs/`), and the `evidence.json` gates it defines are the single operational source of truth for building XR Browser.*
---

# THE FIRST 10 ENGINEERING ACTIONS

Concrete, today-and-next-week, executable under this plan. (These are §4 Phase 1–5 tasks in launch order.)

1. **Create `xr-browser` + `xr-core` repos** with MPL-2.0 LICENSE, DCO bot, CODEOWNERS (S0 path list per §7.2), `docs/adr/` + decision-register tooling; file DR-01..DR-24 equivalents as machine-checkable rows seeded from this document. *(P1-T1/T2/T9)*
2. **File the three legal briefs** (LG-1 fork viability & codec budget; LG-2 Safe Browsing v5 terms incl. OHTTP relay operators and Web Risk fallback; LG-3 Widevine per-platform redistribution) with named counsel and a hard answer-by date before any public build; record verdicts in the register. *(P1-T5)*
3. **Write `SECURITY.md`, embargo + disclosure + bounty-charter v0, and threat-model v0** (T1–T11 table incl. explicit out-of-scope rows); run one synthetic vulnerability report through the entire intake pipeline and fix what breaks. *(P1-T3/T4)*
4. **Stand up the build farm and bootstrapped `./build x`:** DEPS-pinned Chromium checkout + `xr-core` mount script + first patch-manifest entries (branding only) + GN argsets (de-Google flags, endpoints→staging); publish toolchain digest list; achieve three-OS nightly builds for 2 consecutive weeks. *(P2-T1..T9)*
5. **Turn on the rebase bot + patch-budget meter:** daily canary rebase job with auto-issued, owner-routed conflicts; budget ledger initialized (count must be small *by construction*); run one synthetic-conflict drill and one fake-72h security drill to prove the lanes, not just the scripts. *(P3-T1..T6)*
6. **Execute the identity-seam spike (P4) as a one-team timeboxed experiment** — partition-config per-WebContents, cross-identity process assertions, per-partition NetworkContext proxy/DoH binding, ephemeral zero-disk, papercut census with owners — and land **ADR-0042** choosing primary vs fallback identity model. *This is the plan's single highest-information action; do it before any other feature team starts.*
7. **Author and freeze `//xr/mojom` v1 + schemas** (PolicyResolver, Identity, Shield, RouteManager, VaultService, Guard, DownloadSafety, ActivityLog, Command descriptor, EffectivePolicy totals, list-bundle + update-manifest formats, Isolation-Card strings) **with fakes + fixtures**, run the narrow-surface review checklist per interface, and publish generated contract docs. *(P5-T1..T10)*
8. **Build the proof machine before product code (P9 core):** isolation-matrix runner (graduating P4 probes), xr-leaktest harness v0 with its canary self-tests, compat-corpus runner (start against Chrome beta *and* stable now that milestones land biweekly), perf-budget service with `perf-budgets.json`, fuzz fleet wired to CI with the P5 fuzz-required-per-interface rule.
9. **Start the Rust/Go engine tracks in parallel:** vendor `adblock-rust` + `keepass` pins under `cargo vet`; open `xr-vaultd`, `xr-tord`, `xr-wgd`, `xr-inspect` repos with CI, sandbox-policy sketches, and their first fuzz targets *on day one* (they integrate later, per §3, but their riskiest external bits — KDBX write fidelity, Arti embedding API, WG conf parsing — need burn time early); kick off the Widevine/Arti/keepass-rs dependency-eval refresh at 90-day cadence.
10. **Make release machinery real before any human outside the team installs a build (P10 v0):** HSM-backed signing hierarchy + ceremony doc, `//chrome/updater` client integration + `xr-update-server` first deploy (staging), sigstore/rekor transparency entries, SBOM attach, and a full rollback + kill-mid-update drill on three OSes in the VM lab — because a security browser's promise is, first and last, that we can *fix it fast*.

---
