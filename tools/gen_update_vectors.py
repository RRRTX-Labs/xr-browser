#!/usr/bin/env python3
"""tools/gen_update_vectors.py — generate the update golden vectors
(P10-T1): >=60 typed cases across every verify axis + epoch-apply/cohort/
backoff/about-state, deterministic, --check regenerates byte-identical.
Fixture builders live in tools/update_vectors_kit.py (the stub-signature
law's single definition)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

OUT = "docs/contracts/vectors/update-v1.json"

BASE_RESPONSE = {
    "app": [{"appid": "labs.rrrtx.xr", "status": "ok", "updatecheck": {
        "manifest": {"packages": {"package": [{
            "fp": "1.abc", "hash_sha256": "aa" * 32,
            "name": "xr-1.2.0.0.crx", "size": 1024}]},
            "run": "", "version": "1.2.0.0"},
        "status": "ok",
        "urls": {"url": [{"codebase": "https://updates.example/xr/"}]}}}],
    "daystart": {"elapsed_days": 7000},
    "protocol": "3.1",
    "server": "pub",
}

HASH64 = "aa" * 32

def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)

def verify_args(env_str, current="1.0.0.0", channel="dev", epoch=None,
                seen=None, transport=None):
    a = {"channel": channel, "current_version": current, "envelope": env_str,
         "epoch": epoch if epoch is not None else EPOCH, "keys": KEYS}
    if seen:
        a["seen"] = seen
    if transport is not None:
        a["transport"] = transport
    return a

def deepset(obj, path, value):
    """Set obj at dotted path (creating dicts); for list indices use int."""
    if not path:
        return value
    head, rest = path[0], path[1:]
    if isinstance(head, int):
        obj = list(obj)
        obj[head] = deepset(obj[head], rest, value)
        return obj
    obj = dict(obj)
    obj[head] = deepset(obj.get(head), rest, value) if rest else value
    return obj

def delpath(obj, path):
    if not path:
        return None
    if len(path) == 1:
        obj = dict(obj) if isinstance(obj, dict) else list(obj)
        del obj[path[0]]
        return obj
    head, rest = path[0], path[1:]
    obj = dict(obj) if isinstance(obj, dict) else list(obj)
    obj[head] = delpath(obj[head], rest)
    return obj

from update_vectors_kit import (KEY_MATERIAL, EPOCH, KEYS,  # kit (split, LOC law)
                                envelope, stub_sig)
def main() -> int:
    ap = argparse.ArgumentParser(prog="gen-update-vectors")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo)
    cases: list[dict] = []

    def add(cid, method, args_v, expect):
        cases.append({"args": args_v, "expect": expect, "id": cid,
                      "method": method})

    good = envelope(BASE_RESPONSE)

    def V(cid, env_str, expect_reason, current="1.0.0.0", channel="dev",
          epoch=None, seen=None, transport=None, verdict=None):
        v = "accept" if expect_reason == "ok" else (verdict or "deny")
        manual = (epoch or {}).get("manual_path", False) \
            if expect_reason == "epoch-revoked" else False
        add(cid, "verify",
            verify_args(env_str, current, channel, epoch, seen, transport),
            {"manual_path": manual, "reason": expect_reason, "verdict": v})

    # ---- accept paths (4) ----
    V("verify-accept-newer", good, "ok")
    V("verify-accept-newer-major", envelope(deepset(BASE_RESPONSE,
      ["app", 0, "updatecheck", "manifest", "version"], "2.0.0.0")), "ok")
    V("verify-accept-zero-current",
      envelope(deepset(BASE_RESPONSE, ["app", 0, "updatecheck", "manifest",
                                       "version"], "0.0.0.1")),
      "ok", current="0.0.0.0")
    V("verify-accept-every-word-server-field",
      envelope(deepset(BASE_RESPONSE, ["server"], "mirror.example")), "ok")

    # ---- TLS independence (3): the transport echo is accepted and ignored —
    # identical envelopes, contradictory transports, identical verdicts.
    V("verify-tls-good-good", good, "ok", transport={"tls": True,
                                                     "peer": "pin-ok"})
    V("verify-tls-bad-good", good, "ok", transport={"tls": False,
                                                    "peer": "pin-ok"})
    V("verify-tls-good-badsig",
      envelope(BASE_RESPONSE, sig_value="sig:" + "0" * 16), "signature-invalid",
      transport={"tls": True, "peer": "pin-ok"})

    # ---- unknown-field denials at every level (11) ----
    for cid, path, val in [
        ("verify-unknown-envelope-level", ["xrsig"], "z"),
        ("verify-unknown-response-level", ["response", "extra"], 1),
        ("verify-unknown-app-level", ["response", "app", 0, "tag"], "x"),
        ("verify-unknown-updatecheck-level",
         ["response", "app", 0, "updatecheck", "ttl"], 5),
        ("verify-unknown-manifest-level",
         ["response", "app", 0, "updatecheck", "manifest", "restrict"], "x"),
        ("verify-unknown-packages-level",
         ["response", "app", 0, "updatecheck", "manifest", "packages",
          "hash"], "x"),
        ("verify-unknown-package-level",
         ["response", "app", 0, "updatecheck", "manifest", "packages",
          "package", 0, "sha1"], "x"),
        ("verify-unknown-urls-level",
         ["response", "app", 0, "updatecheck", "urls", "region"], "us"),
        ("verify-unknown-url-level",
         ["response", "app", 0, "updatecheck", "urls", "url", 0, "scheme"],
         "https"),
        ("verify-unknown-epoch-level", ["epoch", "note"], "x"),
        ("verify-unknown-signature-level", ["signature", "cert"], "x"),
    ]:
        # unknown-field is caught before any signature/epoch logic
        envs = canonical(delpath({"response": None}, []))  # placeholder no-op
        doc = json.loads(envelope(BASE_RESPONSE))
        doc = deepset(doc, path, val)
        V(cid, canonical(doc), "unknown-field")

    # ---- protocol / shape (6) ----
    V("verify-wrong-protocol",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "protocol"], "3.0")), "wrong-protocol")
    V("verify-malformed-json", "{not json", "malformed-manifest")
    V("verify-empty-doc", "{}", "malformed-manifest")
    V("verify-two-apps",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)), ["response", "app"],
                        json.loads(envelope(BASE_RESPONSE))["response"]["app"] * 2)),
      "malformed-manifest")
    V("verify-missing-appid",
      canonical(delpath(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "appid"])), "malformed-manifest")
    V("verify-bad-signature-alg",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["signature", "alg"], "ed25519-detached")),
      "malformed-manifest")

    # ---- oversize (1) + prefix (1) ----
    V("verify-oversize", "x" * (65 * 1024), "oversize")
    V("verify-safe-prefix-accepted", ")]}'\n" + good, "ok")

    # ---- app / offer (3) ----
    V("verify-unknown-appid",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "appid"], "com.other.browser")),
      "unknown-appid")
    V("verify-noupdate",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "updatecheck", "status"],
                        "noupdate")), "no-update-offered")
    V("verify-error-status",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "updatecheck", "status"],
                        "error-internal")), "no-update-offered")

    # ---- version law (4) ----
    for cid, ver, why in [
        ("verify-three-part-version", "1.2.0", "non-canonical-version"),
        ("verify-leading-zero", "1.02.0.0", "non-canonical-version"),
        ("verify-five-part-version", "1.2.0.0.0", "non-canonical-version"),
        ("verify-garbage-version", "one.two", "non-canonical-version"),
    ]:
        V(cid, envelope(deepset(BASE_RESPONSE,
           ["app", 0, "updatecheck", "manifest", "version"], ver)), why)

    # ---- package law (3) ----
    V("verify-missing-digest",
      canonical(delpath(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "updatecheck", "manifest",
                         "packages", "package", 0, "hash_sha256"])),
      "malformed-manifest")
    V("verify-short-digest",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "updatecheck", "manifest",
                         "packages", "package", 0, "hash_sha256"], "ab" * 16)),
      "bad-digest")
    V("verify-insecure-url",
      canonical(deepset(json.loads(envelope(BASE_RESPONSE)),
                        ["response", "app", 0, "updatecheck", "urls", "url",
                         0, "codebase"], "http://updates.example/xr/")),
      "insecure-url")

    # ---- signature law (3) ----
    V("verify-bad-signature", envelope(BASE_RESPONSE, sig_value="sig:" + "f" * 16),
      "signature-invalid")
    V("verify-missing-signature", envelope(BASE_RESPONSE, sig_value=""),
      "malformed-manifest")
    V("verify-unknown-signing-key",
      envelope(BASE_RESPONSE, key_id="xr-rogue-key"), "unknown-signing-key")

    # ---- epoch law (4) ----
    V("verify-revoked-epoch", good, "epoch-revoked",
      epoch={"epoch_id": "epoch-2026-09", "key_id": "xr-root-1", "seq": 3,
             "revoked": True, "manual_path": True})
    V("verify-unknown-epoch", good, "epoch-revoked",
      epoch={"epoch_id": "epoch-2025-01", "key_id": "xr-root-1", "seq": 2,
             "revoked": False, "manual_path": False})
    V("verify-epoch-regression", good, "epoch-revoked",
      epoch={"epoch_id": "epoch-2026-09", "key_id": "xr-root-1", "seq": 9,
             "revoked": False, "manual_path": False})
    V("verify-epoch-key-mismatch", good, "unknown-signing-key",
      epoch={"epoch_id": "epoch-2026-09", "key_id": "xr-signing-2026-09",
             "seq": 3, "revoked": False, "manual_path": False})

    # ---- monotonicity (2) + replay (2) ----
    V("verify-downgrade-refused", envelope(deepset(BASE_RESPONSE,
      ["app", 0, "updatecheck", "manifest", "version"], "0.9.9.9")),
      "downgrade-refused", current="1.0.0.0")
    V("verify-equal-version-reoffer", envelope(deepset(BASE_RESPONSE,
      ["app", 0, "updatecheck", "manifest", "version"], "1.0.0.0")),
      "equal-version-reoffer", current="1.0.0.0")
    mid = envelope(deepset(BASE_RESPONSE, ["app", 0, "updatecheck",
                                           "manifest", "version"], "1.1.0.0"))
    mid_id = hashlib.sha256(json.loads(mid)["response"] and
                            canonical(json.loads(mid)["response"]).encode()
                            ).hexdigest()
    V("verify-replay-refused", mid, "replay-refused", seen=[mid_id])
    V("verify-replay-other-id", mid, "ok", seen=["0" * 64])

    # ---- channel / TEST-ONLY refusal (2) + malformed frame (2) ----
    V("verify-release-channel-test-verifier-refused", good,
      "test-verifier-refused", channel="beta")
    V("verify-stable-channel-test-verifier-refused", good,
      "test-verifier-refused", channel="stable")
    add("verify-missing-envelope", "verify",
        {"channel": "dev", "current_version": "1.0.0.0", "keys": KEYS},
        {"error": "kMalformedInput"})
    add("verify-unknown-arg", "verify",
        dict(verify_args(good), cookie="track-me"),
        {"error": "kMalformedInput"})

    # ---- epoch-apply surface (4) ----
    notice_body = {"epoch_id": "epoch-2026-09", "key_id": "xr-root-1",
                   "reason": "key compromise drill", "schema":
                   "xr-epoch-revocation", "schema_version": 1, "seq": 4}
    notice = canonical({"body": notice_body,
                        "signature": {"alg": "minisign-ed25519",
                                      "key_id": "xr-root-1",
                                      "sig": stub_sig(notice_body,
                                                      "xr-root-1")}})
    add("epoch-apply-valid", "epoch-apply",
        {"epoch": EPOCH, "keys": KEYS, "notice": notice},
        {"applied": True,
         "epoch": {"epoch_id": "epoch-2026-09", "key_id": "xr-root-1",
                   "manual_path": True, "revoked": True, "seq": 4}})
    stale = dict(notice_body, seq=1)
    notice_stale = canonical({"body": stale,
                              "signature": {"alg": "minisign-ed25519",
                                            "key_id": "xr-root-1",
                                            "sig": stub_sig(stale,
                                                            "xr-root-1")}})
    add("epoch-apply-stale-ignored", "epoch-apply",
        {"epoch": EPOCH, "keys": KEYS, "notice": notice_stale},
        {"applied": False,
         "epoch": {"epoch_id": "epoch-2026-09", "key_id": "xr-root-1",
                   "manual_path": False, "revoked": False, "seq": 3}})
    bad = canonical({"body": notice_body,
                     "signature": {"alg": "minisign-ed25519",
                                   "key_id": "xr-root-1",
                                   "sig": "sig:" + "0" * 16}})
    add("epoch-apply-bad-signature", "epoch-apply",
        {"epoch": EPOCH, "keys": KEYS, "notice": bad},
        {"error": "kRejected", "reason": "signature-invalid"})
    add("epoch-apply-unknown-field", "epoch-apply",
        {"epoch": EPOCH, "keys": KEYS,
         "notice": canonical({"body": dict(notice_body, urgent=True),
                              "signature": {"sig": "x"}})},
        {"error": "kMalformedInput", "detail": "bad notice (unknown-field)"})

    # ---- cohort (4): determinism, range, channel separation, boundaries ----
    add("cohort-deterministic", "cohort",
        {"buckets": 100, "channel": "stable",
         "install_id": "0f3a1c-device-uuid"}, {"bucket": 79})
    add("cohort-differs-by-install", "cohort",
        {"buckets": 100, "channel": "stable",
         "install_id": "0f3a1c-device-uuix"}, {"bucket": 41})
    add("cohort-differs-by-channel", "cohort",
        {"buckets": 100, "channel": "nightly",
         "install_id": "0f3a1c-device-uuid"}, {"bucket": 94})
    add("cohort-bad-buckets", "cohort",
        {"buckets": 0, "channel": "stable",
         "install_id": "x"}, {"error": "kMalformedInput"})

    # ---- backoff (5): 6 h floor, doubling, cap, monotonic ----
    add("backoff-fresh-may-check", "backoff",
        {"now_mono": 1000,
         "state": {"fail_streak": 0, "last_check_mono": -1,
                   "next_allowed_mono": 0}},
        {"may_check_now": True, "seconds_until_next": 0,
         "state": {"fail_streak": 0, "last_check_mono": -1,
                   "next_allowed_mono": 0}})
    add("backoff-success-6h-floor", "backoff",
        {"now_mono": 1000, "outcome": "success",
         "state": {"fail_streak": 0, "last_check_mono": -1,
                   "next_allowed_mono": 0}},
        {"may_check_now": False, "seconds_until_next": 21600,
         "state": {"fail_streak": 0, "last_check_mono": 1000,
                   "next_allowed_mono": 22600}})
    add("backoff-failure-doubles", "backoff",
        {"now_mono": 100000, "outcome": "failure",
         "state": {"fail_streak": 2, "last_check_mono": 90000,
                   "next_allowed_mono": 108000}},
        {"may_check_now": False, "seconds_until_next": 21600,
         "state": {"fail_streak": 3, "last_check_mono": 100000,
                   "next_allowed_mono": 121600}})
    add("backoff-failure-cap-48h", "backoff",
        {"now_mono": 100000, "outcome": "failure",
         "state": {"fail_streak": 20, "last_check_mono": 90000,
                   "next_allowed_mono": 108000}},
        {"may_check_now": False, "seconds_until_next": 172800,
         "state": {"fail_streak": 21, "last_check_mono": 100000,
                   "next_allowed_mono": 272800}})
    add("backoff-clocked-never-goes-backwards", "backoff",
        {"now_mono": 22600,
         "state": {"fail_streak": 0, "last_check_mono": 1000,
                   "next_allowed_mono": 22600}},
        {"may_check_now": True, "seconds_until_next": 0,
         "state": {"fail_streak": 0, "last_check_mono": 1000,
                   "next_allowed_mono": 22600}})

    # ---- about-state machine (8): every state + the refused terminal law ----
    transitions = [
        ("idle", "check", {"state": "checking"}),
        ("checking", "offer", {"state": "available"}),
        ("checking", "noupdate", {"reason": "up to date", "state": "idle"}),
        ("available", "download-start", {"state": "downloading"}),
        ("downloading", "download-done", {"state": "ready"}),
        ("checking", "error", {"check_again": True,
                               "manual_download": {"path": "xr://about -> "
                                                           "manual download"},
                               "reason": "update failed: reason shown with a "
                                         "manual-download path",
                               "state": "failed"}),
        ("refused", "check", {"manual_download": {"path": "xr://about -> "
                                                          "manual download"},
                              "reason": "epoch revoked: manual download "
                                        "required",
                              "state": "refused"}),
        ("idle", "epoch-revoked", {"manual_download": {"path": "xr://about -> "
                                                               "manual "
                                                               "download"},
                                   "reason": "epoch revoked: manual download "
                                             "required",
                                   "state": "refused"}),
    ]
    for i, (st, ev, expect) in enumerate(transitions, 1):
        add(f"about-state-{i}-{st}-{ev}".replace("/", "-"), "about-state",
            {"event": ev, "state": st}, expect)
    add("about-state-invalid-transition", "about-state",
        {"event": "offer", "state": "idle"},
        {"error": "kRejected", "reason": "unknown transition"})

    doc = {"cases": cases, "schema": "xr-update-vectors",
           "schema_version": 1,
           "note": "Golden vectors for the update surface (P10-T1): typed "
                   "verdict + reason per case; signatures are the TEST-ONLY "
                   "fixture value; byte-parity runs across update_host (C++) "
                   "and fakes/update.py via tools/update_vectors_check.py."}
    blob = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out = repo / OUT
    if a.check:
        if not out.exists() or out.read_text(encoding="utf-8") != blob:
            print(f"DRIFT: {OUT} does not match regeneration; "
                  "run tools/gen_update_vectors.py")
            return 1
        print(f"PASS: {OUT} regenerates byte-identical ({len(cases)} cases)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    print(f"wrote {len(cases)} cases -> {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
