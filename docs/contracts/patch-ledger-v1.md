# Contract: patch-ledger-v1 (rebase reports, issue bundles, retirement ledger)

Status: ACTIVE (P3) · Owner: @xr/platform · Schema source: `build/upstream/rebase_bot.py`, `build/upstream/issues.py`, `build/upstream/retirements.py` (code is the single source of truth; this page is the human contract)

## 1. rebase-report.json (v1)

Emitted by `./scripts/build rebase rebase --to <rev>` into `work/upstream-cache/rebase-report.json`. One report per classification pass.

```json
{
  "schema_version": 1,
  "tool": "xr-rebase",
  "source": "real" | "fixture",
  "mode": "classified" | "dry-run",
  "generated_at": "<ISO-8601 UTC>",
  "from_rev": "<40-hex pin>",
  "to_rev": "<as requested>",
  "to_resolved": "<40-hex resolved>",
  "wall_clock_seconds": 0.0,
  "bytes_fetched": 0,
  "verdict": "GREEN" | "DRIFT" | "BROKEN",
  "next_action": "<human-readable next step>",
  "patches": [
    {
      "id": "0001-brand-ui",
      "owner": "@xr/platform",
      "category": "branding",
      "cls": "clean | textual-drift(3way-ok) | file-moved | file-deleted | semantic | stale-base",
      "source": "real" | "fixture",
      "detail": "<what the classifier saw>",
      "files": [{"path": "...", "cls": "...", "detail": "...", "moved_to": "..." | null}],
      "ledger_state": "<applied-at rev>"   // informational only, when the applied-ledger exists
    }
  ],
  "range_log": [{"commit": "...", "subject": "..."}],
  "assumptions": {"status": "not-run" | "not-run (fixture mode)"},
  "issue_bundles": ["work/upstream-cache/issues/<file>.md"],   // only when verdict != GREEN
  "prepared_branch": "rebase/chromium-<short>"                  // only GREEN + real + non-dry-run
}
```

Laws:
- **Verdicts** — GREEN: every patch applies cleanly. DRIFT: only mechanical classes (moved/textual-drift); a human re-anchors, no semantic change. BROKEN: semantic/file-deleted/stale-base present — a human work item, never auto-resolved, and **"disable & TODO" is forbidden (§12.3)**.
- **dry-run mode is never citable as applied state** — a report with `"mode": "dry-run"` is a forecast; only `classified` reports may be referenced as the current treadmill state, and even those describe applicability, not application (application state lives in the applied-ledger + DEPS).
- **The bot never pushes** (L24): `prepared_branch` names a LOCAL candidate branch only.
- Zero-clone: all file content arrives via `build/upstream/fetch.py` (gitiles TEXT) — never a checkout.

## 2. Issue bundles (owner-routed conflict bundles)

On any non-GREEN verdict, `issues.route()` writes one bundle per conflicting patch under `work/upstream-cache/issues/`:

- filename: `<stamp>-<patch-id>.md`
- contents: what broke (class + per-file detail), the upstream range, the patch's semantic intent (from patchinfo), the routed owner, and the re-anchor/rebuild instructions
- credentials: bundles are FILES. The bot never opens authenticated GitHub issues (HG-16: no credential reads by the bot); the owner files/works the bundle themselves. The `api.github.com` allowlist entry covers read-only discovery only.

## 3. retirements.json (the seam-retirement ledger, §12.5)

`build/upstream/retirements.json`, appended ONLY by `xr-patch retire` (the sanctioned removal path):

```json
{"schema_version": 1, "retirements": [
  {"id": "...", "rev_retired_at": "<40-hex>", "mechanism": "upstreamed | obsoleted | dropped-with-review",
   "evidence": "<upstream CL/bug or obsolescence reference>", "note": "<user-visible consequence + review entry>",
   "retired_at": "<ISO-8601>", "retired_by": "<email>"}
]}
```

`./scripts/build retire lint` enforces: schema, field presence, retired ids absent from the current manifest, and — when xr-core git history is available — **every historical manifest removal has a ledger row** (removal-without-ledger fails CI).

## 4. Assumption-suite artifacts (§12.4)

Registry `build/upstream/assumptions.yaml` (rows A1–A7); runner `build/upstream/assumptions.py`.
- file-contract rows: PASS only when every `contains` string is present in `file` at the rev under test.
- pending-feature rows: **SKIP, never PASS** (L6 — visible honesty).
- FAIL rows emit a P0 artifact `<stamp>-P0-assumption-<id>.md` into `--out/issues/` and block promotion (the promotion job runs the suite as a blocking step).
