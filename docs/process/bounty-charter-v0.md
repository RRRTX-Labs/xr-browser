# Bug bounty charter v0 — DRAFT — NOT ACTIVE

> **This charter is a draft. The program is NOT running.** Launch is
> gated at **SF-4 (end of Phase P21, Plan §6.3)** — before that, no
> bounties exist, no payments are owed, and no one should read this file as
> a live program. It is published early because the intake pipeline,
> severity ladder, and scope language must be settled *before* the program
> goes live (Plan §4 P1-T3: "bounty charter v0"; Plan §2.9 row "Bug bounty
> + coordinated disclosure + SECURITY.md + advisories", phase P1).

## 1. Scope (planned)

- `xr-core` `//xr` tree + patch surface;
- helper processes: `xr-vaultd`, `xr-tord`, `xr-wgd`, `xr-inspect`,
  `xr-lists`, `xr-update-server` (as they exist at program launch);
- XR update/list channels (threat-model T10);
- identity isolation, vault boundaries, route integrity (Plan §1.12).

**Out of scope:** upstream Chromium (→ Chromium VRP), local malware /
compromised OS (T8), state-level operations (T9), pre-release stubs,
DMCA/DRM theories (DR-16), marketing surfaces. (Full list: `SECURITY.md`.)

## 2. Severity → payout table (draft, figures unset)

| Severity | Payout (TBD at activation) |
|---|---|
| Critical | TBD — highest band; in-the-wild or real-credential exposure qualifies |
| High | TBD |
| Medium | TBD (considered, not guaranteed) |
| Low | Recognition, no payment (expected) |

Figures are deliberately **unset** in this draft: they are a principals'
decision at SF-4, not an engineering one. Publishing empty bands is more
honest than publishing invented numbers (L5).

## 3. Rules (draft)

1. One report per unique root cause per researcher; duplicates get
   credited, not paid twice.
2. No active scanning of endpoints beyond what a single test build
   requires; the documented endpoint set (Plan §9.13) is the only legal
   target surface for remote findings.
3. Embargo terms identical to `disclosure-policy.md` §2 — a bounty report
   does not shorten or extend the reporter's veto.
4. Good-faith effort that finds nothing is never penalized; the ack
   SLA (≤ 24 h) applies to bounty reports exactly as to any report.
5. **Retroactivity (draft):** reports filed in good faith between P1 and
   activation are re-evaluated against the live table at activation,
   subject to the then-current scope. This is a commitment to
   *consideration*, not a commitment to payment.

## 4. Activation checklist (owners, at SF-4)

- [ ] Payout bands ratified by principals (owner: RRRTX-PRINCIPALS)
- [ ] Program platform live (GHSA-backed) (owner: RRRTX-OPS-02)
- [ ] Triage staffing confirmed (2 staff, Plan §9.9 red-team cadence) (owner: RRRTX-G-LEAD)
- [ ] This file re-issued as v1 with the header banner removed — in a
      commit whose message states activation (no silent switch from draft)
