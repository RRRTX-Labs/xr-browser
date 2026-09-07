# Contract: spike result v1 (`spike-result-v1`)

**Status:** active · **Introduced:** P4 · **Owner:** A lead (Platform/Chromium)

One result row per probe assertion, emitted by the C++ probes and consumed by
`build/spike/probe_driver.py`. The point of fixing the shape now is that these
rows **graduate into the §11.4 isolation matrix** unchanged — the spike's
output and the shipping matrix are the same record type, so "did this hold?"
is answered by comparing rows, not by re-deriving them.

## Shape

```json
{
  "probe":      "isolation_matrix_browsertest.cc::SameSiteDifferentPartition",
  "claim":      "same site + different identity => different partition",
  "expectation": "identity partitions do not share this state",
  "measured":   "two fixed-partition SiteInstances for the same URL",
  "source":     "runtime",
  "pin_sha":    "d04cdb24d67b081f6cf80200ffc5233f44b61109",
  "verdict":    "PASS"
}
```

## Field rules

| field | rule |
|---|---|
| `probe` | `<file>::<case>` — stable across runs; never includes a shard or PID |
| `claim` | one sentence, in the words of the Plan's claim where it maps to one |
| `expectation` | what a correct implementation must do. Never "should work" |
| `measured` | what was actually observed. **Empty until the probe has run** |
| `source` | `static` \| `fixture` \| `runtime` — `runtime` is only legal once a browser executed the probe |
| `pin_sha` | the Chromium rev the row was measured at |
| `verdict` | `PASS` \| `FAIL` \| `SKIP` \| `PENDING-FARM` |

## Law

`source: runtime` rows may not exist until the farm has run (HG-21). Every row
produced today carries `PENDING-FARM` in the probe matrix
(`docs/spike-identity/probe-matrix.md`) and `static` in the tooling rows.
A row whose `source` is `runtime` and whose `measured` is empty is malformed
and the driver rejects it — an unmeasured measurement is not evidence (L5/L11).
