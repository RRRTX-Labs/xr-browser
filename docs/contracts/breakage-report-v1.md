# Contract: breakage report v1 (`breakage-report-v1.schema.json`)

**Status:** LIVING (registered post-freeze; `docs/contracts/registry-post-freeze.md`)
· **Introduced:** P13-T4 · **Validator:** `tools/xr_schema.py` (`breakage-report`)
+ `tools/breakage_report.py` (compose/refuse) · **Owner:** the list-corpus track.

## Why a contract

A breakage report is the only artefact in the product that both **leaves the
machine** and **describes the user's page**. Everything that makes it useful
(site, rule, version) is a step away from everything that makes it dangerous
(path, query, cookie, agent). Prose cannot hold that line — a schema can, because
it can refuse.

## Laws

1. **Context is four things.** origin (scheme + registrable domain), a UA-less
   browser version tag, the matched rule id, and the list's id + bundle version.
   A report with no `rule_id` is legal and is labelled `unclassified`; a report
   with a *path* in its origin is not legal at all.
2. **`additionalProperties: false` everywhere.** An `html` field, a `cookie`
   field, a `screenshots` field — each is refused by structure, before any
   refusal rule has to notice it. This is why the schema, not the tool, is the
   first line: a new tool against this contract inherits the refusal.
3. **`queue` is `const: "fixture"`.** In this repository there is no live mode,
   so a payload that claims one cannot validate. (The live queue is a human act —
   `docs/panel/breakage-report.md`.)
4. **`sla` is data.** `{label, hours, class}` — a declared target and a class,
   never a rendered sentence and never a measured median. No tool here computes
   an SLA statistic, and none may: `48 h median on 20 seeded reports` is a
   production measurement.
5. **`created_at` is caller-supplied** (`--as-of`). The generator has no clock, so
   a timestamp cannot be invented (`tools/wall_clock_lint.py`).

## Vectors

`docs/contracts/vectors/breakage-report-v1.json`: 2 accept cases (a corpus-linked
report and an `unclassified` one) and 8 refuse cases — extra `html` field,
missing required context, origin carrying a path+query, a note carrying a URL
with a query, a cookie, a user-agent string, selector text, and `queue: "live"`.
Each names its expected refusal class, and a case refused for a *different*
reason is a failure: "refused somehow" is not the contract.

Run: `python3 tools/breakage_report.py --check`.
