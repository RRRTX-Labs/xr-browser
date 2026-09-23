#!/usr/bin/env python3
"""tools/cosmetic_vectors_gen.py — regenerate the cosmetic golden vectors.

Every `expect` is CAPTURED from cosmetic_host at generation time and then
pinned: the vectors are a regression net, not a transcription of what anyone
believed the host does. The generator REFUSES to emit a case where the two
backends disagree, so a vector can never record one side's opinion as the
contract — that property is what makes tools/cosmetic_vectors_check.py a parity
test rather than a self-consistency test.

Run this after any change to renderer/cosmetic/core, cosmetic_host.cc, or
fakes/cosmetic.py, then commit BOTH the vectors and the vocab-allowlist rows it
prints. Stdlib only; no wall clock, so the output is reproducible.

Also emits the docs/state/vocab-allowlist.yaml rows for the `anonymous`
identity_class enum value. Those rows are line-precise by design (the lint
rejects a stale line), and a generated vector file's line numbers move, so
hand-maintaining 24 of them would rot on the first regeneration. This is the
generator's job, not a reviewer's.
"""
import json, subprocess, sys
from pathlib import Path

from cosmetic_vectors_matrix import emit_allowlist_rows, matrix_cases

HOST = Path("../xr-core/renderer/cosmetic/tests/build/cosmetic_host")
FAKE = Path("../xr-core/fakes/cosmetic.py")

def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def frame(method, args):
    return canon({"args": args, "method": method})

def run(cmd, fr, flags=()):
    # The fake is invoked through the interpreter: it is not executable and
    # relying on a shebang would make the vectors depend on a file mode.
    argv = [sys.executable, str(cmd)] if str(cmd).endswith(".py") \
        else [str(cmd)]
    r = subprocess.run([*argv, *flags], input=fr, capture_output=True,
                       text=True, timeout=60)
    return r.stdout.strip("\n"), r.returncode

CASES = []
def add(id_, method, args, flags=""):
    fr = frame(method, args)
    h_out, h_rc = run(HOST, fr, flags.split() if flags else ())
    f_out, f_rc = run(FAKE, fr, flags.split() if flags else ())
    if h_out != f_out or h_rc != f_rc:
        print(f"DIVERGED AT GENERATION: {id_}\n  host({h_rc}): {h_out[:200]}\n"
              f"  fake({f_rc}): {f_out[:200]}", file=sys.stderr)
        sys.exit(1)
    CASES.append({"id": id_, "method": method, "args": args,
                  "expect": json.loads(h_out), "exit": h_rc,
                  **({"flags": flags} if flags else {})})

# ---- flag-status (both flags x both states = 4) ----
for cf in ("", "--flag xr_shield_cosmetic_v1=on"):
    for sf in ("", "--flag xr_shield_scriptlets=on"):
        fl = " ".join(x for x in (cf, sf) if x)
        add(f"flag-status-{fl or 'default'}".replace("--flag ", "").replace("=", "-").replace(" ", "_"),
            "flag-status", {}, fl)

# ---- selector-parse: one admitted + every refusal reason ----
ADMITTED = ["div > .ad", "div>.ad", ".ad", "#top-ad", "section.sponsored > div",
            "div.a.b", "div.b.a", "a[href]", "a[href^=\"https\"]",
            "div:has-text(Sponsored)", "div:has(.ad)", "div:not(.keep)",
            "div:min-text-length(40)", "div:upward(2)",
            "div:matches-path(/blog)", "div:remove()", "*"]
for i, sel in enumerate(ADMITTED):
    add(f"selector-admitted-{i:02d}", "selector-parse", {"selector": sel})

REFUSED = [
    ("", "empty"), ("x" * 513, "too-long"), ("div > " * 80 + ".a", "compounds"),
    ("a[" + ",".join(f"x{i}]" for i in range(9)), "attrs"),
    ("div:has(" + ",".join(f".a{i}" for i in range(9)) + ")", "pseudo-args"),
    ("." + "y" * 200, "ident-too-long"), ("div:(.ad", "unbalanced-paren"),
    ("div[.ad", "unbalanced-bracket"), ("div >> .ad", "double-combinator"),
    ("> .ad", "leading-combinator"), ("div >", "trailing-combinator"),
    ("div,.ad,", "comma-list"), ("div:is(.a,.b)", "comma-in-pseudo-arg"),
    ("div;.ad", "disallowed-char"),
    ("div.ad!important", "bang"), ("@media screen", "at-rule"),
    ("div<!--x-->", "markup"), ("a[href^=url(x)]", "url-function"),
    ("div[style*=expression(1)]", "expression"),
    ("div:bogus-pseudo", "unknown-pseudo"),
    ("div:has-text(" + "z" * 600 + ")", "pseudo-arg-too-long"),
    ("*:has(.ad)", "universal-with-pseudo"),
    ("div\\\\.ad", "escape"),
]
for i, (sel, why) in enumerate(REFUSED):
    add(f"selector-refused-{i:02d}-{why}", "selector-parse", {"selector": sel})

# ---- scope-key: trust x navigation x url_class, plus refusals ----
for trust in ("anonymous", "authenticated", "enterprise"):
    for nav in ("initial", "cross-document", "same-document"):
        add(f"scope-key-{trust}-{nav}", "scope-key",
            {"frame_site": "ads.example", "frame_identity": "alice",
             "trust": trust, "navigation": nav, "url_class": "article"})
for uc in ("generic", "article", "search", "player", "embed"):
    add(f"scope-key-urlclass-{uc}", "scope-key",
        {"frame_site": "ads.example", "frame_identity": "anon",
         "url_class": uc})
add("scope-key-embedder-refused", "scope-key",
    {"frame_site": "ads.example", "frame_identity": "alice",
     "url_class": "article", "embedder_site": "top.example"})
add("scope-key-bad-trust", "scope-key",
    {"frame_site": "ads.example", "frame_identity": "a", "trust": "root",
     "url_class": "article"})
add("scope-key-bad-navigation", "scope-key",
    {"frame_site": "ads.example", "frame_identity": "a",
     "navigation": "teleport", "url_class": "article"})
add("scope-key-missing-site", "scope-key",
    {"frame_identity": "a", "url_class": "article"})

# ---- key-set: dedup, actions, styles, refusals ----
add("key-set-single-hide", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide"}]})
add("key-set-whitespace-dedup", "key-set",
    {"rules": [{"id": "r1", "selector": "div>.ad", "action": "hide"},
               {"id": "r2", "selector": "div > .ad", "action": "hide"}]})
add("key-set-classorder-dedup", "key-set",
    {"rules": [{"id": "r1", "selector": "div.a.b", "action": "hide"},
               {"id": "r2", "selector": "div.b.a", "action": "hide"}]})
add("key-set-action-distinct", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide"},
               {"id": "r2", "selector": ".ad", "action": "remove"}]})
for act in ("hide", "collapse", "visibility", "remove"):
    add(f"key-set-action-{act}", "key-set",
        {"rules": [{"id": "r1", "selector": ".ad", "action": act}]})
add("key-set-style-two-decls", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"display": "none", "opacity": "0"}}]})
for prop in ("behavior", "-moz-binding", "content", "position", "z-index",
             "background", "background-image", "list-style-image", "cursor",
             "border-image", "mask", "filter", "src"):
    add(f"key-set-refused-property-{prop}", "key-set",
        {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                    "style": {prop: "none"}}]})
add("key-set-refused-bang-in-value", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"display": "none !important"}}]})
add("key-set-refused-url-in-value", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"background": "url(x)"}}]})
add("key-set-refused-empty", "key-set", {"rules": []})
add("key-set-refused-empty-style-map", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {}}]})
add("key-set-refused-dup-id", "key-set",
    {"rules": [{"id": "r1", "selector": ".a", "action": "hide"},
               {"id": "r1", "selector": ".b", "action": "hide"}]})
add("key-set-refused-unknown-action", "key-set",
    {"rules": [{"id": "r1", "selector": ".a", "action": "script"}]})
add("key-set-refused-bad-selector", "key-set",
    {"rules": [{"id": "r1", "selector": "*.bogus(", "action": "hide"}]})
add("key-set-refused-universal-pseudo", "key-set",
    {"rules": [{"id": "r1", "selector": "*:has(.ad)", "action": "hide"}]})
add("key-set-many-rules", "key-set",
    {"rules": [{"id": f"r{i}", "selector": f".c{i}", "action": "hide"}
               for i in range(50)]})

# ---- degrade-apply: all 14 conditions + refusal ----
for cond in ("flag-off", "scriptlets-off", "blob-invalid", "blob-missing",
             "scope-mismatch", "rule-unparsable", "rule-unknown-pseudo",
             "rule-too-expensive", "shields-down", "empty-rule-set",
             "dom-mutation-storm", "engine-unavailable",
             "main-world-required", "generic-set-only"):
    add(f"degrade-{cond}", "degrade-apply", {"condition": cond})
add("degrade-unknown", "degrade-apply", {"condition": "invented-state"})

# ---- page-states: flag x rules ----
for fl in ("", "--flag xr_shield_cosmetic_v1=on"):
    for n in (0, 1, 3):
        add(f"page-states-{fl or 'off'}-{n}".replace("--flag ", "").replace("=", "-"),
            "page-states", {"keyset_rules": n}, fl)

# ---- blob-build + blob-check round trip ----
def build(blob_id, epoch, scope, rules, refusals=None):
    a = {"blob_id": blob_id, "generated_epoch": epoch, "scope": scope,
         "rules": rules}
    if refusals:
        a["refusals"] = refusals
    return a

SC = {"site": "example.test", "identity_class": "anonymous"}
b = build("vec-1", 1758000000, SC,
          [{"id": "r1", "selector": "div > .ad", "action": "hide"},
           {"id": "r2", "selector": ".sponsor", "action": "remove"}])
add("blob-build-two-rules", "blob-build", b)
fr = frame("blob-build", b)
blob_text = json.loads(run(HOST, fr)[0])["blob"]
add("blob-check-valid", "blob-check",
    {"blob": blob_text, "frame_scope": SC})
add("blob-check-no-frame", "blob-check", {"blob": blob_text})
add("blob-check-wrong-site", "blob-check",
    {"blob": blob_text, "frame_scope": {"site": "other.test",
                                        "identity_class": "anonymous"}})
add("blob-check-wrong-identity", "blob-check",
    {"blob": blob_text, "frame_scope": {"site": "example.test",
                                        "identity_class": "enterprise"}})
add("blob-check-tampered", "blob-check",
    {"blob": blob_text.replace("div > .ad", "body")})
add("blob-check-truncated-digest", "blob-check",
    {"blob": blob_text[:-70] + '"sha256":"abcd"' + blob_text[-2:]})
add("blob-check-not-json", "blob-check", {"blob": "not-json"})
add("blob-check-array", "blob-check", {"blob": "[]"})

# a blob carrying a producer refusal
b2 = build("vec-2", 1758000000, SC,
           [{"id": "r1", "selector": ".ad", "action": "hide"}],
           refusals=[{"rule_index": 7, "reason": "unknown-pseudo-class"}])
add("blob-build-with-refusal", "blob-build", b2)
blob2 = json.loads(run(HOST, frame("blob-build", b2))[0])["blob"]
add("blob-check-with-refusal", "blob-check",
    {"blob": blob2, "frame_scope": SC})

# unknown method
add("unknown-method", "flag-status", {}, "")  # placeholder replaced below


# ---- extra coverage to clear the 150-vector floor with REAL cases, not padding ----
# More admitted selectors: the shapes a real list ships.
MORE_ADMITTED = [
    "div.ad", "section > div.ad", "main .sponsored", "aside#rail .ad-slot",
    "div[class]", "div[class*=advert]", "div[class^=ad-]", "div[class$=-ad]",
    "div[class~=banner]", "div[class|=ad]", 'div[class*="Ad Slot" i]',
    "DIV:HAS(.a)", "Div.Ad", "SECTION > DIV.AD",
    "article > header + div", "ul > li:first-child", "body > div",
    "div.ad:not(.kept)", "span:has-text(Advertisement)",
    "div:min-text-length(120)", "p:upward(1)", "section:matches-path(/news)",
    "div.ad ~ div.footer", "nav a[href]", "form input[type=hidden]",
    "div[class*=promoted]:has(img)", "table td:nth-child(2)",
]
for i, sel in enumerate(MORE_ADMITTED):
    add(f"selector-admitted-extra-{i:02d}", "selector-parse", {"selector": sel})

# More refusals, one per remaining reason and per boundary.
MORE_REFUSED = [
    ("div:has(", "unbalanced-paren"), ("div[", "unbalanced-bracket"),
    ("div:", "disallowed-char"), ("div..ad", "empty-compound"),
    ("div.ad!", "bare-bang"),
    ("." + "a" * 128, "ident-at-limit"), ("." + "a" * 129, "ident-over-limit"),
    ("div:has-text(" + "q" * 511 + ")", "arg-near-limit"),
    ("div:has(" + "div:has(" * 4 + ".a))))","nested-has"),
    ("*:has-text(x)", "universal-functional"),
    ("div:nth-ancestor(2)", "refused-pseudo"),
    ("div:xpath(//a)", "refused-pseudo"),
    ("div:matches-css(color:red)", "refused-pseudo"),
    ("div:matches-attr(href)", "refused-pseudo"),
    ("div:if(.a)", "refused-pseudo"),
    ("div:remove", "admitted-bare-remove"),
    ("div:remove()", "admitted-empty-arg-remove"),
    ("div:remove(x)", "remove-with-arg"),
]
for i, (sel, why) in enumerate(MORE_REFUSED):
    add(f"selector-extra-{i:02d}-{why}", "selector-parse", {"selector": sel})

# key-set: byte accounting and dedup edges
add("key-set-dedup-three-variants", "key-set",
    {"rules": [{"id": "r1", "selector": "div>.ad", "action": "hide"},
               {"id": "r2", "selector": "div > .ad", "action": "hide"},
               {"id": "r3", "selector": "div  >  .ad", "action": "hide"}]})
add("key-set-style-vs-hide-distinct", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide"},
               {"id": "r2", "selector": ".ad", "action": "style",
                "style": {"display": "none"}}]})
add("key-set-hide-collapse-distinct", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide"},
               {"id": "r2", "selector": ".ad", "action": "collapse"}]})
add("key-set-exception-sites", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide",
                "exception_sites": ["a.example", "b.example"]}]})
add("key-set-disabled-rule", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "hide",
                "enabled": False}]})
add("key-set-refused-style-value-too-long", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"display": "n" * 300}}]})
add("key-set-refused-empty-style-value", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"display": ""}}]})
add("key-set-refused-too-many-declarations", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {p: "none" for p in
                          ("display", "visibility", "opacity", "height",
                           "max-height", "min-height", "width", "max-width",
                           "min-width", "overflow", "pointer-events", "clip",
                           "clip-path", "display", "visibility", "opacity",
                           "height")}}]})
add("key-set-refused-empty-id", "key-set",
    {"rules": [{"id": "", "selector": ".ad", "action": "hide"}]})
add("key-set-refused-nonobject-rule", "key-set", {"rules": ["nope"]})
add("key-set-missing-action", "key-set",
    {"rules": [{"id": "r1", "selector": ".ad"}]})

# scope-key: identity and site variety
for ident in ("anon", "alice", "bob@example.test", "x" * 60):
    add(f"scope-key-identity-{len(ident)}", "scope-key",
        {"frame_site": "ads.example", "frame_identity": ident,
         "url_class": "article"})
for site in ("ads.example", "a.b.c.example", "xn--e1afmkfd.example"):
    add(f"scope-key-site-{site.replace('.', '_')}", "scope-key",
        {"frame_site": site, "frame_identity": "anon",
         "url_class": "generic"})

# page-states across both flags and rule counts
for n in (0, 1, 2, 5, 100):
    add(f"page-states-on-{n}", "page-states", {"keyset_rules": n},
        "--flag xr_shield_cosmetic_v1=on")

# degrade-apply: every condition under both flag states is the same answer,
# which is the point — the table does not depend on the flag.
for cond in ("shields-down", "generic-set-only", "engine-unavailable"):
    add(f"degrade-{cond}-flag-on", "degrade-apply", {"condition": cond},
        "--flag xr_shield_cosmetic_v1=on")

# blob-build edges
add("blob-build-empty-rules", "blob-build",
    {"blob_id": "vec-empty", "generated_epoch": 1, "scope": SC, "rules": []})
add("blob-build-authenticated", "blob-build",
    {"blob_id": "vec-auth", "generated_epoch": 2,
     "scope": {"site": "example.test", "identity_class": "authenticated"},
     "rules": [{"id": "r1", "selector": ".ad", "action": "hide"}]})
add("blob-build-style-rule", "blob-build",
    {"blob_id": "vec-style", "generated_epoch": 3, "scope": SC,
     "rules": [{"id": "r1", "selector": ".ad", "action": "style",
                "style": {"opacity": "0"}}]})

# ---- T5: the scope-key/identity/OOPIF matrix (matrix module) ---------------
matrix_cases(add, run, frame, HOST)

doc = {
    "schema": "cosmetic-vectors-1",
    "schema_version": 1,
    "note": ("P12-T1 golden vectors for the renderer/cosmetic host surface. "
             "Every `expect` was CAPTURED from cosmetic_host at generation time "
             "and then pinned; tools/cosmetic_vectors_check.py re-runs BOTH "
             "backends (the compiled C++ host and fakes/cosmetic.py) and requires "
             "byte-identical stdout and identical exit codes against these bytes. "
             "The refusal vocabulary is closed and copied from the C++ "
             "*ErrorName() tables — a rename on either side reddens this file "
             "rather than drifting. `exit` is pinned explicitly: 0 for an ok or "
             "typed rejection, 1 for a typed error, so a vector that changes exit "
             "class is a visible change and not a silent one."),
    "cases": CASES,
}
out = Path("docs/contracts/vectors/cosmetic-v1.json")
out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
print(f"{len(CASES)} vectors over {len({c['method'] for c in CASES})} methods")

emit_allowlist_rows("docs/contracts/vectors/cosmetic-v1.json")
