# Contract: sla-metrics-v1 (security fast-lane service levels)

Status: ACTIVE (P3) · Owner: @xr/security · Tools: `build/upstream/fastlane.py` (`watch` / `plan` / `sla` / `drill`)

## 1. The clock

**The SLA clock starts at TAG PUBLICATION time of the upstream Chromium security release, not at any announcement, advisory, or our detection of it.** Tag publication time is the `time` field of the release row on chromiumdash (allowlisted source, fetched via `build/upstream/fetch.py`).

Rationale: publication is the moment the fix (and the vulnerability, via the diff) becomes public knowledge. Anything earlier (embargoed heads-up) is not observable or honest; anything later (our detection lag) is OUR latency and must not be hidden inside the metric.

## 2. Windows (Plan §12.4)

| severity class | window | meaning |
|---|---|---|
| critical / in-the-wild (IIT) | **72 hours** from tag publication | an XR release consuming the fix exists within 72h |
| high | **14 days** from tag publication | an XR release consuming the fix exists within 14d |

`--severity critical` selects the 72h row; `--severity high` the 14d row. Deadlines are computed by `sla_clock()` as `tag_published_at + window` and exposed in every cherry-pick plan (`deadlines.critical_iit`, `deadlines.high`).

## 3. Breach and the kill-switch (§15-R1)

A breach (now > deadline) writes the **feature-freeze marker** `work/upstream-cache/feature-freeze.json` with the missed deadline and the governing law. Per the plan's R1 kill-switch, a missed window freezes feature work; **in P3 CI the marker is ADVISORY** and becomes a HARD gate when the P9 dashboard consumes it — this is stated in every artifact that carries the marker, not silently downgraded.

**Pre-GA honesty note (P3 state):** XR has no stable release yet (first stable promotion is P10). Pre-GA breach markers are therefore recorded as ADVISORY-ONLY — the kill-switch arms at the first stable promotion. The `sla` output carries this note verbatim so a raw JSON dump can never be mistaken for an armed enforcement event.

## 4. Detection (release-driven; commit-message advisory only — R4)

Candidates are SECURITY RELEASES: every new Stable/Extended tag is a candidate whose range is classified (explicit advisory marker > security wording > unknown risk). Commit-message regex (CVE-, security, UA-words) is advisory enrichment, never the primary signal — a fix that lands without those words still rides the release-driven lane.

## 5. Drills (synthetic, honest elapsed)

`./scripts/build fastlane drill` runs the two synthetic rehearsals end-to-end:
detect → plan → apply (git cherry-pick onto a fixture stable branch) → verify content → sign via the P2 `sign_artifact.py` interface (TEST minisign key, `--channel dev`) → SLA clock → freeze-on-breach → report.

- in-window (30h simulated): no breach, no marker.
- breach (80h simulated): marker written.

Every drill artifact is stamped `"source": "fixture"` and `"simulated": true`, and carries BOTH `elapsed_real_seconds` (wall clock, typically < 1s) and `simulated_elapsed_hours` — simulated time is never presented as real latency (honest-drill law).

## 6. Signing lane

Drill plans sign through the P2 interface ONLY: `sign_artifact.py --artifact <plan> --channel dev --os linux --key <TEST key>`. The negative proof runs in every drill: `--channel stable` must be STRUCTURALLY refused by the P2 tool (refuses release/stable channels; release-key parity arrives with P10's HSM story).

## 7. Metrics publication

Fork-health chart rows (`docs/state/fork-health.md`): last drill verdict + simulated hours, and the freeze-marker state. When real activations begin (post-GA), each real activation records real elapsed from tag publication in the same fields, labeled `source: "real"`.
