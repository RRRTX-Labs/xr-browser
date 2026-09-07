# Contract: xr-schema v1 — prefs/ledger row versioning (§1.11 #14 part, T9)

- **Version:** 1. **Reference impl:** `tools/xr_schema.py` (+ `tools/tests/test_xr_schema.py`).

## Versions-from-creation law

Every persisted row (prefs, ledger, activity) carries `{version, created_at}`
**from the moment it is created**. There is no unversioned data. `version` is a
monotonically-increasing integer; `created_at` is an epoch-millis integer set
once at creation and never rewritten (peer pattern: Chromium `components/prefs/`
integer schema version + forward-only migration, research R5).

## Forward-only migration chain

Migrations form a chain `v1 → v2 → v3 …`. Each step is a pure function
`row@vN → row@v(N+1)`. **Downgrades are rejected** (a vN+1 row handed to a vN
reader is a hard error, never silently truncated). `tools/xr_schema.py migrate`
applies the chain forward; `tools/xr_schema.py migrate --to <lower>` exits 1
with `downgrade rejected`.

## Reference impl surface

- `xr_schema.py validate <contract> <file>` — strict validation.
- `xr_schema.py migrate <file> --to <n>` — forward-only migration.
- `xr_schema.py stamp <file>` — add {version, created_at} to a fresh row.
