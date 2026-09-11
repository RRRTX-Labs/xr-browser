#!/usr/bin/env python3
"""tools/shield_vector_families.py — the case families of the shield
golden vectors (P11-T2, split by responsibility out of
gen_shield_vectors.py for the touched-file size law; the
update_vectors_families.py pattern). Each fam_* builder appends its
family's cases through the kit's Gen, which captures each expectation as
the Python reference's real stdout — deterministic, no clock, no RNG.
The driver (gen_shield_vectors.py) calls the families in a FIXED order;
the emitted vector bytes depend on that order, so it is part of the
byte-identical-regen law.
"""
from __future__ import annotations

from shield_vectors_kit import (  # noqa: E402
    BUNDLE, CTX, GOOD_MANIFEST, MATCH_URLS, SAMPLE_EVENT, STATE_EMPTY, Gen,
    canonical, ctx, slot, state_v3,
)


def fam_frozen(g: Gen) -> None:
    g.add("status-frozen-fixture", "Status",
          {"identity": {"value": "xr:...-001"},
           "origin": {"scheme": "https",
                      "registrable_domain": "example.com"}})
    g.add("status-flag-off", "Status",
          {"identity": {"value": "xr:...-001"},
           "origin": {"scheme": "https",
                      "registrable_domain": "example.com"}},
          flags=["--flag", "xr_shield_v1=off"])
    g.add("status-http-origin", "Status",
          {"identity": {"value": "xr:a"},
           "origin": {"scheme": "http", "registrable_domain": "e.com"}})
    for i, (cid, args) in enumerate([
            ("status-empty-identity", {"identity": {"value": ""},
                                       "origin": {"scheme": "https"}}),
            ("status-missing-identity", {"origin": {"scheme": "https"}}),
            ("status-identity-not-object", {"identity": "x",
                                            "origin": {"scheme": "https"}}),
            ("status-ftp-origin", {"identity": {"value": "x"},
                                   "origin": {"scheme": "ftp"}}),
            ("status-missing-origin", {"identity": {"value": "x"}}),
            ("status-unknown-field", {"identity": {"value": "x"},
                                      "origin": {"scheme": "https"},
                                      "extra": 1}),
            ("status-ring-malformed", {"identity": {"value": "x"},
                                       "origin": {"scheme": "https"},
                                       "ring": "no"}),
    ]):
        g.add(cid, "Status", args)
    g.add("status-ring-count", "Status",
          {"identity": {"value": "xr:a"}, "origin": {"scheme": "https"},
           "ring": [SAMPLE_EVENT, {**SAMPLE_EVENT, "action": "kAllowed"},
                    {**SAMPLE_EVENT, "identity": {"value": "xr:b"}}]})
    g.add("events-frozen-sample", "RecentEvents",
          {"identity": {"value": "xr:...-001"}, "max_events": 5})
    g.add("events-sample-cap-1", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 1})
    g.add("events-max-0", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 0})
    g.add("events-max-missing", "RecentEvents", {"identity": {"value": "xr:a"}})
    g.add("events-max-negative", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": -3})
    g.add("events-max-not-int", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": "x"})
    g.add("events-identity-not-object", "RecentEvents",
          {"identity": "x", "max_events": 1})
    g.add("events-ring-view", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 9,
           "ring": [SAMPLE_EVENT, {**SAMPLE_EVENT, "ts_millis": 2000},
                    {**SAMPLE_EVENT, "identity": {"value": "xr:b"},
                     "ts_millis": 3000}]})
    g.add("events-ring-newest-first", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 2,
           "ring": [{**SAMPLE_EVENT, "ts_millis": t} for t in range(5)]})
    g.add("events-ring-malformed-event", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 1,
           "ring": [{"bad": 1}]})
    g.add("events-ring-unknown-action", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 1,
           "ring": [{**SAMPLE_EVENT, "action": "blocked"}]})
    g.add("events-ring-empty", "RecentEvents",
          {"identity": {"value": "xr:a"}, "max_events": 5, "ring": []})
    g.add("status-ring-empty", "Status",
          {"identity": {"value": "xr:a"}, "origin": {"scheme": "https"},
           "ring": []})


def fam_flag_posture(g: Gen) -> None:
    g.add("flag-status-on", "flag-status", {})
    g.add("flag-status-off", "flag-status", {},
          flags=["--flag", "xr_shield_v1=off"])
    g.add("flag-status-unknown-field", "flag-status", {"x": 1})
    names = ["engine_alive", "engine_poisoned", "route_bound",
             "kill_switch_on"]
    for mask in range(16):
        args = {n: bool(mask & (1 << i)) for i, n in enumerate(names)}
        g.add(f"posture-truth-{mask:02d}", "posture", args)
    g.add("posture-defaults", "posture", {})
    g.add("posture-not-bool", "posture", {"engine_alive": "yes"})
    g.add("posture-unknown-field", "posture", {"switch": True})


def fam_match(g: Gen) -> None:
    for cid, url, dom in MATCH_URLS:
        extra: dict = {}
        if cid == "m-first-party-field":
            extra = {"first_party": True, "tab_type": "workspace",
                     "workspace": "ws1"}
        rc = "kNavigation" if cid == "m-navigation-class" else "kSubresource"
        g.add(cid, "match", {"context": ctx(url, dom, request_class=rc,
                                            **extra), "bundle": BUNDLE})
    g.add("m-no-bundle", "match", {"context": CTX})
    for cid, flags in [
            ("m-engine-dead", {"engine_alive": False}),
            ("m-engine-poisoned", {"engine_poisoned": True}),
            ("m-kill-switch", {"kill_switch_on": True}),
            ("m-route-loss", {"route_bound": False}),
            ("m-route-loss-absolute", {"route_bound": False,
                                       "kill_switch_on": True,
                                       "engine_alive": False}),
            ("m-poison-outranks-kill", {"engine_poisoned": True,
                                        "kill_switch_on": True}),
    ]:
        g.add(cid, "match", {"context": CTX, "bundle": BUNDLE, **flags})
    scopes = [
        ("m-scope-site-rule", [{"scope_id": "s1", "site": "tracker.example",
                                "rule_id": "r1", "reason": "user"}]),
        ("m-scope-identity-coupling", [{"scope_id": "s1",
                                        "identity": "xr:other",
                                        "rule_id": "r1", "reason": "user"}]),
        ("m-scope-identity-match", [{"scope_id": "s1", "identity": "xr:a",
                                     "rule_id": "r1", "reason": "user"}]),
        ("m-scope-workspace-miss", [{"scope_id": "s1", "workspace": "ws1",
                                     "reason": "w"}]),
        ("m-scope-list-id", [{"scope_id": "s1", "list_id": "l1",
                              "rule_id": "r1", "reason": "l"}]),
        ("m-scope-list-id-miss", [{"scope_id": "s1", "list_id": "l2",
                                   "rule_id": "r1", "reason": "l"}]),
        ("m-scope-all-empty", [{"scope_id": "s1", "reason": "everything"}]),
        ("m-scope-redirect-suppressed", [{"scope_id": "s1",
                                          "site": "ads.example",
                                          "reason": "user"}]),
    ]
    for cid, sc in scopes:
        c = CTX
        if cid == "m-scope-redirect-suppressed":
            c = ctx("https://ads.example/banner", "ads.example")
        if cid == "m-scope-workspace-miss":
            c = ctx("https://tracker.example/a.js", "tracker.example",
                    workspace="ws2")
        g.add(cid, "match", {"context": c, "bundle": BUNDLE, "scopes": sc})
    g.add("m-scope-expired-boundary", "match",
          {"context": CTX, "bundle": BUNDLE, "now_mono": 500,
           "scopes": [{"scope_id": "s1", "expiry_mono": 500,
                       "reason": "temp"}]})
    g.add("m-scope-active-boundary", "match",
          {"context": CTX, "bundle": BUNDLE, "now_mono": 499,
           "scopes": [{"scope_id": "s1", "expiry_mono": 500,
                       "reason": "temp"}]})
    g.add("m-scope-never-expires", "match",
          {"context": CTX, "bundle": BUNDLE, "now_mono": 10 ** 9,
           "scopes": [{"scope_id": "s1", "expiry_mono": -1,
                       "rule_id": "r1", "reason": "forever"}]})
    # refusals
    g.add("m-missing-context", "match", {})
    g.add("m-empty-identity", "match", {"context": {"identity": {"value": ""}}})
    g.add("m-unknown-tab-type", "match", {"context": {**CTX,
                                                      "tab_type": "guest"}})
    g.add("m-unknown-request-class", "match",
          {"context": {**CTX, "request_class": "kFetch"}})
    g.add("m-unknown-context-field", "match",
          {"context": {**CTX, "incognito": True}})
    g.add("m-userinfo-url-refused", "match",
          {"context": ctx("https://user:pw@tracker.example/a.js",
                          "tracker.example")})
    g.add("m-ftp-url-refused", "match",
          {"context": ctx("ftp://tracker.example/a.js", "tracker.example")})
    g.add("m-bundle-wrong-schema", "match",
          {"context": CTX, "bundle": {"schema": "wrong"}})
    g.add("m-bundle-cosmetic-directive", "match",
          {"context": CTX, "bundle": {**BUNDLE, "lists": [
              {**BUNDLE["lists"][0],
               "rules": [{"id": "rx", "kind": "network", "filter": "##.ad",
                          "action": "block"}]}]}})
    g.add("m-scope-missing-reason", "match",
          {"context": CTX, "bundle": BUNDLE, "scopes": [{"scope_id": "s"}]})
    g.add("m-scope-not-array", "match",
          {"context": CTX, "bundle": BUNDLE, "scopes": "x"})
    g.add("m-now-mono-negative", "match",
          {"context": CTX, "bundle": BUNDLE, "now_mono": -1})
    g.add("m-unknown-arg", "match", {"context": CTX, "x": 1})
    g.add("m-tab-type-incognito", "match",
          {"context": ctx("https://tracker.example/a.js", "tracker.example",
                          tab_type="incognito"), "bundle": BUNDLE})
    g.add("m-workspace-context", "match",
          {"context": ctx("https://tracker.example/a.js", "tracker.example",
                          tab_type="workspace", workspace="ws1"),
           "bundle": BUNDLE})
    g.add("b-load-comment-refused", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "! comment",
               "action": "block"}]}]}})
    g.add("b-load-at-syntax-refused", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "@@||a.example^",
               "action": "allow"}]}]}})


def fam_bundle(g: Gen) -> None:
    g.add("b-load-summary", "bundle-load", {"bundle": BUNDLE})
    g.add("b-load-empty-lists", "bundle-load",
          {"bundle": {**BUNDLE, "lists": []}})
    g.add("b-load-version-zero", "bundle-load",
          {"bundle": {**BUNDLE, "bundle_version": 0}})
    g.add("b-load-unknown-top", "bundle-load",
          {"bundle": {**BUNDLE, "signed_by": "x"}})
    g.add("b-load-unknown-list-key", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0],
                                           "license": "MIT"}]}})
    g.add("b-load-regex-refused", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "/re/",
               "action": "block"}]}]}})
    g.add("b-load-options-refused", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "||a.example^$x",
               "action": "block"}]}]}})
    g.add("b-load-interior-pipe", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "a|b",
               "action": "block"}]}]}})
    g.add("b-load-duplicate-rule-id", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              BUNDLE["lists"][0]["rules"][0],
              BUNDLE["lists"][0]["rules"][0]]}]}})
    g.add("b-load-redirect-no-resource", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "redirect", "filter": "||a.example^",
               "action": "redirect"}]}]}})
    g.add("b-load-resource-no-redirect", "bundle-load",
          {"bundle": {**BUNDLE, "lists": [{**BUNDLE["lists"][0], "rules": [
              {"id": "r", "kind": "network", "filter": "||a.example^",
               "action": "block", "resource": "x"}]}]}})
    g.add("b-load-missing-bundle", "bundle-load", {})
    g.add("b-check-bound", "bundle-check",
          {"bundle": BUNDLE, "manifest": GOOD_MANIFEST})
    g.add("b-check-rule-count", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": [
              {**GOOD_MANIFEST["lists"][0], "rules": 1}]}})
    g.add("b-check-sha", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": [
              {**GOOD_MANIFEST["lists"][0], "sha256": "0" * 64}]}})
    g.add("b-check-name", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": [
              {**GOOD_MANIFEST["lists"][0], "name": "other"}]}})
    g.add("b-check-count", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": []}})
    g.add("b-check-unknown-manifest-key", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "extra": 1}})
    g.add("b-check-unknown-entry-key", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": [
              {**GOOD_MANIFEST["lists"][0], "license": "MIT"}]}})
    g.add("b-check-bad-sha-length", "bundle-check",
          {"bundle": BUNDLE, "manifest": {**GOOD_MANIFEST, "lists": [
              {**GOOD_MANIFEST["lists"][0], "sha256": "abc"}]}})
    g.add("b-check-missing-manifest", "bundle-check", {"bundle": BUNDLE})


def fam_apply(g: Gen) -> None:
    b4 = {**BUNDLE, "bundle_version": 4}
    b2 = {**BUNDLE, "bundle_version": 2}
    other = {**BUNDLE, "name": "other-bundle"}
    s1 = state_v3()
    s2 = {"active": slot("xr-default", 4), "lkg": slot("xr-default", 3),
          "pins": [slot("xr-default", 3), slot("xr-default", 4)],
          "last_apply_mono": 200}
    g.add("a-fresh", "apply", {"bundle": BUNDLE, "state": STATE_EMPTY,
                               "now_mono": 100})
    g.add("a-equal-reoffer", "apply",
          {"bundle": BUNDLE, "state": s1, "now_mono": 200})
    g.add("a-downgrade", "apply", {"bundle": b2, "state": s1,
                                   "now_mono": 200})
    g.add("a-upgrade-lkg", "apply", {"bundle": b4, "state": s1,
                                     "now_mono": 200})
    g.add("a-second-upgrade-pins", "apply",
          {"bundle": {**BUNDLE, "bundle_version": 5}, "state": s2,
           "now_mono": 300})
    g.add("a-cross-bundle-id", "apply",
          {"bundle": other, "state": s2, "now_mono": 250})
    g.add("a-stale-clock", "apply", {"bundle": b4, "state": s1,
                                     "now_mono": 50})
    g.add("a-equal-clock-ok", "apply",
          {"bundle": b4, "state": s1, "now_mono": 100})
    g.add("a-hot-pin-out", "apply",
          {"bundle": b4, "state": {**s1, "pins": []}, "now_mono": 300})
    g.add("a-too-many-pins", "apply",
          {"bundle": b4, "state": {**s1, "pins": s1["pins"] * 3},
           "now_mono": 300})
    g.add("a-lkg-duplicates-active", "apply",
          {"bundle": b4, "state": {**s1, "lkg": s1["active"]},
           "now_mono": 300})
    g.add("a-missing-now-mono", "apply", {"bundle": BUNDLE, "state": s1})
    g.add("a-missing-state", "apply", {"bundle": BUNDLE, "now_mono": 1})
    g.add("a-missing-bundle", "apply", {"state": STATE_EMPTY,
                                        "now_mono": 1})
    g.add("a-state-unknown-field", "apply",
          {"bundle": BUNDLE, "state": {**STATE_EMPTY, "x": 1},
           "now_mono": 1})
    g.add("a-slot-short-digest", "apply",
          {"bundle": BUNDLE,
           "state": {"active": {"present": True, "bundle_id": "b",
                                "digest": "abc", "version": 1},
                     "lkg": {"present": False}, "pins": [],
                     "last_apply_mono": -1},
           "now_mono": 1})
    g.add("a-slot-bad-present", "apply",
          {"bundle": BUNDLE,
           "state": {"active": {"present": "yes"}, "lkg": {"present": False},
                     "pins": [], "last_apply_mono": -1},
           "now_mono": 1})


def fam_protocol(g: Gen) -> None:
    g.add("p-unknown-method", "bogus", {})
    g.add("p-bad-stdin-json", "match", {}, raw="not json at all")
    g.add("p-args-not-object", "match", {},
          raw=canonical({"method": "match", "args": 5}))
