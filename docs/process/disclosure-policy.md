# Disclosure policy — XR Browser

Status: in force as policy text (P1). Operational dependencies (hosting,
mailbox) tracked in `evidence/P1/human-gates.md`. Law anchor: Plan L22
("Incidents are published") + Plan §9.10 (incident response & disclosure).

## 1. Principles

1. **Publish, always.** Security and user-impact incidents ship a
   post-mortem, redacted of persons, always including a
   "what would have caught it sooner" section (L22). Embargo is a delay
   mechanism, never a suppression mechanism.
2. **Reporter-first.** The reporter sees the disclosure draft before
   publication and can veto a publication date; we cannot unilaterally
   extend an embargo.
3. **Receipts over adjectives.** Every published advisory links the
   evidence: regression test ids (`SEC-*` naming, Plan §9.9), release tag,
   and (where relevant) the leak-suite / isolation-matrix rows that now
   cover the finding (L11: no completion claim without verification).
4. **Upstream transparency.** Upstream Chromium findings we consume get a
   per-train CVE mapping published (Plan §13.6). We never hide upstream
   issues (§9.9).

## 2. Embargo mechanics

| Step | Actor | SLA | Output |
|---|---|---|---|
| Intake + ack | security on-call (P1: named Platform engineer) | ≤ 24 h | embargo record opened |
| Severity triage | security on-call + owning track lead | ≤ 48 h | severity per `SECURITY.md` ladder |
| Fix development | owning track (S0 dual review if applicable, L13) | Critical ≤ 72 h; High ≤ 14 d | patched build tag |
| Disclosure draft | reporter-facing comms (Platform lead) | before publication | §3 template filled |
| Publication | Platform lead | agreed date | advisory + `SEC-*` regression tests + evidence link |

- Embargo records are need-to-know; the set of people under embargo is
  listed per incident (this list itself is not published).
- An embargo that cannot be held (e.g. fix requires an immediate public
  release) is disclosed **sooner**, not later — with the reporter told
  first.
- **Supply-chain compromise** (list channel, update channel, dependency
  backdoor): kill-switch matrix + pinned-key rotation drill per Plan
  §9.10; disclosure includes the rotation evidence.
- **Law-enforcement / data requests:** we hold nothing — zero-knowledge
  claims are re-verified against the release's actual endpoints
  (Plan §9.10, privacy guarantee 2, §9.13); requests are answered in
  writing and the *fact of a request* is published (not its content).

## 3. Public advisory template

```
# XR Browser security advisory: <short name>

- ID: XRSA-YYYY-NNN
- Severity: <ladder from SECURITY.md>
- Affected: <build tags / version range; "none shipped yet" if pre-release>
- Fixed in: <tag> (evidence: <link>)
- CWE (best effort): <id>

## Summary
<what it is, 2–4 sentences, no drama>

## Impact
<concrete: what data/capability, which identities, which routes>

## What we did NOT protect against (honesty row)
<per threat-model: does this finding change any "Does NOT protect against"
cell? If yes, the model diff is linked — §9.1 rule>

## Root cause
<technical>

## Fix
<change + why it is safe>

## What would have caught it sooner
<missing test / gate / review; the follow-up task that adds it>

## Credits
<reporter, per their preference>

## Timeline (UTC)
| event | date |
```

## 4. Post-incident template (user-impact, non-security)

Same shape as §3 with: "affected users", "data touched" (usually: none —
we verify and say so), "what we'd have caught it sooner", and the
corrective list. L22 applies to security **and** user-impact incidents.

## 5. What is deliberately not here

- No bug-bounty amounts (charter v0 is DRAFT — NOT ACTIVE, launch gated
  at SF-4; see `bounty-charter-v0.md`).
- No "we were not breached" blanket claims — each incident report states
  the verified facts for that incident (L5).
- No NDA culture: NDAs may delay disclosure for reporters who request it,
  but the *public* version is always published on the agreed date.
