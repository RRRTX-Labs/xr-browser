# Contract — patch-manifest format v1

- **Status:** PUBLISHED (P2-T3)
- **Amendment 2026-09-07 (P3 T0.4):** tooling paths renamed
  `buildsys/` → `build/`, dispatcher `./build` → `./scripts/build` (ADR-0006).
  No schema or field changes — path references only.. Consumed by P3's rebase bot (which keys its
  re-apply logic off the ledger `<checkout>/.xr/patch-apply.json`) and by the
  budget meter (`build/farm/budget_meter.py`). P3 may extend the schema;
  it may not rename fields without a register note.
- **Manifest lives at:** `xr-core/patches/manifest.yaml` (the product repo).
  The applicator (`build/patching/apply.py`) reads it from
  `<checkout>/src/xr/patches/manifest.yaml`.

## 1. Schema (YAML, safe-loaded)

```yaml
schema_version: 1
total_cap: 150
categories:                 # caps are the Plan §1.2 patch-class budgets
  branding: { cap: null }   # "unlimited-ish (cheap)" — still counts in total_cap
  hook_points: { cap: 45 }
  blink_seams: { cap: 25 }
  content_seams: { cap: 30 }
  network_seams: { cap: 20 }
  ui: { cap: 35 }
  extension_chokepoint: { cap: 2 }
patches:
  - id: "0001-brand-ui"          # unique, stable (rebases key on it)
    owner: "@xr/platform"        # owning team/handle (patchinfo.md too)
    category: branding           # one of the categories above
    files:                       # upstream files touched (metadata; the .patch is truth)
      - chrome/app/theme/chromium/BRANDING
    dir: branding/0001-brand-ui   # relative to the manifest file's directory
                                  # (patches/); holds patchinfo.md + *.patch
```

Each `patch.dir` contains **`patchinfo.md`** (mandatory) and the unified-diff
patch file(s) `*.patch`. The applicator applies every `*.patch` in a dir, in
sorted order, via `git apply`.

## 2. Applicator law (L6 — the anti-fork-rot rule)

1. **Idempotent:** applying an already-applied patch is a reported no-op
   (ledger content-hash match), never a re-apply, never a silent skip.
2. **Atomic per patch:** `git apply` is all-or-nothing per patch file; a
   conflict on patch N stops the run with unified-diff context and reports
   exactly which patches applied. The ledger reflects only what actually
   applied.
3. **Fail-loud:** a patch that does not apply cleanly is an error with diff
   context — never skipped, never "best effort".
4. **Applicability ledger:** `<checkout>/.xr/patch-apply.json`, entries
   `{patch_id, applied_at_rev, content_hash}`. P3's rebase bot keys off this:
   a patch is "applied" iff its content-hash matches at the recorded rev.
5. **Path policy:** the applicator refuses any patch whose `+++` target path
   is outside the allowed roots (default `chrome/app/`), is absolute, or
   contains `..` traversal. Extending the roots is a manifest edit, not a
   runtime override.
6. **Checkout guard:** the applicator refuses to run unless it can verify the
   checkout is Chromium-at-pin: `src/chrome/VERSION` exists and
   `git -C src rev-parse HEAD` equals the pin (never against a random dir).
7. **No destructive ops:** never `git clean -fdx`; revert only reverses
   patches the ledger records as applied by this tool.

## 3. patchinfo.md mandatory fields (linted by `xr-patch lint`)

`id`, `title`, `owner`, `category`, `files`, `upstream-bug-if-any`,
`retirement plan`, `rebase-notes`. P3-T6 extends these; missing fields are a
data error today.

## 4. Budget (Plan §1.2)

- **Total** upstream-touched patch entries ≤ **150** (count published per
  release). **Per-category caps** as in the `categories` block. Exceeding the
  budget is an architecture review, never silent scope — `xr-patch lint` and
  `budget_meter.py` reject overflow as a *data error* today (P3-T3 turns the
  meter into a hard CI gate).
