#!/usr/bin/env python3
"""tools/shield_vector_families_t6.py — the P11-T6 dev-only debug-page
family (`page-states` + `debug-page` + the `--build-channel` gate), split
out of gen_shield_vectors.py by the touched-file size law (the same split
as the t4/t5 families). Pins: the page-state union (posture-reason
vocabulary — ui/shield/shield.ts must render every state,
tools/shield_state_check.py holds the sync), the REAL channel gate
(default "release" fails CLOSED; dev renders; nightly-test refuses typed),
the enterprise kill path (force-disable WINS over the caller's
kill_switch_on — no silent re-enable; the reason passes through VERBATIM,
unicode included; a force-disable without a reason is malformed because
it IS a silent suppression), the amber/green distinction on the page, the
riding-state rows (bundle refusals, apply state echo, ring chip count,
scope count, last-apply echo — caller-supplied time, no clock), and every
debug-page `kMalformedInput` detail token.
"""
from __future__ import annotations

from shield_vectors_kit import Gen  # noqa: E402

DEV = ["--build-channel", "dev"]
REL = ["--build-channel", "release"]
NT = ["--build-channel", "nightly-test"]

# A minimal VALID xr-list-bundle document (all six keys), carrying one
# compiler-refusal entry so the page's refused-directive row renders.
BUNDLE6 = {
    "bundle_version": 3,
    "lists": [
        {"attribution": "The EasyList authors (https://easylist.to/)",
         "name": "l1",
         "rules": [{"action": "block", "filter": "||tracker.example^",
                    "id": "r1", "kind": "network"}]},
    ],
    "name": "xr-default",
    "refusals": [{"count": 2, "directive": "##.ad",
                  "reason": "unsupported-directive:cosmetic-hash"}],
    "schema": "xr-list-bundle",
    "schema_version": 1,
}

# A valid apply state (active present, pins contain active — the a-equal-
# reoffer fixture shape); debug-page ECHOES it as given (no invariant
# gate — the page reports honestly, `apply` stays the gatekeeper).
STATE6 = {
    "active": {"bundle_id": "xr-default",
               "digest": "4e2a696549d6940e7ff6cc6cdb0cc58da13b1417e1e326e"
                         "695a9fc0a2c3f28",
               "present": True, "version": 3},
    "last_apply_mono": 100,
    "lkg": {"present": False},
    "pins": [{"bundle_id": "xr-default",
              "digest": "4e2a696549d6940e7ff6cc6cdb0cc58da13b1417e1e326e"
                        "695a9fc0a2c3f28",
              "present": True, "version": 3}],
}

# One kBlocked + one kAllowed event: chip_count counts kBlocked only.
RING6 = [
    {"action": "kBlocked", "identity": {"value": "xr:a"},
     "list_provenance": "xr-default-list-v1",
     "origin": {"registrable_domain": "tracker.example", "scheme": "https"},
     "request_class": "kScript", "rule": "||tracker.example^", "tab_id": 1,
     "target": "https://tracker.example/a.js", "ts_millis": 1000},
    {"action": "kAllowed", "identity": {"value": "xr:a"},
     "list_provenance": "xr-default-list-v1",
     "origin": {"registrable_domain": "safe.example", "scheme": "https"},
     "request_class": "kSubresource", "rule": "||safe.example^", "tab_id": 1,
     "target": "https://safe.example/ok.js", "ts_millis": 1001},
]

SCOPE6 = [{"reason": "user-allow", "scope_id": "ex-1", "site": "example.com"}]

LAST_APPLY6 = {"duration_ms": 40, "result": "ok", "ts_millis": 1750000000123}

FULL_ARGS = {"bundle": BUNDLE6, "last_apply": LAST_APPLY6, "ring": RING6,
             "scopes": SCOPE6, "state": STATE6}


def fam_page(g: Gen) -> None:
    # ---- the page-state union (public vocabulary; NOT channel-gated) ----
    g.add("p-page-states", "page-states", {})
    g.add("p-page-states-unknown-field", "page-states", {"x": 1})

    # ---- the REAL channel gate (a startup option, never a comment) -----
    g.add("p-debug-refused-default-channel", "debug-page", {})
    g.add("p-debug-refused-release", "debug-page", {}, flags=REL)
    g.add("p-debug-refused-nightly-test", "debug-page", {}, flags=NT)

    # ---- dev opens the page: minimal + full riding-state goldens --------
    g.add("p-debug-dev-minimal", "debug-page", {}, flags=DEV)
    g.add("p-debug-dev-full", "debug-page", FULL_ARGS, flags=DEV)

    # ---- every page state renders (amber != "blocked nothing") ----------
    g.add("p-debug-state-engine-dead", "debug-page",
          {"engine_alive": False}, flags=DEV)
    g.add("p-debug-state-engine-poisoned", "debug-page",
          {"engine_poisoned": True}, flags=DEV)
    g.add("p-debug-state-kill-switch", "debug-page",
          {"kill_switch_on": True}, flags=DEV)
    g.add("p-debug-state-route-loss", "debug-page",
          {"route_bound": False}, flags=DEV)

    # ---- the enterprise kill path (T6's law trio) ------------------------
    # force-disable WINS over the caller's kill_switch_on (policy is
    # final; no silent re-enable), reason VERBATIM (unicode included),
    # and a not-forced enterprise row is inert.
    g.add("p-debug-enterprise-force-wins", "debug-page",
          {"enterprise": {"force_disabled": True,
                          "reason": "IT policy 4711: shielding mandated off"},
           "kill_switch_on": False}, flags=DEV)
    g.add("p-debug-enterprise-reason-verbatim-unicode", "debug-page",
          {"enterprise": {"force_disabled": True,
                          "reason": "Unternehmensrichtlinie 4711 — Schild "
                                    "aus"}}, flags=DEV)
    g.add("p-debug-enterprise-not-forced", "debug-page",
          {"enterprise": {"force_disabled": False, "reason": ""}}, flags=DEV)

    # ---- the closed kMalformedInput token set ----------------------------
    g.add("p-debug-unknown-field", "debug-page", {"bogus": 1}, flags=DEV)
    g.add("p-debug-posture-not-bool", "debug-page",
          {"engine_alive": "yes"}, flags=DEV)
    g.add("p-debug-enterprise-not-object", "debug-page",
          {"enterprise": 5}, flags=DEV)
    g.add("p-debug-enterprise-unknown-key", "debug-page",
          {"enterprise": {"force_disabled": True, "reason": "r", "x": 1}},
          flags=DEV)
    g.add("p-debug-missing-force-disabled", "debug-page",
          {"enterprise": {"reason": "r"}}, flags=DEV)
    g.add("p-debug-force-disabled-not-bool", "debug-page",
          {"enterprise": {"force_disabled": "yes", "reason": "r"}},
          flags=DEV)
    g.add("p-debug-missing-enterprise-reason", "debug-page",
          {"enterprise": {"force_disabled": True}}, flags=DEV)
    g.add("p-debug-empty-enterprise-reason", "debug-page",
          {"enterprise": {"force_disabled": True, "reason": ""}}, flags=DEV)
    g.add("p-debug-reason-without-force-disabled", "debug-page",
          {"enterprise": {"force_disabled": False, "reason": "x"}},
          flags=DEV)
    g.add("p-debug-reason-not-string-without-force", "debug-page",
          {"enterprise": {"force_disabled": False, "reason": 5}}, flags=DEV)
    g.add("p-debug-last-apply-not-object", "debug-page",
          {"last_apply": 5}, flags=DEV)
    g.add("p-debug-last-apply-unknown-key", "debug-page",
          {"last_apply": {"duration_ms": 1, "result": "ok", "ts_millis": 1,
                          "x": 1}}, flags=DEV)
    g.add("p-debug-bad-last-apply-negative-ts", "debug-page",
          {"last_apply": {"duration_ms": 1, "result": "ok",
                          "ts_millis": -1}}, flags=DEV)
    g.add("p-debug-bad-last-apply-missing-duration", "debug-page",
          {"last_apply": {"result": "ok", "ts_millis": 1}}, flags=DEV)
    g.add("p-debug-bad-last-apply-empty-result", "debug-page",
          {"last_apply": {"duration_ms": 1, "result": "",
                          "ts_millis": 1}}, flags=DEV)
    g.add("p-debug-ring-not-array", "debug-page", {"ring": 5}, flags=DEV)
    g.add("p-debug-scopes-not-array", "debug-page", {"scopes": 5},
          flags=DEV)
    g.add("p-debug-state-not-object", "debug-page", {"state": 5}, flags=DEV)
    # a grammar-violating bundle refuses the WHOLE page (the bundle-load
    # kRejected law rides through debug-page unchanged)
    g.add("p-debug-bundle-grammar-refusal", "debug-page",
          {"bundle": dict(BUNDLE6, lists=[
              {"attribution": "The EasyList authors (https://easylist.to/)",
               "name": "l1",
               "rules": [{"action": "block", "filter": "! comment",
                          "id": "r1", "kind": "network"}]}])}, flags=DEV)
