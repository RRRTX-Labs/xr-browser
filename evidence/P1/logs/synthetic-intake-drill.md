# Synthetic intake drill — XR-DRILL-001 — **SIMULATED**

**Classification: SIMULATED.** This drill exercised the *documented* intake
pipeline of P1 against a **fake** report. No real report was received, no
real vulnerability exists, no real person was involved, and no mailbox,
hosting, or GHSA flow was used (none exists yet — see `human-gates.md`).
Running this drill now is Plan §4 P1's "Security req: disclosure pipeline
*tested* (synthetic report walked end-to-end)" and "First 10 actions"
item 3 ("run one synthetic vulnerability report through the entire intake
pipeline and fix what breaks").

Date: 2026-09-07 · Executor: XR Platform agent (P1) · Witness: orchestrator log

## The fake report (invented for the drill — do not treat as real)

> **ID:** XR-DRILL-001
> **Channel:** (simulated) private message to a named Platform engineer
> **Claim:** "Hypothetical: in a *future* list-bundle format, a crafted
> signed bundle with a truncated signature block might cause the *future*
> list parser (P11) to misclassify a rule as a resource-replace directive,
> letting a compromised list channel serve blocking rules to a specific
> identity. No current code implements any of this."
> **Reporter:** (simulated) external researcher, wishes to remain unnamed

## Walk-through against the documented pipeline

| Step (per SECURITY.md / disclosure-policy.md) | What happened (SIMULATED) | Manual-only? |
|---|---|---|
| 1. Intake via preferred channel (GHSA) | **BLOCKED — no hosting** (PENDING-OPS). Fallback used: "report to a named engineer directly" bridge from SECURITY.md. The bridge *worked as documented*; the preferred path could not be exercised at all. | YES — GHSA enabling is human-gated |
| 2. Acknowledgement ≤ 24 h | (Simulated) ack drafted at T+2 h; content: severity triage requested, embargo record opened, reporter's name-not-required preference recorded. | NO (template exists) — but *sending* it requires the mailbox (UNREGISTERED) → manual |
| 3. Severity triage (≤ 48 h) | (Simulated) mapped to **Critical-adjacent → High**: "list-channel compromise enabling malicious rule injection" matches the High row *if the code existed*; downgraded to **not-triageable** because the claimed component (P11 parser) does not exist in any shipped code — correct call per SECURITY.md out-of-scope row 4 ("issues in pre-P5 stubs that do not exist yet"). | NO (ladder exists) — judgement call is human |
| 4. Embargo record | (Simulated) record fields filled from the template; no real embargo opened. | NO (fields defined) |
| 5. Fix development | N/A — no code exists to fix; the drill correctly produced *no* fix step. This is the honest outcome: **the pipeline refuses to fabricate work against non-existent code** (anti-fabrication rule held). | — |
| 6. Disclosure draft | (Simulated) §3 template filled for the "not-triageable" outcome: advisory would state "reported component does not exist in any released build; no action; tracked as P11 threat-model input (T10)". | NO (template exists) |
| 7. Publication | (Simulated) not published — nothing to publish; drill record *is* the artifact. | — |

## Findings (what the drill broke / exposed)

1. **F1 — Preferred intake path is non-functional until hosting lands.**
   The GHSA path cannot be simulated meaningfully (it is a platform
   feature). Recorded in `human-gates.md` (GHSA enabling). Severity:
   acceptable for P1 (governance phase); must close before any public
   build (Plan §17 "Public trust" column: SECURITY.md + bounty live at
   Public Alpha).
2. **F2 — The email fallback is non-functional until DNS + mailbox land.**
   Same gate; recorded.
3. **F3 — Triage ladder handles the "component does not exist" case with
   no documented outcome class.** The walk-through produced an ad-hoc
   "not-triageable" label. **Fix applied:** SECURITY.md out-of-scope row 4
   already names this case ("issues in pre-P5 stubs that do not exist
   yet") — the drill confirms the row is sufficient; no change needed,
   noted for the record.
4. **F4 — No automated ack clock.** The 24 h ack is human-tracked.
   Acceptable pre-hosting (one engineer, zero expected volume); the
   human-gates list notes that an ack-tracking tool is *not* in P1 scope
   (no premature tooling — L24).

## Verdict

**SIMULATED — pipeline text is coherent end-to-end; operational paths are
blocked exactly where human-gated items say they are.** No part of this
drill claims a live capability that does not exist. Re-run this drill
(simulated) after each of: hosting live, mailbox live — then once, at
SF-4, with the real channel and a *volunteered* internal test report.
