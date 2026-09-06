# Security policy — XR Browser (RRRTX Systems)

**Status of this file:** in force as policy text (P1). Two operational
dependencies are **not yet live** and are marked as such — see
`evidence/P1/human-gates.md`:

| Item | State |
|---|---|
| GitHub repository hosting (required for the GitHub Security Advisory flow) | **PENDING-OPS** — placeholder URL: `https://github.com/rrrtx/xr-browser` (PENDING-OPS: repository not yet created; the URL will be corrected by ops in a one-line commit when hosting lands) |
| `security@rrrtx.example` mailbox + DNS | **UNREGISTERED** — the address is declared here as the future routing point but does not exist yet; do not send reports to it until `evidence/P1/human-gates.md` shows it live |

Until both are live, the only working intake path is: **report to a named
XR Platform engineer directly** (see `CONTRIBUTING.md` for team pointers),
clearly marked "security report", and request forwarding into the embargo
workflow below. That is a *temporary human bridge*, not a policy exception.

## Reporting

1. **Preferred (when hosting is live):** open a **GitHub Security Advisory
   (GHSA)** private vulnerability report on the repository hosting this
   file (`https://github.com/rrrtx/xr-browser` — PENDING-OPS). GHSA gives
   reporters private tracking, embargo-aware disclosure, and credit
   options.
2. **Email (when registered):** `security@rrrtx.example` (currently
   UNREGISTERED — see table above).
3. **Never** post security issues to the public issue tracker. The public
   template `.github/ISSUE_TEMPLATE/security-report-intake.md` is for tracking
   *already-acknowledged, in-embargo-or-disclosed* items only.

Include, where possible: affected component (`//xr` subsystem or helper
process: vaultd / tord / wgd / inspect), reproduction steps or PoC,
environment (build tag / Chromium milestone), and impact assessment.
Reporters may remain unnamed if they wish; we do not require identity.

## What we accept (in scope)

In scope is anything in XR-owned code and XR-operated channels:

- `xr-core` (`//xr` tree) and its patch surface;
- helper processes `xr-vaultd`, `xr-tord`, `xr-wgd`, `xr-inspect`,
  `xr-lists` tooling, `xr-leaktest`, `xr-update-server` (as they come to
  exist — Plan §7.1);
- XR update/list channels: signed manifests, list bundles, component
  endpoints (threat-model T10);
- identity isolation mechanisms (Plan §1.12 invariants 1–2), vault
  boundaries (invariant 3), route integrity (invariant 5).

## What we do not accept (out of scope — mirrored from the Plan, not invented)

- **Upstream Chromium component vulnerabilities** (V8, Blink internals,
  sandbox, GPU): report to the Chromium VRP. We forward reports, track our
  exposure, and publish consumed-CVE mappings per release — **XR never
  hides upstream issues** (Plan §9.9). Duplicating a Chromium-VRP report
  here is out of scope.
- **Local malware / compromised OS** (threat-model T8): out of scope,
  stated (Plan §9.1). A compromised host can read anything; XR makes no
  defense claim here.
- **State-level adversary operations** (threat-model T9): out of scope,
  stated; XR routes users to Tor Browser/Tails in-product (Plan §9.1, §1.13).
- **Theoretical issues with no reachable exploit path in shipped code**,
  and **issues in pre-P5 stubs that do not exist yet** (this repository
  intentionally contains no engine code — P1 is governance only).
- **Social engineering of RRRTX staff**, marketing-site issues for
  `xr-web` (does not exist until P39), and DMCA/DRM theories (DR-16
  posture is categorical: no extractor, no circumvention — contribution
  policy bans it).

## Severity ladder

| Severity | Definition (examples) |
|---|---|
| **Critical** | Real-credential or vault material exposure; cross-identity isolation bypass (invariant 1/2 break); route-integrity leak on a Tor/WG identity (invariant 5); update-channel compromise; in-the-wild exploitation |
| **High** | Remote code execution in a renderer *via XR-owned code*; vault boundary violation without credential exposure; list-channel compromise enabling malicious rule injection; extension egress policy bypass |
| **Medium** | Fingerprint/isolation *weakening* below the published §1.13 posture; telemetry/endpoint not in the documented set (L15); data-leak of K3/K4 class (identity metadata / activity ledger) |
| **Low** | Local denial of service without privilege gain; minor redaction gaps in exports; non-security correctness bugs with privacy flavor |

## Response SLAs (DR-02 / Plan §12.4)

- **Acknowledgement:** ≤ **24 hours** from intake, every day of the week.
- **Patch SLA:** **Critical ≤ 72 hours** (from tag/acknowledgement of the
  triaged severity); **High ≤ 14 days**. These are the same numbers as the
  upstream-security fast-lane (Plan §12.4: "72 h critical/IIT / 14 d high
  SLA from tag publication").
- **Embargo:** shared until coordinated disclosure (see
  `docs/process/disclosure-policy.md`). We hold the fix, not the silence —
  the publication date is set with the reporter by default, never
  unilaterally extended.
- **Bounties:** **DRAFT — NOT ACTIVE.** The charter v0
  (`docs/process/bounty-charter-v0.md`) is intentionally inactive; program
  launch is gated at **SF-4 (end of P21, Plan §6.3)** per the Plan. Until
  then, good-faith reports get acknowledgement, credit, and (where a
  program later activates) retroactive consideration — never a promise of
  payment made now.

## What happens after you report (embargo steps, abridged)

1. Acknowledge ≤ 24 h; assign severity; open embargo record (internal).
2. Triage + fix development under embargo; severity may be revised (we
   tell you if it drops).
3. Patch lands per SLA; disclosure draft prepared
   (`docs/process/disclosure-policy.md` template).
4. Coordinated disclosure date agreed; advisory published (L22: incidents
   are published — including the "what would have caught it sooner"
   section).

Full disclosure mechanics: `docs/process/disclosure-policy.md`.
Post-incident template and publication law (L22): same file, §4.

## Our own security posture (honesty row)

This policy text is P1 governance. The protections it references (isolation
matrix, leak suite, vault audit) are **target postures** that ship with
their phases (Plan §11) — the threat model
(`docs/threat-model.md` v0) states per-adversary what the product does and
does **not** protect against. We do not claim security we have not shipped.
