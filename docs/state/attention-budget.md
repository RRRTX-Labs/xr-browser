# Attention-Budget ledger v0 — policy of record (Plan P8-T6)

Status: LOCAL COUNTERS ONLY. Cited by `xr-core/settings/core/counters.h`
("stated here and in docs/state/attention-budget.md") — this file is that
statement and is gate-checked by `tools/run_checks.sh` (P8-T6 lane).

## 1. The law

Settings search and settings-usage analytics are **local counters only**.
There is no telemetry: no upload path exists, no network path exists, no
identifiers are recorded, and nothing in this policy may be read as an
exception to the phase's no-hidden-telemetry law. The host (`settings_host`)
is a stdio JSON process; the counter ledger is a file in the settings store
dir. Neither has a socket, an uploader, or a clock finer than a day.

## 2. What is counted — and why

The ledger answers three questions at DAY granularity (UTC calendar dates):

| event | record | purpose |
| --- | --- | --- |
| a settings section is opened | `opened.<section> += 1` | which sections people actually use |
| a search query is accepted | `queries += 1` | search is used (count only — never the query text) |
| a setting is changed | `changed.<key> += 1` | which settings get changed |

The counts exist so product/promotion decisions (Plan L12) rest on usage
data instead of opinion. Counts are coarse by design: no query text, no
event content beyond the static schema ids of sections/settings, no
timestamps finer than the day bucket.

## 3. Storage

- File: `settings-counters.json` inside the settings store dir (`--store-dir`).
- Shape: canonical JSON, one line + trailing newline:
  `{"schema":"xr-settings-counters","schema_version":1,"days":{"YYYY-MM-DD":{"opened":{"section":n},"queries":n,"changed":{"key":n}}}}`
- Day keys are UTC calendar dates produced by `gmtime_r`; no clock value is
  stored anywhere in the file.
- An absent file loads as an empty ledger (`ok`, nothing written).

## 4. Retention

Rolling 90-day window, enforced at persist time: on `Save`, day buckets
older than `today − 90 days` are dropped (inclusive cutoff). The retention
constant is `kRetentionDays = 90` in `counters.h`; the doc and the code are
the single statement of the policy — never tune one without the other.

## 5. Durability and failure semantics

- Persist = write `settings-counters.json.tmp` → `fsync` → `rename(2)`.
  A kill mid-write can leave a partial `.tmp`, never a half-written ledger
  (proven by the kill-loop suite).
- A ledger that fails to load (corrupt JSON, schema/schema_version
  mismatch) is **kept as-is**: `Load` reports `preserved`, and `Save`
  refuses to overwrite it (deny-preserve — a file the loader could not read
  is never silently rewritten or dropped; a downgrade is a no-op).

## 6. Disposable sessions

With an empty/absent store dir (disposable, ephemeral, in-memory contexts)
counters live in memory **only**: `Save` returns success and writes zero
bytes. Asserted by a filesystem-diff suite (ephemeral writes nothing).

## 7. Diagnostics

The host exposes `counters-dump` (also `xrctl settings counters`) returning
`{schema, schema_version, days, in_memory}` — a full local view of the
ledger. That is the only reader surface besides the store file itself.

## 8. Boundaries (what this is NOT)

- Not telemetry: nothing leaves the device; there is no network path to
  audit because none exists in code.
- Not behavioral profiling: day-bucket counts of schema-id keys only.
- Not content: query text is never recorded, only that a query was accepted.
- Not a tracker of individuals: no identifiers, no per-user keys.
- Promotion decisions use counts, not event content.

## 9. Enforcement

- C++ suites (`settings` make test): counters unit/durability suites,
  kill-loop, zero-byte disposable fsdiff, deny-preserve corrupt-ledger
  cases, fuzz with the ledger in the loop (`XR_FUZZ_SECONDS` campaigns).
- `tools/run_checks.sh` P8-T6 lane asserts this file exists with the law's
  markers so the citation in `counters.h` can never dangle.
