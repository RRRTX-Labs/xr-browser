# DRAFT ISSUE — fast-lane watch source: SECURITY_NOTES.md does not exist in-tree

- **Raised:** 2026-09-07 (P3 research, R3)
- **Status:** DRAFT for orchestrator/plan-owner review — the Plan is untouched
  (docs/process/plan-amendment.md governs any edit; none proposed here)
- **Affects:** Plan §4 P3-T5 as operationalized by the phase prompt ("watch
  `chrome/desktop/SECURITY_NOTES.md`"); XR-P3-T5 implementation

## Problem → Evidence → Impact → Solutions → Recommendation

**Problem.** The phase's security fast-lane research item expected an in-tree
per-release security-notes file (`chrome/desktop/SECURITY_NOTES.md`) at the
pinned Chromium rev, to be diffed as the primary watch source.

**Evidence (live, 2026-09-07).**
- `https://chromium.googlesource.com/chromium/src/+/d04cdb24…/chrome/desktop/SECURITY_NOTES.md?format=TEXT` → **HTTP 404**
- Same path at `refs/heads/main` → **HTTP 404**
- Gitiles tree listing of `chrome/` at main → **no `desktop/` subdirectory
  exists** (`app, browser, child, common, credential_provider, …`)
- Web search (chromium.org, blog.google, release-notes surfaces): no in-tree
  SECURITY_NOTES.md for per-release desktop security notes; the Google
  Security blog (2026-07-30) describes release-note publication on the
  existing channels, and machine-readable release data on chromiumdash /
  versionhistory.

**Impact.** A watcher implemented against the assumed file would never fire —
the exact silent-failure L6 forbids. The SLA clock must key off a source that
actually exists and is allowlisted.

**Possible solutions.**
1. Watch the Chrome Releases blog (blogspot) — rejected: not on the fetch
   allowlist, HTML scraping, no machine-readable timestamps.
2. Watch versionhistory.googleapis.com — rejected for runtime: precise
   timestamps but **not on the allowlist** (kept as research cross-check only).
3. **Watch chromiumdash `fetch_releases` (Stable + Extended channels) +
   gitiles exact-tag lookup** — chosen: both domains allowlisted, JSON,
   carries per-release publication time (`time`, epoch ms; cross-checked
   against versionhistory to the millisecond), previous_version (range
   boundary), milestone (even-series discovery), and the chromium hash.

**Recommendation.** Adopt solution 3 (implemented in
`build/upstream/fastlane.py` as `ChromiumdashSecurityWatch` +
`GitilesTagVerification`), keep the SLA definition contract
(`docs/contracts/sla-metrics-v1.md`) source-agnostic ("measured from tag
publication"), and record this divergence here. If a future Chromium rev adds
an in-tree security-notes file, a `GitilesSecurityNotes` watch source can be
added behind the same `WatchSource` interface without contract changes.
