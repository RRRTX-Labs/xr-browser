# LG-3 — Widevine CDM acquisition & redistribution per platform (Win/mac/Linux) — **DRAFT-FOR-COUNSEL**

- **Status:** DRAFT-FOR-COUNSEL (facts, sources, questions, options — no legal conclusions; the verdict is counsel's work, HG-1)
- **Date:** 2026-09-07 · **Prepared by:** XR Platform agent (P1, XR-P1-T5)
- **Linked register rows:** DR-14 (OPEN — Widevine = user-consented download if legally clear; else disclosed absence)
- **Linked assumptions:** A2 ("Widevine component-updater availability for third-party builds on Win/mac/Linux → LG-3 before P10 exit")
- **Why now:** Plan §4 P1: "T5 legal brief … LG-3 Widevine CDM redistribution per platform — each with a written verdict"; Plan §0.1-R13: "legal gate LG-3 must clear platform terms before P10 exit; fallback = honest download-page disclosure."

## 1. Questions for counsel

- **Q1 (client-use, no MLA):** The 2015 chromium-dev thread (F1) records the CEF author's understanding from talks with Widevine: CDM "available free of charge provided you download it from Google using Chromium's component updater"; an MLA is required only "if you plan to encrypt content and issue Widevine licenses"; "if your Chromium-based application is simply a client of other services like Netflix then you shouldn't need a license." **Is that understanding still valid in 2026 for a Chromium fork that (a) never bundles the CDM, (b) offers a user-initiated, explicitly consented download at first run of a DRM-protected stream, and (c) issues no licenses?** We request counsel's independent confirmation — we do not treat a 2015 mailing-list statement as current authority.
- **Q2 (Linux packaging nuance):** The Plan records a Linux packaging caution (Appendix A item 12: "Linux CDM cannot be repackaged freely — the FreeBSD ports split is the cautionary tale"). **What, specifically, does "cannot be repackaged" mean for our Linux distribution formats (deb/rpm/AppImage are tier-1, Flatpak tier-2 — Plan §13.4):** must the CDM be downloaded to the user's *profile* directory at first run (never shipped in any package, never mirrored by us), or is a first-party mirror of Google's CDN files permissible?
- **Q3 (Brave precedent):** Brave's user-consented download flow is the cited industry practice (Plan Appendix A item 12; the Plan also notes the in-tree mechanism: `enable_widevine`/`bundle_widevine_cdm`-class build flags, verified present in-tree as `ENABLE_WIDEVINE_CDM_COMPONENT` / `BUNDLE_WIDEVINE_CDM` — F4). **Is the Brave practice sufficient evidence of accepted industry usage, or does each fork need its own written confirmation from Google/Widevine — and what form should that confirmation take (email from a named Google contact? a current policy page citation?)?**
- **Q4 (disclosure obligations):** What consent language is required at the download prompt (per platform), and what disclosure is required if the CDM is *unavailable* on a platform — the Plan's fallback is an honest page: "XR doesn't play DRM video — here's why + which services" (Plan §15-R7: "never let users discover it"). We request review of the consent + failure-copy drafts at P10 (we will supply strings; P1 cannot supply them — the UX surface does not exist yet).
- **Q5 (terms-change scenario):** If Google/Widevine terms for third-party forks change per platform (or require per-distributor agreements), what is the minimal contractual path, and should the Plan's A2 gate (verdict before P10 exit) be treated as hard? (The Plan treats it as hard: "LG-3 must clear platform terms before P10 exit".)

## 2. Facts (sourced; all accessed 2026-09-07 unless noted)

| # | Fact | Source (URL) | One-line quote | Anchors |
|---|---|---|---|---|
| F1 | Widevine client-use vs. license-issuance distinction, recorded by the CEF author after talks with Widevine (thread cc'd the Widevine team) | https://groups.google.com/a/chromium.org/g/chromium-dev/c/16hDHEpgUb8 ("Widevine legal issues", 2015-10-15) | "1. The Widevine Content Decryption Module (CDM) is available free of change provided you download it from Google using Chromum's component updater. … 2. You must sign a Master License Agreement (MLA) with Widevine if you plan to encrypt content and issue Widevine licenses. … So, if your Chromium-based application is simply a client of other services like Netflix then you shouldn't need a license to enable Widevine support." (note: original wording "free of change" = "free of charge") | Q1 |
| F2 | Download-vs-bundle distinction for third-party applications | https://github.com/chromiumembedded/cef/issues/1631 | "The binary component used by Chromium, called the Widevine CDM, is a Pepper plugin that is downloaded on Windows and OS X via the Chrome component updater … **Automated download of the binary from Google is allowed but bundling of the Widevine CDM with third-party applications requires a license**." | Q1, Q2 |
| F3 | 2021 CEF/Alloy restoration of the component-updater path, with recent (mid-2021) Google communications quoted | https://github.com/chromiumembedded/cef/issues/3149 | "Recent communications with Google (mid-2021) provide the following responses … The CDM is normally bundled with a new Chrome installation process." and "widevine: Use component updater with the Alloy runtime … CDM binaries will be downloaded on supported platforms shortly after application startup." | Q1 (recency), Q3 |
| F4 | The in-tree mechanism exists and is build-flag gated (component download path + separate bundled path) — i.e., the "user-initiated download, never pre-bundled" design is expressible in-tree | https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/component_updater/widevine_cdm_component_installer.cc | Code paths `#if BUILDFLAG(ENABLE_WIDEVINE_CDM_COMPONENT)` (download) vs. `#if BUILDFLAG(BUNDLE_WIDEVINE_CDM)` (bundled) — the Plan's R13 ruling: "user-initiated, explicitly consented CDM download using the in-tree Widevine bundle-manager path (the Brave model), never pre-bundled" | Q1, Q2 (mechanism) |
| F5 | Plan's recorded evidence on the Linux packaging caution (FreeBSD ports split; community helper `silvervine` showing the user-initiated-install pattern live in 2026) | `XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` Appendix A item 12 (internal) | "Widevine for forks: chromium-dev thread w/ CEF author + Widevine team cc'd: free for *client* use via component-updater download, MLA only for licensing issuance; Brave's user-consent download model (brave-core wiki); Linux packaging nuance (FreeBSD ports split; `silvervine` 2026 helper for Mac/Linux)" | Q2 |
| F6 | **Live re-verification of the FreeBSD/freshports port page failed** — the specific freshports page is no longer published (404 on 2026-09-07, both `/security/linux-widevine-cdm` and `/www/linux-widevine-cdm`); the Plan's Appendix A record (verified at reconciliation) stands as written, but counsel should treat the *port-split fact* as "recorded in the Plan; live page removed" and confirm independently if the Linux nuance is decision-relevant | https://www.freshports.org/security/linux-widevine-cdm (404 on access) | — (page absent) | Q2 (evidence status: **UNVERIFIED-live**, recorded per P1 anti-fabrication rules) |
| F7 | Brave's widevine wiki page (cited in Plan Appendix A item 12) was not reachable in its recorded form on 2026-09-07 (GitHub wiki page 404); the Brave *model* is independently corroborated by F3/F4 + the active brave-core repo (MPL-2.0, pushed 2026-09-06) | https://github.com/brave/brave-core/wiki/Support-widevine-on-Brave-Linux (404 on access) | — (page absent) | Q3 (evidence status: **UNVERIFIED-live**) |

## 3. Our model, as it exists (for counsel's framing)

- Design (Plan R13, binding): **default OFF; user-initiated, explicitly consented download; never pre-bundled; disclosed download page**; the in-tree component-updater path is the mechanism (F4).
- Per-platform distribution: Windows (per-user default + MSI), macOS (dmg/zip, Developer ID), Linux (deb/rpm/AppImage tier-1, Flatpak tier-2) — Plan §13.4.
- The browser is a **pure client**: it decrypts content licensed by *content providers* (Netflix-class); RRRTX issues no Widevine licenses and hosts no DRM content.

## 4. Options with consequences (no recommendation — counsel's call)

| Option | Content | Consequences (as we understand them — counsel to correct) |
|---|---|---|
| **A** | User-consented download (Brave model) on all platforms where the in-tree path is available; per-platform terms confirmed by counsel before P10 exit (A2) | DRM playback works where legally clear; each platform with a negative answer ships the disclosed-absence page (§15-R7) for that platform only — the plan is per-platform by design (DR-14: "if legally clear; **else disclosed absence**") |
| **B** | Disclosed absence everywhere (no CDM at all): "XR doesn't play DRM video — here's why + which services" | Zero terms exposure; large user-perception cost ("Netflix-broken perception", Plan §15-R7 impact "High"); the product still functions (DRM is a feature, not the product) |
| **C** | Enterprise MLA path (negotiate for enterprise editions) | Only rational if the business wants guaranteed DRM playback in the enterprise pack (P39-T4); the Plan's premise is that a *client* needs no MLA (F1) — counsel to confirm/correct; cost: contract + per-platform compliance obligations |

## 5. Decision — **left blank by design**

- **VERDICT:** ______________ (counsel; attach written memo; per-platform table requested)
- **CONDITIONS:** ______________ (e.g. required consent strings per platform, download-destination rules for Linux, mirror policy)
- **REVIEW-BY:** ______________ · **DATE:** ______________ (hard gate before **P10 exit** per A2 — "LG-3 must clear platform terms before P10 exit")

## 6. Register actions on verdict

- DR-14: OPEN → RATIFIED (or scoped per platform) via ADR + `Register-Change` trailer;
- threat model: no T-row change expected (CDM is an isolated component process — Plan §1.3), but the Isolation Card / `docs/limitations.md` gains a DRM row per platform outcome (same PR rule);
- if the verdict requires any *bundling* on any platform: **stop and report** — that contradicts Plan R13 ("never pre-bundled") and requires a Plan amendment, not a quiet design change (L24).
