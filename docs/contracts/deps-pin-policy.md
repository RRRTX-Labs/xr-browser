# Contract — DEPS pin policy (v1)

- **Status:** PUBLISHED (P2-T1)
- **Amendment 2026-09-07 (P3 T0.4):** tooling paths renamed
  `buildsys/` → `build/`, dispatcher `./build` → `./scripts/build` (ADR-0006).
  No schema or field changes — path references only.. Consumed by P3's rebase bot (`./scripts/build refresh`
  is the only writer of pin changes) and by `build/sync.py`.
- **File:** `DEPS` (repo root). Schema version 1 (YAML, safe-loaded).

## 1. The pin is the truth

1. `chromium_rev` and `xr_core_rev` are 40-char git SHAs. Version strings
   (e.g. "152.0.7977.82") are recorded as *metadata* only; the SHA is the pin.
2. A pin change is a PR. Reverting a pin change is also a pin change. There is
   no "latest", no branch pin, no floating tag (Plan §4 P2, "no invented pins").
3. No tool or artifact may re-pin sub-revisions (v8/skia/webrtc/…) inside the
   pins. The chosen Chromium DEPS already pins them; the research log records
   them as informational (R1).

## 2. Remotes

- `gclient_url_scheme` is `https` and only `https`. No `ssh://`, no `file://`,
  no `git://`. The synth-synced DEPS produced by `build/sync.py` must contain
  only `https` URLs; a non-https URL is a data error (sync refuses).

## 3. Write path

- `./scripts/build refresh --to <sha>` is the only pin writer. It:
  1. creates branch `refresh/chromium-<n>` (n = next integer, never re-used),
  2. edits `DEPS` (chromium_rev),
  3. runs `./scripts/build preflight` + (if a checkout exists) `gn parse` of the
     argsets against the new rev,
  4. emits PR-body markdown with the dependency-eval refresh reminder (L9),
  5. **never auto-pushes**.
- Direct hand-edits of `DEPS` are caught by CI: `build/tests/` asserts the
  file parses, has 40-char SHAs, and `schema_version == 1`.

## 4. Offline-after-sync (zero-egress build rule)

- After `./scripts/build sync`, build time performs **no fetches**. The egress manifest
  (`<checkout>/.xr/egress.json`, every URL contacted + timestamp) is the
  checkable property. Any build-time network need is a stop-condition: design it
  in, never smuggle it (build/net-audit.md).
