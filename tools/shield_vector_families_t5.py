#!/usr/bin/env python3
"""tools/shield_vector_families_t5.py — the P11-T5 emitter family
(`event-emit` ⇒ living block-event-v1 rows), split out of
gen_shield_vectors.py by the touched-file size law (the same split as
shield_vector_families_t4.py). Pins: the canonical row shape, redaction
AT CREATION (query/fragment/port never reach `target`), the int64 wire
law for epoch-scale numerics (mojom BlockEvent declares ts_millis/tab_id
int64), every closed `why_code` (vocabulary law — each of the 11 codes
appears at least once, with its reason-code-table default action), every
frozen action k-spelling, the zero boundaries, the contract-doc golden
instance, and all 22 emitter `kMalformedInput` detail tokens. There is no
kRejected class: the emitter has no content-conflict semantics.
"""
from __future__ import annotations

from shield_vectors_kit import Gen, ctx  # noqa: E402

EMIT_CTX = ctx("https://tracker.example/ad.js?utm_source=x#player",
               "tracker.example", request_class="kScript")

BASE = {"action": "kBlocked", "context": EMIT_CTX, "seq": 7,
        "ts_millis": 1234, "why_code": "rule-blocked"}
FULL = dict(BASE, bundle_version=2, list_id="l-1",
            rule="||tracker.example^", rule_id="r-1", tab_id=3)

# The contract-document instance (docs/contracts/block-event-v1.md §Shape):
# its `.row` IS docs/contracts/tests/golden-block-event.json — byte-verified
# from both backends by docs/contracts/tests/test_block_event.py and pinned
# here as a vector, so the golden rides the 274-case byte-parity law too.
GOLDEN_ARGS = {
    "action": "kBlocked", "bundle_version": 3,
    "context": {
        "identity": {"value": "xr:00000000-0000-4000-8000-000000000001"},
        "origin": {"registrable_domain": "tracker.example",
                   "scheme": "https"},
        "request_class": "kScript",
        "url": "https://tracker.example/ad.js?utm_source=newsletter#player"},
    "list_id": "l-1", "rule": "||tracker.example^", "rule_id": "r-1",
    "seq": 41, "tab_id": 7, "ts_millis": 1750000000123,
    "why_code": "rule-blocked"}

# default_action per why_code, mirroring docs/shield/reason-codes.json
# (the sync is pytest-asserted; this list is the vectors' usage side).
WHY_TABLE = [("rule-blocked", "kBlocked"), ("rule-allowed", "kAllowed"),
             ("rule-redirected", "kRedirected"),
             ("rule-replaced", "kBlocked"), ("no-match", "kAllowed"),
             ("no-bundle", "kAllowed"), ("exception-scope", "kAllowed"),
             ("engine-dead-fail-open", "kAllowed"),
             ("engine-poisoned-fail-open", "kAllowed"),
             ("kill-switch", "kAllowed"),
             ("route-loss-fail-closed", "kBlocked")]


def fam_events(g: Gen) -> None:
    g.add("e-emit-golden-instance", "event-emit", GOLDEN_ARGS)
    g.add("e-emit-happy-full", "event-emit", FULL)
    g.add("e-emit-defaults", "event-emit", BASE)
    for action, why in (("kAllowed", "rule-allowed"),
                        ("kRedirected", "rule-redirected"),
                        ("kUpgraded", "rule-redirected")):
        g.add(f"e-emit-action-{action[1:].lower()}", "event-emit",
              dict(BASE, action=action, why_code=why))
    for i, (why, action) in enumerate(WHY_TABLE):
        g.add(f"e-emit-why-{why}", "event-emit",
              dict(BASE, seq=100 + i, action=action, why_code=why))
    g.add("e-emit-redact-shop", "event-emit", dict(FULL, context=ctx(
        "https://shop.example/cart?cc=4111111111111111#pay",
        "shop.example", request_class="kNavigation")))
    g.add("e-emit-redact-port", "event-emit", dict(FULL, context=ctx(
        "https://t.example:8443/a.js?x=1", "t.example")))
    g.add("e-emit-zero-boundaries", "event-emit",
          dict(BASE, seq=0, ts_millis=0, tab_id=0, bundle_version=0))
    g.add("e-emit-http-origin", "event-emit", dict(BASE, context={
        "identity": {"value": "xr:a"},
        "origin": {"scheme": "http", "registrable_domain": "plain.example"},
        "url": "http://plain.example/p?q=1",
        "request_class": "kNavigation"}))
    g.add("e-emit-epoch-ts", "event-emit",
          dict(BASE, ts_millis=1750000000123))  # int64 wire law
    g.add("e-emit-big-ints", "event-emit",
          dict(BASE, seq=4000000000, tab_id=5000000000,
               bundle_version=3000000000))

    def drop(key: str) -> dict:
        return {k: v for k, v in BASE.items() if k != key}

    malformed = [
        ("e-emit-bad-action", dict(BASE, action="blocked")),
        ("e-emit-bad-why", dict(BASE, why_code="because")),
        ("e-emit-missing-seq", drop("seq")),
        ("e-emit-neg-seq", dict(BASE, seq=-1)),
        ("e-emit-float-seq", dict(BASE, seq=7.5)),
        ("e-emit-missing-ts", drop("ts_millis")),
        ("e-emit-missing-action", drop("action")),
        ("e-emit-missing-why", drop("why_code")),
        ("e-emit-missing-context", drop("context")),
        ("e-emit-action-not-string", dict(BASE, action=3)),
        ("e-emit-why-not-string", dict(BASE, why_code=3)),
        ("e-emit-rule-not-string", dict(BASE, rule=7)),
        ("e-emit-rule-id-not-string", dict(BASE, rule_id=7)),
        ("e-emit-list-id-not-string", dict(BASE, list_id=7)),
        ("e-emit-bad-tab-id", dict(BASE, tab_id=-1)),
        ("e-emit-tab-id-not-int", dict(BASE, tab_id="3")),
        ("e-emit-bad-bundle-version", dict(BASE, bundle_version=-2)),
        ("e-emit-unknown-field", dict(BASE, extra=1)),
        ("e-emit-ctx-unparsable-url",
         dict(BASE, context=dict(EMIT_CTX, url="not a url"))),
        ("e-emit-ctx-unknown-field",
         dict(BASE, context=dict(EMIT_CTX, zzz=1))),
        ("e-emit-ctx-bad-class",
         dict(BASE, context=dict(EMIT_CTX, request_class="kX"))),
        ("e-emit-ctx-empty-identity",
         dict(BASE, context=dict(EMIT_CTX, identity={"value": ""}))),
    ]
    for cid, args in malformed:
        g.add(cid, "event-emit", args)
