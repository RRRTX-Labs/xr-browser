# The breakage report: what leaves the machine, and what "48 h" means

**Status:** the local half is implemented (P13-T4); the live half is
**HUMAN-GATED**. Owner of the queue: a human maintainer of the public list
corpus — not a bot, not this repository. Instrument: `tools/breakage_report.py`.

This document is the *method* cited by `evidence/P13/human-gates.md` (HG-33) and
by the bundle's `NOT-RUN` rows. It was cited there before it existed, which is how
the dangling-citation law in `tools/doc_reference_check.py` was found: a
`NOT-RUN (method: <path>)` whose path does not resolve is not a method.

## What a report carries (and what it cannot)

```
context.origin                scheme + registrable domain   (no path, no query, no fragment)
context.browser_version_tag   a UA-less version tag         (never a user-agent string)
context.rule_id               the matched rule, or ""       (a list id alone is not a report)
context.list_id / bundle_version    which list, which revision
context.action                kBlocked | kAllowed | kRedirected | kUpgraded
user_note                     free text, refused if it smuggles
sla                           {label, hours: 48, class}      DATA, never a sentence
queue                         the literal string "fixture"
```

Page content, cookies, full URLs with query strings, user agents and selector
text are **absent by schema**: `additionalProperties: false` everywhere means an
`html` field is refused by structure, and the free-text fields are scanned for the
same classes before anything is written. Refusal is **pre-send**, and the refused
bytes are never written — `tools/breakage_report.py` has no redaction step,
because a report that went out "mostly redacted" went out.

The eight refused shapes are committed as vectors
(`docs/contracts/vectors/breakage-report-v1.json`) so a future change that starts
accepting one of them is caught rather than argued about.

## Transport: there is none here, on purpose

The plan says a report reuses **P10's update channel** rather than opening a
second egress path. That channel today carries an *envelope fetch* (GET +
minisign verification of an update manifest); it has no POST payload shape. The
honest consequence is recorded rather than papered over:

* this repository adds **no** egress path, no new host, and no network code to
  `tools/breakage_report.py`;
* a POST shape for the existing channel is **P14 work** (the channel's contract is
  `docs/contracts/server-channels-v1.schema.json`; adding a shape there is a
  contract change with its own review, not a P13 side effect);
* until then the tool writes to a **local fixture queue** whose path must contain
  `fixture`, and its stdout says `queue_mode: fixture`. A queue that does not say
  it is local is how a fixture starts looking like production.

## The live half, as a drill (HUMAN-GATED)

To file a real report a human:

1. exports the payload with `--validate-only` and confirms the schema accepts it;
2. posts it to the queue's intake **from a machine with credentials for that
   queue** — this repository holds no credential and never will (HG-20);
3. records the report id back into the phase's evidence as a human act, not as a
   `ci-run` row.

The live queue is **NOT-RUN** from this sandbox: it is not reachable, and a `gh`
write to a private repository is not the public queue. Presenting the latter as
the former would disqualify the phase.

## What "48 h median" means, and why there is no chart here

The plan's DoD reads "corpus-linked breakage pipeline live w/ 48 h median proven
on 20 seeded reports". That is a **production measurement over real reports in a
public queue**. It is not measurable here, and P13 does not pretend otherwise:

* **`sla.hours: 48` is the declared target** — a number in a payload, labelled by
  class (`corpus-linked` / `unclassified`), not a claim about history;
* **the median is not computed anywhere in this repository.** There is no
  synthetic 20-report chart, no simulated latency, no seeded corpus standing in
  for real reports. Any of those would be a fabricated SLA result;
* the DoD row is recorded `HUMAN-GATED` / `NOT-RUN (method: this file)`, and what
  would make it real is a human filing and closing reports in the public queue.

## Who owns what

| thing | owner |
| --- | --- |
| the payload contract | this repository (`docs/contracts/breakage-report-v1.md`) |
| the fixture queue | this repository (local, `fixture`-labelled) |
| the live queue and its SLA | the list-corpus maintainer (human) |
| filing a real report | a human, with that queue's credentials |
