# Open assumptions (verbatim from Plan Appendix A)

Copied from `XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` Appendix A — "Open
assumptions (named verification tasks, not hand-waving)". These are
*assumptions with a named verification task*, each with a mitigation
already in Plan §15. They are **not** decisions (the Decision Register
owns those) and they are **not** closed by P1.

| # | Assumption (verbatim) | Verified in |
|---|---|---|
| A1 | "`StoragePartitionConfig`-based mixed-identity windows survive the full papercut census" | **P4** (fallback pre-designed) |
| A2 | "Widevine component-updater availability for third-party builds on Win/mac/Linux" | **LG-3 before P10 exit** (brief: `docs/legal/LG-3-widevine-distribution.md`) |
| A3 | "SB API non-commercial terms cover RRRTX's distribution model (esp. enterprise pack)" | **LG-2** (brief: `docs/legal/LG-2-safe-browsing-terms.md`) |
| A4 | "Arti's bridge/transport completeness meets XR's Tor-user threat population" | **P31 spike w/ C-tor fallback shipped same-phase** |
| A5 | "keystore coexistence with uBO-Lite/1Password double-fill conflict" | **P27-T8/P21-T8 corpus** |

Plan note (verbatim): "Each assumption's failure has its mitigation
already in §15."

## P1 status (2026-09-07)

All five OPEN. A2/A3 are additionally human-gated on counsel verdicts
(HG-1). None may be marked verified without the named task's evidence
(L11).
