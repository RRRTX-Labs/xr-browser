# Human gates — P1

Items that are **human/ops-gated by design**. None of these is faked in P1
artifacts: they appear here, in `evidence.json` (verdict `HUMAN-GATED`),
and in the affected documents (marked PENDING-OPS / UNREGISTERED / DRAFT).
Each gate has a named owner placeholder (RRRTX-*) and the exact action that
unblocks it.

| # | Gate | Why it cannot be done in P1 (agent scope) | Blocking action to unblock | Owner placeholder | Status (2026-09-07) | Blocks |
|---|---|---|---|---|---|---|
| HG-1 | **Counsel verdicts LG-1, LG-2, LG-3** | Legal conclusions are human counsel work; P1 delivers briefs (facts + options + blank verdict fields), never verdicts | Outside counsel files a written verdict per brief; verdicts attached to DR-14/DR-15 (and DR-01 context) with dates | RRRTX-LEGAL-01 | PENDING | DR-14 → RATIFIED (Widevine posture, before P10 exit per A2); DR-15 → RATIFIED (SB terms, before P16); DR-01 ratification context (funding + codec budget) |
| HG-2 | **`security@rrrtx.example` mailbox + DNS** | Domain/DNS operations are ops work; the address is *declared* in SECURITY.md but must be marked UNREGISTERED until live | Register `rrrtx.example` (or the real domain), create the mailbox, publish it in SECURITY.md (remove the UNREGISTERED marker) in one reviewed commit | RRRTX-OPS-01 | PENDING | Live email intake (drill finding F2) |
| HG-3 | **GitHub repository creation + branch protection + CODEOWNERS enforcement** | Hosting is an external service account; agent has no org credentials; CODEOWNERS is committed *as data* but GitHub-side review enforcement only exists once hosted | Create `RRRTX-Labs/xr-browser` + `RRRTX-Labs/xr-core` in the existing `RRRTX-Labs` GitHub organization (created 2026-09-07), push, enable branch protection on `main` (required: DCO check, passing governance CI, CODEOWNERS approval for S0 paths) | RRRTX-OPS-02 | PENDING | CODEOWNERS dual-review enforcement (L13); PR template enforcement; GHSA (HG-4); DCO *bot* (P1's `dco_check.py` is the interim) |
| HG-4 | **GitHub Security Advisory (GHSA) enabling** | Requires the hosted repos (HG-3) + org security settings | Enable private vulnerability reporting on both repos; correct the PENDING-OPS placeholder URL in SECURITY.md in one commit | RRRTX-OPS-02 | PENDING | Preferred intake path (drill finding F1); bounty platform at SF-4 |
| HG-5 | **Domain / trademark filings** | Legal/commercial act (XR Browser name, logo, `xr://` scheme name in markets) | Filings per counsel advice; record outcome in the register | RRRTX-LEGAL-02 | PENDING | Brand surfaces (P6 branding task) |
| HG-6 | **Funding confirmation (DR-01)** | DR-01 is the *funding gate for a fork* (≥10 engineers or §15-R17 fallback). P1 records it as `GATE-PENDING` with the funded-team premise (Plan §0.2-7); the confirmation is a principals' act | Principals record staffing level in the register (Register-Change trailer + ADR reference) | RRRTX-PRINCIPALS | PENDING | Stage-0 exit; P2 scale-up (build farm sizing assumes funded premise — §15-R17 fallback activates if it regresses) |
| HG-7 | **Human re-read of agent-drafted ADRs 0001/0002 and the register transcription** | ADR-0002 §4: agents draft, humans decide. The register is an agent transcription of Appendix B — a human must verify row-by-row before the register counts as ratified | Named decider(s) re-read `docs/adr/0001*`, `0002*`, `docs/register/decisions.yaml` against Plan Appendix B; flip ADR decider lines; commit references this gate | RRRTX-PLATFORM-LEAD | PENDING | Register status "RATIFIED" has full standing (mechanics already enforced by CI either way) |
| HG-8 | **Re-run of the synthetic intake drill on live channels** | Requires HG-2/HG-4 | Re-run drill (record in `evidence/P1/logs/`) after hosting + mailbox are live; once more with a volunteered internal report at SF-4 | RRRTX-G-LEAD | PENDING | Public-trust row (§17) before Public Alpha |

## Standing rule

Any P1+ artifact that would read as "live" for a gated item must carry an
explicit marker (PENDING-OPS / UNREGISTERED / DRAFT — NOT ACTIVE /
SIMULATED). The vocabulary lint and review checklist enforce this (L5/L11).
If a gate stays PENDING past the phase that needs it, that phase's DoD row
is `HUMAN-GATED`, not `PASS` — and the block is reported, not papered over
(orchestrator stop-condition: "evidence would require claiming something
not actually run → never fabricate").
