# ADR-0050: `breakage-report-v1` — a report carries context, not the page, and its queue is a fixture

- **Status:** PROPOSED (drafted by the P13-CLOSE coding agent; ratification rides
  HG-26/HG-35; the LIVE queue is HG-33)
- **Date:** 2026-09-30
- **Deciders (humans):** Privacy lead + Platform lead (this is the only artifact
  in the product that both leaves the machine and describes the user's page)
- **Plan anchor:** §4 P13-T4; plan DoD "corpus-linked breakage pipeline live w/
  48 h median proven on 20 seeded reports".

## Context

A breakage report is a data-leak audit item wearing a form. The plan's DoD asks
for a live pipeline with a proven 48 h median; the honest position is that the
live half is a production act over a public queue, and the sandbox cannot perform
it (HG-33). Two failure modes are therefore close at hand and both are
disqualifying: a *simulated* median or synthetic SLA chart, and a `gh` write to a
private repository presented as "the public queue".

## Decision

1. **The payload carries CONTEXT and nothing else**, schema-enforced:
   `origin{scheme, registrable_domain}`, a UA-LESS `browser_version_tag`, the
   matched `rule_id`, `list_id` + `bundle_version`, the `action`. Page content,
   cookies, full URLs, query strings, fragments and user agents are absent **by
   schema** (`additionalProperties: false` everywhere), so they are refused
   before a report is written rather than scrubbed after.
2. **Refusals happen pre-send, by class, with the bytes withheld.** Six smuggle
   classes (url-with-query, cookie, user-agent, selector, HTML, credentials) are
   refused before anything is produced, and the offender's bytes must be absent
   from every byte the tool emitted. The refusal MESSAGE carries the class and a
   byte count, never the matched text: an error message must not become the leak.
3. **`queue` is `const: "fixture"`.** There is no live mode in this repository, so
   a payload claiming one cannot validate. The local queue's path must contain
   `fixture`, and the tool prints `queue_mode: fixture`.
4. **The SLA is DATA** (`{label, hours, class}`), never a rendered sentence. The
   48 h figure is a declared target; **no median is computed anywhere**, and no
   20-report chart is drawn, because nothing here measured them.
5. **No second transport.** The plan says a report reuses P10's update channel.
   That channel is an envelope fetch (GET + minisign) with no POST payload shape,
   so this tool contains no network code at all (asserted by test) and the POST
   shape for that channel is named as P14 work. Adding a second egress path is a
   failure condition, not an implementation choice.
6. **The confirmation is non-attentional**: inline, one click, and the core
   THROWS on notification vocabulary (`ui/panel/breakage-tab.ts`).

## Consequences

* The live half is recorded `HUMAN-GATED` / `NOT-RUN (method: docs/panel/breakage-report.md)`:
  filing a real report, the queue's owner, and what the 48 h median means in
  production are all described there and performed by a human.
* The tab and the tool refuse the same classes in two languages (TS core rows,
  Python pre-send refusal), which is deliberate: the payload is built where the
  user can see it, and refused where it can actually escape.

## Alternatives rejected

Carrying the URL with its query and redacting at send time (scrubbing after
serialization is the leak), signing the payload client-side (new crypto, and
nothing to sign against here), and treating the fixture queue as a "staging" mode
(a fixture must not be able to travel as production).
