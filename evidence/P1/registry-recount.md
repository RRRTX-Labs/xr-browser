# Registry recount — 2026-09-07 (P1-T10)

Purpose: record the row count of plan §2.1–§2.9 exactly, because the
planning estimate ("~115±2 rows") does not match the pinned plan's
tables.

Method (reproducible): parse `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md`
(pinned sha256 `02743146146fa139cd53b15216aaa26b79f9d9307998b1814019d27406265a7b`)
between the `# 2.` and `# 3.` headers; count data rows (9-column markdown
table rows, header + separator excluded) per `## 2.N` section:

| Section | Rows |
|---|---|
| 2.1 | 7 |
| 2.2 | 14 |
| 2.3 | 15 |
| 2.4 | 13 |
| 2.5 | 16 |
| 2.6 | 10 |
| 2.7 | 19 |
| 2.8 | 14 |
| 2.9 | 14 |
| **Total** | **122** |

Status split (by decision class): active 100 · deferred 3 (Android,
payment cards, reproducible builds) · dropped 19.

Command used (independent cross-check, same result):

```
awk '/^# 2\./{in2=1;next} /^# 3\./{in2=0}
     in2 && /^## 2\./{sec=$2;next}
     in2 && /^\| /{ if ($0 ~ /^\| Feature /) next; if ($0 ~ /^\|[- |]+\|$/) next; cnt[sec]++; total++ }
     END{ for (s in cnt) print s": "cnt[s]; print "TOTAL: " total }' \
  docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md
```

Ruling: the plan is the source of truth; the registry contains all 122
rows. The "~115" estimate (a pre-plan working figure) is superseded and
recorded here rather than forcing the plan or the registry to match it.
This is a *counting* discrepancy, not a plan deviation: no plan passage
was changed, so no amendment or draft issue is required.
