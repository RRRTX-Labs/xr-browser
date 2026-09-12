#!/usr/bin/env python3
"""tools/shield_vector_families_t4.py — the P11-T4 exception-surface family
of the shield golden vectors (split by responsibility from
shield_vector_families.py for the touched-file size law — that file sits at
341 lines and this family is ~60 cases). Same machinery: every `expect` is
the Python reference's real stdout, captured by the kit's Gen; the driver
calls this family in the FIXED assembly order (byte-identical-regen law).

Axes covered: exception-add (append/normalization/order, content-conflict
refusal, every T2 scope-grammar parse error via the new arg), exception-
remove (survivors, unknown-id refusal, id validation), exception-sweep
(inclusive expiry boundary, forever scopes, required non-negative as-of),
site-toggle (canonical scope shape, already-on/already-off refusals, the
shared id space with manual scopes, arg validation).
"""
from __future__ import annotations

from shield_vectors_kit import Gen  # noqa: E402

# Two legal standing scopes (reason is REQUIRED on every scope — T2 law).
EX_A = {"scope_id": "ex-a", "identity": "profile-a", "reason": "user-allow"}
EX_B = {"scope_id": "ex-b", "rule_id": "r-7", "list_id": "l1",
        "reason": "false-positive"}
# What site-toggle emits for example.com (canonical 8-key form).
TOGGLED = [{"expiry_mono": -1, "identity": "", "list_id": "",
            "reason": "user-site-toggle", "rule_id": "",
            "scope_id": "site-toggle:example.com", "site": "example.com",
            "workspace": ""}]


def fam_exceptions(g: Gen) -> None:
    # ---- exception-add -----------------------------------------------------
    g.add("x-add-site-scope", "exception-add",
          {"scope": {"scope_id": "ex-1", "site": "example.com",
                     "reason": "user-allow"}})
    g.add("x-add-onto-existing", "exception-add",
          {"scopes": [EX_A, EX_B],
           "scope": {"scope_id": "ex-c", "workspace": "ws",
                     "reason": "work"}})
    g.add("x-add-rule-scope", "exception-add",
          {"scope": {"scope_id": "ex-r", "rule_id": "r-3", "list_id": "l1",
                     "reason": "false-positive"}})
    g.add("x-add-identity-scope", "exception-add",
          {"scope": {"scope_id": "ex-i", "identity": "profile-b",
                     "reason": "user-allow"}})
    g.add("x-add-expiry", "exception-add",
          {"scope": {"scope_id": "ex-t", "site": "news.example",
                     "expiry_mono": 700, "reason": "temporary"}})
    g.add("x-add-expiry-zero", "exception-add",
          {"scope": {"scope_id": "ex-z", "expiry_mono": 0,
                     "reason": "expires-at-zero"}})
    g.add("x-add-all-dimensions", "exception-add",
          {"scope": {"scope_id": "ex-full", "identity": "p",
                     "site": "s.example", "workspace": "w",
                     "rule_id": "r-1", "list_id": "l1", "expiry_mono": 42,
                     "reason": "everything"}})
    g.add("x-add-order-preserved", "exception-add",
          {"scopes": [EX_B, EX_A],
           "scope": {"scope_id": "ex-c", "reason": "third"}})
    g.add("x-add-dup-rejected", "exception-add",
          {"scopes": [EX_A, EX_B],
           "scope": {"scope_id": "ex-a", "site": "other.example",
                     "reason": "collision"}})
    g.add("x-add-dup-rejected-toggle-id", "exception-add",
          {"scopes": TOGGLED,
           "scope": {"scope_id": "site-toggle:example.com",
                     "site": "example.com", "reason": "manual"}})
    g.add("x-add-missing-scope", "exception-add", {})
    g.add("x-add-missing-reason", "exception-add",
          {"scope": {"scope_id": "ex-9", "site": "x.example"}})
    g.add("x-add-empty-reason", "exception-add",
          {"scope": {"scope_id": "ex-9", "reason": ""}})
    g.add("x-add-bad-scope-id", "exception-add",
          {"scope": {"scope_id": "", "reason": "r"}})
    g.add("x-add-scope-not-object", "exception-add", {"scope": "ex"})
    g.add("x-add-scope-unknown-field", "exception-add",
          {"scope": {"scope_id": "ex-9", "bogus": 1, "reason": "r"}})
    g.add("x-add-field-not-string", "exception-add",
          {"scope": {"scope_id": "ex-9", "site": 5, "reason": "r"}})
    g.add("x-add-bad-expiry-string", "exception-add",
          {"scope": {"scope_id": "ex-9", "expiry_mono": "700",
                     "reason": "r"}})
    g.add("x-add-bad-expiry-negative", "exception-add",
          {"scope": {"scope_id": "ex-9", "expiry_mono": -2, "reason": "r"}})
    g.add("x-add-scopes-not-array", "exception-add",
          {"scopes": 5, "scope": {"scope_id": "e", "reason": "r"}})
    g.add("x-add-scopes-dup-in-set", "exception-add",
          {"scopes": [EX_A, EX_A],
           "scope": {"scope_id": "ex-c", "reason": "r"}})
    g.add("x-add-scopes-missing-reason-in-set", "exception-add",
          {"scopes": [{"scope_id": "ex-x", "site": "s.example"}],
           "scope": {"scope_id": "ex-c", "reason": "r"}})
    g.add("x-add-unknown-arg", "exception-add",
          {"scope": {"scope_id": "e", "reason": "r"}, "bogus": 1})

    # ---- exception-remove --------------------------------------------------
    g.add("x-remove-happy", "exception-remove",
          {"scopes": [EX_A, EX_B], "scope_id": "ex-a"})
    g.add("x-remove-last", "exception-remove",
          {"scopes": [EX_A], "scope_id": "ex-a"})
    g.add("x-remove-toggle-scope", "exception-remove",
          {"scopes": TOGGLED + [EX_A],
           "scope_id": "site-toggle:example.com"})
    g.add("x-remove-unknown-rejected", "exception-remove",
          {"scopes": [EX_A, EX_B], "scope_id": "nope"})
    g.add("x-remove-from-empty", "exception-remove",
          {"scopes": [], "scope_id": "ex-a"})
    g.add("x-remove-no-scopes-arg", "exception-remove",
          {"scope_id": "ex-a"})
    g.add("x-remove-bad-id-empty", "exception-remove",
          {"scopes": [EX_A], "scope_id": ""})
    g.add("x-remove-bad-id-not-string", "exception-remove",
          {"scopes": [EX_A], "scope_id": 7})
    g.add("x-remove-missing-id", "exception-remove", {"scopes": [EX_A]})
    g.add("x-remove-scopes-malformed", "exception-remove",
          {"scopes": [{"scope_id": "ex-x"}], "scope_id": "ex-x"})
    g.add("x-remove-unknown-arg", "exception-remove",
          {"scopes": [EX_A], "scope_id": "ex-a", "bogus": 1})

    # ---- exception-sweep ---------------------------------------------------
    sweep_set = [{"scope_id": "a", "expiry_mono": 500, "reason": "r"},
                 {"scope_id": "b", "reason": "r"},
                 {"scope_id": "c", "expiry_mono": 900, "reason": "r"}]
    g.add("x-sweep-boundary", "exception-sweep",
          {"scopes": sweep_set, "now_mono": 500})
    g.add("x-sweep-just-before", "exception-sweep",
          {"scopes": sweep_set, "now_mono": 499})
    g.add("x-sweep-just-after", "exception-sweep",
          {"scopes": sweep_set, "now_mono": 501})
    g.add("x-sweep-all-gone", "exception-sweep",
          {"scopes": sweep_set, "now_mono": 900})
    g.add("x-sweep-none-expired", "exception-sweep",
          {"scopes": sweep_set, "now_mono": 0})
    g.add("x-sweep-forever-survives", "exception-sweep",
          {"scopes": [{"scope_id": "f", "reason": "r"}],
           "now_mono": 999999})
    g.add("x-sweep-zero-expiry-zero-now", "exception-sweep",
          {"scopes": [{"scope_id": "z", "expiry_mono": 0, "reason": "r"}],
           "now_mono": 0})
    g.add("x-sweep-empty-set", "exception-sweep",
          {"scopes": [], "now_mono": 10})
    g.add("x-sweep-no-scopes-arg", "exception-sweep", {"now_mono": 10})
    g.add("x-sweep-missing-now", "exception-sweep", {"scopes": sweep_set})
    g.add("x-sweep-negative-now", "exception-sweep",
          {"scopes": sweep_set, "now_mono": -3})
    g.add("x-sweep-now-not-int", "exception-sweep",
          {"scopes": sweep_set, "now_mono": "500"})
    g.add("x-sweep-scopes-malformed", "exception-sweep",
          {"scopes": [{"scope_id": "a", "expiry_mono": 1}], "now_mono": 5})
    g.add("x-sweep-unknown-arg", "exception-sweep",
          {"scopes": [], "now_mono": 1, "bogus": 1})

    # ---- site-toggle -------------------------------------------------------
    g.add("x-toggle-on-fresh", "site-toggle",
          {"site": "example.com", "on": True})
    g.add("x-toggle-on-with-manual-set", "site-toggle",
          {"scopes": [EX_A], "site": "example.com", "on": True})
    g.add("x-toggle-on-expiry", "site-toggle",
          {"site": "news.example", "on": True, "expiry_mono": 700})
    g.add("x-toggle-on-expiry-zero", "site-toggle",
          {"site": "news.example", "on": True, "expiry_mono": 0})
    g.add("x-toggle-on-existing", "site-toggle",
          {"scopes": TOGGLED, "site": "example.com", "on": True})
    g.add("x-toggle-on-collision-manual-id", "site-toggle",
          {"scopes": [{"scope_id": "site-toggle:example.com",
                       "site": "example.com", "reason": "manual"}],
           "site": "example.com", "on": True})
    g.add("x-toggle-off-existing", "site-toggle",
          {"scopes": TOGGLED + [EX_A, EX_B], "site": "example.com",
           "on": False})
    g.add("x-toggle-off-absent", "site-toggle",
          {"scopes": [EX_A], "site": "example.com", "on": False})
    g.add("x-toggle-off-no-scopes-arg", "site-toggle",
          {"site": "example.com", "on": False})
    g.add("x-toggle-off-keeps-manual-collision", "site-toggle",
          {"scopes": [{"scope_id": "site-toggle:example.com",
                       "reason": "manual"}],
           "site": "example.com", "on": False})
    g.add("x-toggle-bad-site-int", "site-toggle",
          {"site": 5, "on": True})
    g.add("x-toggle-empty-site", "site-toggle", {"site": "", "on": True})
    g.add("x-toggle-missing-site", "site-toggle", {"on": True})
    g.add("x-toggle-bad-on-string", "site-toggle",
          {"site": "example.com", "on": "true"})
    g.add("x-toggle-missing-on", "site-toggle", {"site": "example.com"})
    g.add("x-toggle-bad-expiry-string", "site-toggle",
          {"site": "example.com", "on": True, "expiry_mono": "700"})
    g.add("x-toggle-bad-expiry-negative", "site-toggle",
          {"site": "example.com", "on": True, "expiry_mono": -2})
    g.add("x-toggle-scopes-malformed", "site-toggle",
          {"scopes": [{"scope_id": "a"}], "site": "example.com",
           "on": True})
    g.add("x-toggle-unknown-arg", "site-toggle",
          {"site": "example.com", "on": True, "bogus": 1})
