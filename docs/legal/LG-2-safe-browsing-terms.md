# LG-2 — Safe Browsing v5 terms (non-commercial clause, OHTTP relays, Web Risk fallback) — **DRAFT-FOR-COUNSEL**

- **Status:** DRAFT-FOR-COUNSEL (facts, sources, questions, options — no legal conclusions; the verdict is counsel's work, HG-1)
- **Date:** 2026-09-07 · **Prepared by:** XR Platform agent (P1, XR-P1-T5)
- **Linked register rows:** DR-15 (OPEN — SB kept per LG-2), DR-29 (SB = v5 local-list + OHTTP; no XR-operated proxy)
- **Linked assumptions:** A3 ("SB API non-commercial terms cover RRRTX's distribution model (esp. enterprise pack) → LG-2")
- **Why now:** Plan §0.1-R6: "The API is free **for non-commercial use** (commercial → Web Risk) → legal gate LG-2, and the license posture drives the enterprise-edition plan, same as Widevine."

## 1. Questions for counsel

- **Q1 (the core question — non-commercial scope):** The Safe Browsing terms state the API "may not … be used for commercial purposes" absent a separate agreement. Does this bar:
  (a) RRRTX (a commercial entity) distributing a **free, open-source browser** to consumers that uses the API (no per-user charge, no ad revenue — Plan L16 bans ads/rewards/tokens permanently)?
  (b) the **paid enterprise edition** (Plan §16 P39-T4 policy pack) in which the *browser platform* is free and the *enterprise policy tooling* is paid?
  (c) a build in which Safe Browsing is a user-toggleable feature, default-on, with plain-language consequences (Plan §1.6)?
- **Q2 (Web Risk fallback cost/terms):** If (a) or (b) is barred, what are the cost and terms of the commercial fallback (Web Risk), and does the Plan's "commercial → Web Risk" premise (§0.1-R6) survive per-build (consumer build on non-commercial terms, enterprise build on Web Risk) or must the choice be per-entity?
- **Q3 (OHTTP relay operators):** The Oblivious HTTP Gateway documentation says clients "can choose any Relay provider" (example: Fastly) and that the relay authenticates to the service with a specific OAuth scope. Questions: (i) is relay usage covered by the same ToS as direct API usage, or does each relay service add terms? (ii) what privacy claims may XR make to users about the relay topology (relay sees IP, Google sees request content; queries end-to-end encrypted so truncated URL hashes are not visible to the relay — per the docs, counsel to confirm the claimable wording)? (iii) is relying on a *third-party-operated* relay (e.g. Fastly's) consistent with DR-10's "no XR-operated services" and with our "no non-colluding third party we control" honesty row, or does it require a threat-model addition (T6/T10)?
- **Q4 (30-minute freshness):** The terms condition treating a URL as unsafe on having "received from Google updated information (via the applicable API method) within the past thirty minutes." For **Local-List mode** (our default, DR-15/DR-29): does periodic list download satisfy "updated information (via the applicable API method)"? What minimum client-side update cadence and failure behavior (fail how? fail visible per L6?) is compliant?
- **Q5 (SearchUrls data usage):** The terms permit Google to use and share *submitted* URLs from the raw-URL search method. The Plan's default uses hash-prefix lookups + Local-List (no raw URLs leave the device). Please confirm the hash-prefix + local-list design avoids the SearchUrls data-usage clause entirely, and that *opt-in Real-Time mode* (Plan: "Real-Time opt-in") would trigger it — which would require explicit consent copy.
- **Q6 (attribution/warning wording):** The terms require, "before any user begins using the service, and when displaying each warning," attribution + conspicuous notice that reliability/accuracy cannot be guaranteed, "using language similar to that found at User Warnings." We request review of the drafted strings (P16 interstitial + settings disclosure) against the required User Warnings language; we will supply the exact strings at P16.

## 2. Facts (sourced; all accessed 2026-09-07)

| # | Fact | Source (URL) | One-line quote | Anchors |
|---|---|---|---|---|
| F1 | SB v5 offers documented operating modes, is free for non-commercial use, and requires user warnings + attribution | https://developers.google.com/safe-browsing/reference (Overview) | "It offers flexible operation modes: Real-Time, Local List, and No-Storage Real-Time … The system is free for non-commercial use and requires clear user warnings with specific language and attribution to Google." | Q1, Q4, Q6 |
| F2 | OHTTP gateway: privacy model, relay topology, relay examples | https://developers.google.com/safe-browsing/reference (IP Privacy section) | "We introduced a companion API known as the Safe Browsing Oblivious HTTP Gateway API … a non-colluding third-party to handle an encrypted version of the user request … the third party only has access to the IP addresses, and Google only has access to the content of the request. The third party operates an Oblivious HTTP Relay (such as this service by Fastly), and Google operates the Oblivious HTTP Gateway." | Q3 |
| F3 | OHTTP gateway API mechanics: client-chosen relay, relay OAuth scope, E2E encryption of queries | https://developers.google.com/safe-browsing/ohttp/reference (Overview) | "Clients can choose any Relay provider (eg., Fastly) to integrate with the service. The Relay must use OAuth 2.0 authentication with following authorization scope … all the requests are end-to-end encrypted, which means clients' Safe Browsing queries (i.e. truncated hashes of URL expressions) are not visible to the Relay." (page header: "This documentation is currently still under development") | Q3 |
| F4 | Non-commercial restriction + attribution/freshness conditions (terms last modified 2025-11-20) | https://developers.google.com/safe-browsing/terms | "Unless you have a separate agreement with Google, you may not use the Safe Browsing API for commercial purposes. If you indicate to users that you are providing protection against unsafe web resources, then you also agree that before any user begins using the service, and when displaying each warning about a particular site, you will provide attribution and conspicuous notice that the reliability and accuracy of the service cannot be guaranteed, using language similar to that found at User Warnings." | Q1, Q4, Q6 |
| F5 | 30-minute freshness condition + SearchUrls data-usage clause | https://developers.google.com/safe-browsing/terms | "You may not treat a URL from Google's list as an unsafe web resource … unless your application has received from Google updated information (via the applicable API method) within the past thirty minutes. Google may use URLs and associated data submitted through the Safe Browsing API's SearchUrls method … Google may also share submitted URLs, content and metadata with third parties, including other Google customers and users." | Q4, Q5 |
| F6 | Plan's design posture (internal; the engineering side of this gate) | `XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` §0.1-R6, §1.6, DR-15, DR-29 | "adopt the current Safe Browsing v5 architecture's Local-List mode + Google's OHTTP (Oblivious HTTP) relay — no XR-operated proxy needed … Default: Local List + OHTTP; opt-in Real-Time; **Enhanced never shipped**. The API is free for non-commercial use (commercial → Web Risk) → legal gate LG-2" | framing |

## 3. Our model, as it exists (for counsel's framing)

- Consumer build: free, open source (MPL-2.0), **no ads, no rewards, no tokens, no feeds — permanently** (DR-22, L16); telemetry default-off (L16); no XR-operated proxy for SB (DR-29) — the relay, if used, is operated by a *third party* (relay-provider choice per F3).
- Enterprise edition (P39-T4): paid policy-pack tooling layered on the same free codebase.
- Planned client behavior (P16): Local-List + OHTTP default; Real-Time **opt-in**; Enhanced never compiled in; toggleable in Settings "with plain-language consequences" (Plan §1.6).

## 4. Options with consequences (no recommendation — counsel's call)

| Option | Content | Consequences (as we understand them — counsel to correct) |
|---|---|---|
| **A** | Ship SB v5 Local-List + OHTTP in the consumer build on the non-commercial reading (Q1(a) = permitted); enterprise build either (i) covered by the same reading or (ii) on Web Risk or (iii) SB-disabled-with-honest-disclosure | Keeps the phishing story for the free product; enterprise packaging must know which sub-case applies before P39-T4 ships; if (iii), the enterprise edition carries a documented protection gap (honesty row, §15-R6) |
| **B** | Adopt Web Risk for all builds from the start (pay, per F4's "separate agreement" path) | Removes the non-commercial ambiguity for both editions; adds a commercial dependency Google can price; API surface differs (terms per method) — P16 implementation would target the commercial API |
| **C** | Fallback: honest "SB disabled for terms" mode (Plan §15-R6) with third-party list feeds (URLhaus family — terms to be evaluated) or no SB, disclosed in-product | No Google terms exposure; phishing protection degrades materially (Plan §15-R6 rates this "High" impact: "phishing claims hollow"); the disclosure must be prominent (L5) |

## 5. Decision — **left blank by design**

- **VERDICT:** ______________ (counsel; attach written memo)
- **CONDITIONS:** ______________ (e.g. permitted edition split, required warning strings, relay operator constraints, update-cadence minimums)
- **REVIEW-BY:** ______________ · **DATE:** ______________ (must land before P16 exit — the phase that ships SB; A3 is verified *by this verdict*)

## 6. Register actions on verdict

- DR-15: OPEN → RATIFIED (or changed to reflect the chosen mode) via ADR + `Register-Change` trailer;
- DR-29 (no XR-operated proxy): confirm unaffected;
- threat model T4 row: "Does NOT protect against" cell updated with any counsel-imposed limitation (same PR — Plan §9.1 rule);
- `docs/limitations.md`: gains an SB row if any degradation is accepted (same PR).
