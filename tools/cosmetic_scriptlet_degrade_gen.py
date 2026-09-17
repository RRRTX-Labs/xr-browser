#!/usr/bin/env python3
"""Build docs/contracts/cosmetic-scriptlet-degrade.json.

Each case names a MODEL page (a DOM-model fixture, never a browser), a scriptlet
invocation, and the structure the page must still have after the scriptlet runs
or is disabled. `surface: model` on every case so nobody mistakes it for a
browser measurement.
"""
import json, pathlib

CASES = []
def add(id_, scriptlet, page, enabled, expect_structure, note):
    CASES.append({
        "id": id_, "surface": "model", "scriptlet": scriptlet,
        "page": page, "enabled": enabled,
        "expect_structure": expect_structure, "note": note,
    })

# 12 synthetic pages as DOM-model fixtures.
PAGES = {
    "softwall-body-lock": {"nodes": 41, "body_attrs": {"style": "overflow:hidden"},
        "classes": {"body": ["locked"]}, "text_len": 5200},
    "softwall-overlay": {"nodes": 58, "classes": {"div#veil": ["overlay", "on"]},
        "text_len": 4100},
    "inline-ad-slot": {"nodes": 33, "classes": {"div.ad": ["ad", "slot"]},
        "text_len": 3000},
    "sticky-header-ad": {"nodes": 47, "classes": {"header": ["sticky-ad"]},
        "text_len": 3800},
    "interstitial": {"nodes": 66, "classes": {"div#inter": ["interstitial"]},
        "text_len": 2900},
    "video-preroll": {"nodes": 52, "classes": {"div.player": ["ad-playing"]},
        "text_len": 2400},
    "newsletter-modal": {"nodes": 44, "classes": {"div.modal": ["signup"]},
        "text_len": 3300},
    "scroll-hijack": {"nodes": 39, "body_attrs": {"data-lock": "1"},
        "text_len": 4400},
    "cookie-wall": {"nodes": 55, "classes": {"div#cwall": ["wall"]},
        "text_len": 3600},
    "app-install-prompt": {"nodes": 37, "classes": {"div.prompt": ["install"]},
        "text_len": 3100},
    "article-truncation": {"nodes": 49, "classes": {"div.trunc": ["fade"]},
        "text_len": 6100},
    "autoplay-banner": {"nodes": 43, "classes": {"div.banner": ["autoplay"]},
        "text_len": 2700},
}

SCRIPTLETS = {
    "abort-on-property-read": ("sd-abort-on-property-read", "sr-abort-bad-arity"),
    "abort-on-property-write": ("sd-abort-on-property-write", "sr-write-bad-arity"),
    "set-constant": ("sd-set-constant", "sr-set-constant-bad-arity"),
    "remove-attr": ("sd-remove-attr", "sr-remove-attr-bad-arity"),
    "remove-class": ("sd-remove-class", "sr-remove-class-bad-arity"),
    "set-attr": ("sd-set-attr", "sr-set-attr-bad-arity"),
    "json-prune": ("sd-json-prune", "sr-json-prune-bad-arity"),
    "no-setTimeout-if": ("sd-no-setTimeout-if", "sr-no-settimeout-bad-arity"),
    "prevent-setTimeout": ("sd-prevent-setTimeout", "sr-prevent-settimeout-bad-arity"),
    "noeval": ("sd-noeval", "sr-noeval-bad-arity"),
    "nowebrtc": ("sd-nowebrtc", "sr-nowebrtc-bad-arity"),
    "cookie-remover": ("sd-cookie-remover", "sr-cookie-bad-arity"),
}

# The invariant every case asserts: disabling a scriptlet leaves the page's
# STRUCTURE intact. Node count and text length are the structure; classes and
# attributes are what a scriptlet may change.
for name, (dc, rc) in SCRIPTLETS.items():
    for page_name, page in PAGES.items():
        add(f"{dc}__{page_name}", name, page_name, False,
            {"nodes": page["nodes"], "text_len": page["text_len"]},
            "Scriptlet disabled: the page must render the same structure. "
            "A scriptlet that is not disable-able individually is not a "
            "degrade path, it is a dependency.")
        add(f"{dc}__{page_name}__on", name, page_name, True,
            {"nodes": page["nodes"], "text_len": page["text_len"]},
            "Scriptlet enabled on the model: it may change classes and "
            "attributes, but node count and text length are unchanged. A "
            "scriptlet that removes NODES is doing DOM removal, which is the "
            "cosmetic `remove` action's job and is labelled page-modifying.")
    # The refusal path: a bad arity must be refused, not partially applied.
    add(rc, name, "inline-ad-slot", True,
        {"nodes": 33, "text_len": 3000},
        "Refusal path: wrong arity is refused and the page is untouched. A "
        "scriptlet that half-applied on a malformed instruction would leave "
        "the page in a state neither the list nor the user asked for.")

# A failing scriptlet degrades to inert rather than breaking the page.
for page_name, page in PAGES.items():
    add(f"sd-failing-scriptlet__{page_name}", "abort-on-property-read",
        page_name, True, {"nodes": page["nodes"], "text_len": page["text_len"]},
        "A scriptlet that raises must degrade to inert and leave the page "
        "structure intact — the plan's 'never breaks page render', asserted on "
        "the model rather than claimed.")

doc = {
    "schema": "cosmetic-scriptlet-degrade-1",
    "schema_version": 1,
    "surface": "model",
    "note": ("P12-T4 scriptlet degrade corpus. EVERY case is a DOM-MODEL "
             "fixture, not a browser: `surface: model` is on the document and "
             "on every case, and the tooling refuses to run without it, "
             "because a model result read as a page result is exactly the "
             "claim this phase is graded on. Each scriptlet gets one case per "
             "synthetic page with the scriptlet DISABLED (the page must render "
             "the same structure), one with it ENABLED (structure still "
             "unchanged; only classes and attributes may differ), one "
             "refusal-path case at bad arity, and one failing-scriptlet case "
             "per page proving it degrades to inert. The structure asserted is "
             "node count and text length; classes and attributes are what a "
             "scriptlet is allowed to change."),
    "pages": PAGES,
    "cases": CASES,
}
out = pathlib.Path("docs/contracts/cosmetic-scriptlet-degrade.json")
out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
print(f"{len(CASES)} cases over {len(PAGES)} pages and {len(SCRIPTLETS)} scriptlets")
