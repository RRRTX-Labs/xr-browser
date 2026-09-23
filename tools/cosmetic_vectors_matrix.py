#!/usr/bin/env python3
"""tools/cosmetic_vectors_matrix.py — the T5 scope-key/identity/OOPIF matrix.

Imported by tools/cosmetic_vectors_gen.py (adds the matrix cases to the golden
vector build) and by tools/cosmetic_scope_single_check.py (asserts the four
brief laws over the committed cases). Split into its own module for the
touched-file size law: cosmetic_vectors_gen.py sits six lines under the
380-line ceiling and the matrix is the bulk of T5.

THE LAW BEING PINNED (P12 brief, T5): cosmetic and network consult the SAME
P11 exception scopes object; \"shields down\" flips one bit both read. The
matrix pins the four scope-key/identity/OOPIF properties:

  1. embedder-shields-down must NOT extend to a cross-site frame — the scope
     key is derived from the FRAME's own site, never the embedder's (a
     non-empty embedder_site is REFUSED, so this is structural, not policy);
  2. a frame's exception must NOT reach the embedder — the frame's key is
     frame-scoped; two frames with different frame_site derive different keys
     from identical identity, so one frame's exception data can never key
     another frame's rule set;
  3. same site, different identity => different key-set — hex AND partition
     differ (partition is identity+trust only, so same identity keeps the same
     partition across sites: eviction is per-identity, never per-site);
  4. eviction for one identity never serves another — IdentityPartition()
     hashes (trust, identity), so an eviction dropped for identity A cannot be
     reached from identity B's partition.

Deterministic: no clock, no RNG, no network. Every `expect` is CAPTURED from
cosmetic_host at generation time by the caller's `add()` (which already
refuses to emit a divergent case).
"""
from __future__ import annotations

import json
import typing

IDENTITIES = (
    "anon",
    "alice",
    "bob@example.test",
    "xr:00000000-0000-4000-8000-000000000001",
    "xr:00000000-0000-4000-8000-000000000002",
    "z" * 60,
)
SITES = (
    "ads.example",
    "frame.example",
    "tracker.example",
    "widget.example",
    "a.b.c.example",
    "xn--e1afmkfd.example",
)
TRUSTS = ("anonymous", "authenticated", "enterprise")
NAVS = ("initial", "cross-document", "same-document")


def _tag(x: str) -> str:
    return x.replace(".", "_").replace(":", "-")


def matrix_cases(add, run, frame, host) -> int:
    """Register the T5 matrix cases; returns the number added.

    `add(id_, method, args, flags="")`, `run(cmd, frame, flags=())` and
    `frame(method, args)` are the caller's (cosmetic_vectors_gen) helpers, so
    the module never spawns a host itself except through `run(host, …)`.
    """
    n = 0

    # (1) same site, different identity => different key-set. Two navigation
    # classes per identity so the same-document law is pinned alongside.
    for i, ident in enumerate(IDENTITIES):
        for nav in ("initial", "same-document"):
            add(f"matrix-scope-key-identity-{_tag(ident)}-{nav}", "scope-key",
                {"frame_site": "ads.example", "frame_identity": ident,
                 "trust": "anonymous", "navigation": nav,
                 "url_class": "article"})
            n += 1

    # (2) a frame's exception must not reach the embedder / cross-site frame:
    # same identity, different frame site => different key (hex), same
    # partition (partition is identity+trust, site never reaches it).
    for s in SITES:
        add(f"matrix-scope-key-site-{_tag(s)}-initial", "scope-key",
            {"frame_site": s, "frame_identity": "alice",
             "trust": "anonymous", "navigation": "initial",
             "url_class": "article"})
        add(f"matrix-scope-key-site-{_tag(s)}-cross", "scope-key",
            {"frame_site": s, "frame_identity": "alice",
             "trust": "anonymous", "navigation": "cross-document",
             "url_class": "article"})
        n += 2

    # (3) trust x navigation: the same identity under three trust classes must
    # never collapse — trust changes both hex and partition, so an anonymous
    # rule set can never key an enterprise or authenticated frame.
    for trust in TRUSTS:
        for nav in NAVS:
            add(f"matrix-scope-key-trust-{trust}-{nav}", "scope-key",
                {"frame_site": "ads.example", "frame_identity": "alice",
                 "trust": trust, "navigation": nav, "url_class": "article"})
            n += 1

    # (4) embedder and OOPIF refusal surface: the embedder is never an input.
    for site, embedder in (("ads.example", "top.example"),
                           ("frame.example", "top.example"),
                           ("ads.example", "search.example")):
        add(f"matrix-scope-key-embedder-{_tag(site)}-{_tag(embedder)}",
            "scope-key",
            {"frame_site": site, "frame_identity": "anon",
             "trust": "anonymous", "navigation": "initial",
             "url_class": "article", "embedder_site": embedder})
        n += 1
    # empty embedder is a no-op (the caller that passes "" did not try to key
    # on the embedder) and a non-string embedder is not a refusal — pinned so
    # neither regression can slip through silently.
    add("matrix-scope-key-embedder-empty", "scope-key",
        {"frame_site": "ads.example", "frame_identity": "anon",
         "trust": "anonymous", "navigation": "initial",
         "url_class": "article", "embedder_site": ""})
    n += 1
    add("matrix-scope-key-embedder-nonstring", "scope-key",
        {"frame_site": "ads.example", "frame_identity": "anon",
         "trust": "anonymous", "navigation": "initial",
         "url_class": "article", "embedder_site": 123})
    n += 1

    # (5) blob-check identity/OOPIF half: a blob for one site (or identity)
    # must never apply in another. The caller's run()/frame() build the blobs
    # against the host so the digests are the host's own canonical bytes.
    def blob_of(site: str, identity: str) -> str:
        b = {"blob_id": f"matrix-{_tag(site)}-{identity}",
             "generated_epoch": 1758000000,
             "scope": {"site": site, "identity_class": identity},
             "rules": [{"id": "r1", "selector": "div > .ad",
                        "action": "hide"}]}
        return json.loads(run(host, frame("blob-build", b))[0])["blob"]

    blob_a = blob_of("example.test", "anonymous")
    blob_b = blob_of("example.test", "authenticated")
    blob_c = blob_of("other.test", "anonymous")

    def fs(site: str, identity: str) -> dict:
        return {"site": site, "identity_class": identity}

    _ = [
        add("matrix-blob-a-anon-pass", "blob-check",
            {"blob": blob_a, "frame_scope": fs("example.test", "anonymous")}),
        add("matrix-blob-a-auth-mismatch", "blob-check",
            {"blob": blob_a, "frame_scope": fs("example.test",
                                               "authenticated")}),
        add("matrix-blob-a-enterprise-mismatch", "blob-check",
            {"blob": blob_a, "frame_scope": fs("example.test", "enterprise")}),
        add("matrix-blob-a-cross-site-mismatch", "blob-check",
            {"blob": blob_a, "frame_scope": fs("other.test", "anonymous")}),
        add("matrix-blob-b-auth-pass", "blob-check",
            {"blob": blob_b, "frame_scope": fs("example.test",
                                               "authenticated")}),
        add("matrix-blob-b-anon-mismatch", "blob-check",
            {"blob": blob_b, "frame_scope": fs("example.test", "anonymous")}),
        add("matrix-blob-c-pass", "blob-check",
            {"blob": blob_c, "frame_scope": fs("other.test", "anonymous")}),
        add("matrix-blob-embedder-key-ignored", "blob-check",
            {"blob": blob_a, "frame_scope": {"site": "example.test",
                                             "identity_class": "anonymous",
                                             "embedder_site": "top.example"}}),
        add("matrix-blob-frame-scope-empty", "blob-check",
            {"blob": blob_a, "frame_scope": {}}),
    ]
    n += len(_)

    # (6) shields-down is a SITE-INDEPENDENT decision: the degrade table row
    # is the same regardless of which frame raised it — cross-frame matrix.
    for fl in ("", "--flag xr_shield_cosmetic_v1=on"):
        add(f"matrix-degrade-shields-down-{fl or 'off'}".replace("--flag ", ""),
            "degrade-apply", {"condition": "shields-down"}, fl)
        n += 1

    return n


# --- vocab-allowlist emission (moved here from cosmetic_vectors_gen.py) ----
def emit_allowlist_rows(vec_path) -> None:
    """Print the vocab-allowlist rows for the captured `anonymous` values."""
    import re
    import pathlib
    text = pathlib.Path(vec_path).read_text(encoding="utf-8")
    hits = [i for i, ln in enumerate(text.splitlines(), 1)
            if re.search(r"\banonymous\b", ln, re.IGNORECASE)]
    if not hits:
        return
    just = (
        "identity_class enum value in a captured host output, not rhetoric. "
        "Mirrors IdentityTrustName() in "
        "xr-core/renderer/cosmetic/core/scope_key.cc, whose kAnonymous renders "
        "as exactly this string; the blob's scope must compare equal to the "
        "frame's derived scope key, so the two vocabularies cannot diverge. "
        "The banned sense is a marketing claim ('browse anonymously'); this is "
        "a machine-compared partition label. Row generated by "
        "tools/cosmetic_vectors_gen.py, not hand-maintained."
    )
    print("\n# --- vocab-allowlist rows for the above (replace the existing "
          "cosmetic-v1.json rows) ---")
    for n2 in hits:
        print(f"- path: {vec_path}")
        print(f"  line: {n2}")
        print("  pattern: anonymous")
        print(f"  justification: {json.dumps(just)}")
