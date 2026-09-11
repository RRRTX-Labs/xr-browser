#!/usr/bin/env python3
"""tools/shield_vectors_kit.py — shared fixture builders for the shield
golden-vector generator (P11-T2; the update_vectors_kit.py pattern, split
out for the 400-LOC law). One definition of the test bundle, contexts,
manifest binding and apply states so the generator, the C++ suite
(xr-core/shield/tests) and the parity checker all cite the same fixtures.

Also the home of Gen (the expectation-capture machinery: every vector's
`expect` is the Python reference's real stdout) and the MATCH_URLS
fixture table — moved here by the P11-T2 size-law split (the
update_vectors_kit pattern: kit = fixtures + machinery, families = case
builders, gen = driver).

The manifest sha256 values here are COMPUTED from the bundle under the
frozen list-bundle-manifest-v1 rule (sha256 over the canonical per-list
bytes) — the same single definition both backends implement.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SEP = "\x01"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def list_canonical_bytes(lst: dict) -> str:
    """The bytes a manifest entry's sha256 covers (frozen rule)."""
    rules = []
    for r in lst["rules"]:
        ro = {"action": r["action"], "filter": r["filter"], "id": r["id"],
              "kind": r["kind"]}
        if r.get("resource"):
            ro["resource"] = r["resource"]
        if r.get("domains"):
            ro["domains"] = r["domains"]
        if r.get("exclude_domains"):
            ro["exclude_domains"] = r["exclude_domains"]
        rules.append(ro)
    return canonical({"attribution": lst["attribution"], "name": lst["name"],
                      "rules": rules})


def list_sha(lst: dict) -> str:
    return hashlib.sha256(list_canonical_bytes(lst).encode("utf-8")).hexdigest()


def bundle_digest(bundle: dict) -> str:
    joined = "[" + ",".join(list_canonical_bytes(l) for l in
                            bundle["lists"]) + "]"
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def rule(rid: str, filt: str, action: str = "block",
         kind: str = "network", **kw) -> dict:
    r = {"id": rid, "kind": kind, "filter": filt, "action": action}
    r.update(kw)
    return r


# The vector test bundle: one list exercising every v1 grammar branch
# (domain anchor + separator, allow-exception, redirect, domains option,
# exclude_domains option, wildcard pair, left anchor, right anchor, plain
# literal, cosmetic skip) plus a recorded compiler refusal.
LIST1 = {
    "name": "l1", "attribution": "CC-BY-3.0",
    "rules": [
        rule("r1", "||tracker.example^"),
        rule("r2", "||tracker.example^ok.js", action="allow"),
        rule("r3", "||ads.example/banner", action="redirect",
             kind="redirect", resource="1x1.gif"),
        rule("r4", "||scoped.example^", domains=["site.example"]),
        rule("r5", "||wild.example*/ad_*.js"),
        rule("r6", "|https://anchor.example/x"),
        rule("r7", "||exact.example/e|"),
        rule("r8", "plain-literal.js", exclude_domains=["safe.example"]),
        rule("r9", "cosmetic.example", kind="cosmetic"),
        rule("r10", "||bare.example|"),
        rule("r11", "||sep.example^a^b"),
    ],
}

BUNDLE = {"schema": "xr-list-bundle", "schema_version": 1,
          "name": "xr-default", "bundle_version": 3, "lists": [LIST1],
          "refusals": [{"directive": "##.ad",
                        "reason": "unsupported-directive:cosmetic-hash",
                        "count": 2}]}

GOOD_MANIFEST = {"schema_version": 1, "bundle_id": "xr-default-2026-09",
                 "created_epoch": 1780000000,
                 "lists": [{"name": LIST1["name"],
                            "sha256": list_sha(LIST1),
                            "rules": len(LIST1["rules"])}],
                 "key_pin": "ed25519:test"}


def ctx(url: str, domain: str, identity: str = "xr:a",
        request_class: str = "kSubresource", **kw) -> dict:
    c = {"identity": {"value": identity},
         "origin": {"scheme": "https", "registrable_domain": domain},
         "url": url, "request_class": request_class}
    c.update(kw)
    return c


CTX = ctx("https://tracker.example/a.js", "tracker.example",
          request_class="kScript")

SAMPLE_EVENT = {"ts_millis": 1000, "identity": {"value": "xr:a"}, "tab_id": 7,
                "origin": {"scheme": "https",
                           "registrable_domain": "tracker.example"},
                "target": "https://tracker.example/a.js",
                "rule": "||tracker.example^", "list_provenance": "l1",
                "action": "kBlocked", "request_class": "kScript"}

STATE_EMPTY = {"active": {"present": False}, "lkg": {"present": False},
               "pins": [], "last_apply_mono": -1}


def slot(bundle_id: str, version: int, digest: str | None = None) -> dict:
    return {"present": True, "bundle_id": bundle_id, "version": version,
            "digest": digest if digest is not None else bundle_digest(BUNDLE)}


def state_v3() -> dict:
    """The state after activating BUNDLE (v3) at mono 100."""
    return {"active": slot("xr-default", 3), "lkg": {"present": False},
            "pins": [slot("xr-default", 3)], "last_apply_mono": 100}


class Gen:
    def __init__(self, fake: Path) -> None:
        self.fake = fake
        self.cases: list[dict] = []

    def add(self, cid: str, method: str, args: dict,
            flags: list[str] | None = None, raw: str | None = None) -> None:
        frame = raw if raw is not None else \
            canonical({"method": method, "args": args})
        r = subprocess.run([sys.executable, str(self.fake), *(flags or [])],
                           input=frame, capture_output=True, text=True,
                           timeout=60)
        out = r.stdout.strip("\n")
        if not out:
            raise SystemExit(f"vector {cid}: no stdout (rc={r.returncode}) — "
                             "usage-exit cases do not belong in the vectors")
        expect = json.loads(out)
        case: dict = {"expect": expect, "id": cid}
        if raw is not None:
            case["raw"] = raw  # protocol-level frame, replayed verbatim
        else:
            case["args"] = args
            case["method"] = method
        if flags:
            case["flags"] = " ".join(flags)
        # exit code: derived by the replay rules unless it deviates
        derived = 0
        if isinstance(expect, dict) and "error" in expect and "ok" not in expect:
            derived = 1 if expect["error"] in ("kMalformedInput",
                                               "kUnknownMethod") else 0
        if r.returncode != derived:
            case["exit"] = r.returncode
        self.cases.append(case)


MATCH_URLS = [
    ("m-block-basic", "https://tracker.example/a.js", "tracker.example"),
    ("m-block-subdomain", "https://sub.tracker.example/a", "tracker.example"),
    ("m-block-query-strip", "https://tracker.example/a.js?uid=SECRET#f",
     "tracker.example"),
    ("m-block-port-strip", "https://tracker.example:8443/a.js",
     "tracker.example"),
    ("m-block-bare-host", "https://tracker.example", "tracker.example"),
    ("m-not-suffix-boundary", "https://tracker.example.com/a",
     "tracker.example.com"),
    ("m-not-prefix-host", "https://nottracker.example/a",
     "nottracker.example"),
    ("m-allow-overrides-block", "https://tracker.example/ok.js",
     "tracker.example"),
    ("m-allow-case-path", "https://tracker.example/OK.js", "tracker.example"),
    ("m-redirect-hit", "https://ads.example/banner", "ads.example"),
    ("m-redirect-path-suffix", "https://ads.example/banner/x", "ads.example"),
    ("m-anchor-host-not-substring", "https://x.com/ads.example/banner",
     "x.com"),
    ("m-domains-option-in", "https://scoped.example/x", "site.example"),
    ("m-domains-option-out", "https://scoped.example/x", "other.example"),
    ("m-exclude-domains-in", "https://safe.example/plain-literal.js",
     "safe.example"),
    ("m-exclude-domains-out", "https://any.example/plain-literal.js",
     "any.example"),
    ("m-wildcard-pair-hit", "https://wild.example/deep/ad_min.js",
     "wild.example"),
    ("m-wildcard-pair-miss", "https://wild.example/ad_min.css",
     "wild.example"),
    ("m-wildcard-host-miss", "https://other.example/deep/ad_min.js",
     "other.example"),
    ("m-left-anchor-hit", "https://anchor.example/x", "anchor.example"),
    ("m-left-anchor-scheme-miss", "http://anchor.example/x",
     "anchor.example"),
    ("m-left-anchor-prefix-miss", "https://anchor.example/xy",
     "anchor.example"),
    ("m-right-anchor-hit", "https://exact.example/e", "exact.example"),
    ("m-right-anchor-miss", "https://exact.example/e/more", "exact.example"),
    ("m-right-anchor-port", "https://exact.example:8443/e", "exact.example"),
    ("m-bare-domain-hit", "https://bare.example", "bare.example"),
    ("m-bare-domain-root-slash", "https://bare.example/", "bare.example"),
    ("m-bare-domain-miss", "https://bare.example/x", "bare.example"),
    ("m-separator-class-hit", "https://sep.example/a/b", "sep.example"),
    ("m-separator-class-miss", "https://sep.example/ab", "sep.example"),
    ("m-plain-literal-substring", "https://any.example/js/plain-literal.js",
     "any.example"),
    ("m-cosmetic-never-network", "https://cosmetic.example/",
     "cosmetic.example"),
    ("m-no-match-clean", "https://clean.example/", "clean.example"),
    ("m-first-party-field", "https://tracker.example/a.js",
     "tracker.example"),
    ("m-navigation-class", "https://tracker.example/a.js",
     "tracker.example"),
]
