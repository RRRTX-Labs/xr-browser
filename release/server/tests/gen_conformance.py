#!/usr/bin/env python3
"""release/server/tests/gen_conformance.py — builds the conformance corpus.

The corpus is COMMITTED DATA (release/server/tests/conformance.json); this
generator is how it is built and re-verified: expectations are the
REFERENCE implementation's exact bytes (the reference is the spec's
executable form — render-31.md). The Rust deployable replays the same
corpus on the hosted runner; a byte of divergence is a red gate.

Every case pins: the raw request frame, the optional Content-Length, an
optional spec overlay (e.g. pause a channel, add a revocation — applied
identically by both backends), the expected HTTP status, and the expected
response BYTES.

Exit: 0 corpus consistent · 1 drift. Stdlib only.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".." / "refimpl"))

import update_server_ref as ref  # noqa: E402

CORPUS = HERE / "conformance.json"
APP = ref.APP_ID
V = "0.9.21.0"          # an ancestor of the nightly head
BETA_V = "0.9.19.0"     # older than the beta head

PAUSE_BETA = {"channels": {"channels": {"beta": {"paused": True}}}}
REVOKE_ACTIVE = {"epochs": {"revoked": [{
    "client_effect": "forced manual path", "epoch_id": "epoch-2026-05",
    "key_id": "xr-signing-2026-05", "reason": "key compromise drill",
    "seq": 9}]}}

OS_OK = {"platform": "linux"}

# Named spec variants (the corpus's overlay axis; both backends must apply
# them identically — the Rust side gets each variant PRE-MERGED by
# tools/gen_server_spec_rs.py, the Python side merges at load).
VARIANT_BASE = None
VARIANTS = {"pause-beta": PAUSE_BETA, "revoke-active": REVOKE_ACTIVE}
VARIANT_NAMES = {json.dumps(None, sort_keys=True): "base"}
VARIANT_NAMES.update({json.dumps(v, sort_keys=True): k
                      for k, v in VARIANTS.items()})


def req(app, os_block=None, protocol="3.1"):
    return ref.canonical({"app": app, "os": os_block or OS_OK,
                          "protocol": protocol})


def app(channel="nightly", version=V, bucket=0, appid=APP, epoch=None):
    a = {"appid": appid, "bucket": bucket, "channel": channel,
         "version": version}
    if epoch is not None:
        a["epoch"] = epoch
    return a


def main() -> int:
    spec0 = ref.load_spec()
    cases: list[dict] = []

    def merge(dst: dict, src: dict) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v

    def spec_for(overlay: dict | None) -> dict:
        if not overlay:
            return spec0
        spec = copy.deepcopy(spec0)
        for top, sub in overlay.items():
            merge(spec[top], sub)
        return spec

    def add(cid, frame, *, cl=None, overlay=None, note=""):
        spec = spec_for(overlay)

        status, out = ref.handle(frame.encode(), spec, cl)
        case = {"content_length": cl, "expect_response": out,
                "expect_status": status, "id": cid, "note": note,
                "request": frame,
                "spec_variant": VARIANT_NAMES[json.dumps(overlay, sort_keys=True)]}
        cases.append(case)
        return status, out

    # -- happy paths -----------------------------------------------------
    add("happy-nightly-old-version",
        req([app()], {"platform": "linux", "arch": "amd64",
                      "version": "1.0"}),
        note="head offer, os parsed+ignored")
    add("happy-nightly-with-prefix", ref.PREFIX + req([app()]),
        note="the )]}' prefix is optional and stripped")
    add("happy-beta-in-ramp", req([app("beta", BETA_V, 0)]))
    add("happy-multiple-apps",
        req([app("nightly", V, 0), app("beta", BETA_V, 3),
             app("dev", V, 0)]),
        note="one frame, three entries: offer/offer/dev-noupdate")
    add("happy-no-prefix", req([app()]))
    add("happy-cap-boundary",
        req([app()], {"platform": "x" * (ref.REQUEST_CAP - 400)}),
        note="body lands exactly under the cap -> 200")
    add("happy-unicode-os-escaped",
        req([app()], {"platform": "línu×"}),
        note="non-ASCII renders as \\uXXXX (ensure_ascii law)")
    add("happy-active-epoch-echo", req([app(epoch="epoch-2026-09")]))

    # -- cohort boundaries (the off-by-one is pinned, never vibes) --------
    add("beta-boundary-49-in", req([app("beta", BETA_V, 49)]))
    add("beta-boundary-50-out", req([app("beta", BETA_V, 50)]))
    add("nightly-bucket-99-in", req([app("nightly", V, 99)]))
    add("nightly-bucket-0-in", req([app("nightly", V, 0)]))

    # -- up-to-date / never-downgrade -------------------------------------
    add("stable-up-to-date-noupdate",
        req([app("stable", "0.9.18.2", 0)]), note="equal version")
    add("stable-newer-client-noupdate",
        req([app("stable", "9.9.9.9", 0)]), note="newer than head")
    add("dev-unserved-noupdate", req([app("dev", "0.0.0.0", 0)]))

    # -- paused channel (spec overlay pins the paused bytes) --------------
    add("paused-beta-typed-error",
        req([app("beta", BETA_V, 0)]), overlay=PAUSE_BETA,
        note="error-pausedChannel per channels.yaml")
    add("paused-beta-nightly-unaffected",
        req([app("nightly", V, 0), app("beta", BETA_V, 0)]),
        overlay=PAUSE_BETA, note="only the paused channel refuses")

    # -- epoch revocation (overlay; after it lands bytes MUST differ) -----
    add("epoch-revoked-typed-error",
        req([app("nightly", V, 0, epoch="epoch-2026-05")]),
        overlay=REVOKE_ACTIVE)
    add("epoch-revoked-but-noupdate-bucket",
        req([app("beta", BETA_V, 50, epoch="epoch-2026-05")]),
        overlay=REVOKE_ACTIVE,
        note="bucket-out wins? no: revocation checked before ramp")
    add("epoch-revoked-other-client-unaffected",
        req([app(epoch="epoch-2026-09")]), overlay=REVOKE_ACTIVE)
    add("unknown-appid-typed-error",
        req([app(appid="labs.other.xr")]),
        note="200 envelope, error-unknownApplication entry")

    # -- request closure (unknown fields at every level) -------------------
    add("unknown-field-request-level",
        ref.canonical({"app": [app()], "extra": 1, "os": OS_OK,
                       "protocol": "3.1"}))
    add("unknown-field-app-level",
        req([dict(app(), brand="x")]))
    add("unknown-field-os-level",
        req([app()], {"platform": "linux", "platform2": "x"}))
    add("missing-app", ref.canonical({"os": OS_OK, "protocol": "3.1"}))
    add("missing-protocol", ref.canonical({"app": [app()], "os": OS_OK}))

    # -- protocol / framing ------------------------------------------------
    add("wrong-protocol-3.0",
        req([app()], protocol="3.0"))
    add("wrong-protocol-missing-version",
        req([app()], protocol=""))
    add("malformed-json", "{\"app\": [", )
    add("request-not-object", "[1,2,3]")
    add("double-prefix", ref.PREFIX + ref.PREFIX + req([app()]),
        note="only ONE prefix is stripped; the rest is malformed json")
    add("empty-app-array", ref.canonical({"app": [], "os": OS_OK,
                                          "protocol": "3.1"}))
    add("app-entry-not-object", ref.canonical({"app": ["x"], "os": OS_OK,
                                               "protocol": "3.1"}))

    # -- appid / channel / bucket validation -------------------------------
    add("bad-appid-empty", req([app(appid="")]))
    add("bad-appid-oversized", req([app(appid="a" * 129)]))
    add("bad-channel", req([app("canary")]))
    add("bad-bucket-100", req([app("nightly", V, 100)]))
    add("bad-bucket-negative", req([app("nightly", V, -1)]))
    add("bad-bucket-bool", req([{"appid": APP, "bucket": True,
                                 "channel": "nightly", "version": V}]))
    add("bad-bucket-missing", req([{"appid": APP, "channel": "nightly",
                                    "version": V}]))

    # -- version canonicality ----------------------------------------------
    add("bad-version-three-part", req([app("nightly", "1.2.3")]))
    add("bad-version-five-part", req([app("nightly", "1.2.3.4.5")]))
    add("bad-version-leading-zero", req([app("nightly", "01.2.3.4")]))
    add("bad-version-empty", req([app("nightly", "")]))
    add("bad-version-non-numeric", req([app("nightly", "next")]))
    add("bad-version-missing", req([{"appid": APP, "bucket": 0,
                                     "channel": "nightly"}]))

    # -- content-length framing (slow-client truncation et al) -------------
    frame = req([app()])
    n = len(frame)
    add("cl-truncated", frame[: n - 5], cl=n, note="slow client cut mid-body")
    add("cl-longer", frame, cl=n + 1, note="declared > actual")
    add("cl-ok", frame, cl=n)
    add("cl-shorter", frame, cl=n - 1, note="declared < actual")
    add("too-large", "x" * (ref.REQUEST_CAP + 1),
        note="above the cap -> refused before parse")

    # -- build + verify the corpus ----------------------------------------
    # cross-backend invariants every case must satisfy (both backends run
    # these): determinism (same input twice => same bytes) and, for 200s,
    # canonical-byte identity after a parse round-trip.
    for c in cases:
        overlay = VARIANTS.get(c["spec_variant"])
        spec = spec_for(overlay)
        again = ref.handle(c["request"].encode(), spec, c["content_length"])
        if again != (c["expect_status"], c["expect_response"]):
            print(f"FAIL: {c['id']} nondeterministic")
            return 1
        if c["expect_status"] == 200:
            body = c["expect_response"]
            if not body.startswith(ref.PREFIX) or not body.endswith("\n"):
                print(f"FAIL: {c['id']} 200 missing prefix/trailing NL")
                return 1
            env = json.loads(body[len(ref.PREFIX):])
            if ref.canonical(env) + "\n" != body[len(ref.PREFIX):]:
                print(f"FAIL: {c['id']} response not canonical")
                return 1
            expect_sig = ref.stub_sig(
                ref.KEY_MATERIAL[env["signature"]["key_id"]],
                ref.canonical(env["response"]))
            if env["signature"]["sig"] != expect_sig:
                print(f"FAIL: {c['id']} signature not stub-valid")
                return 1

    doc = {"cases": cases, "schema": "xr-update-server-conformance",
           "schema_version": 1,
           "variants": {k: v for k, v in VARIANTS.items()}}
    rendered = json.dumps(doc, indent=1, sort_keys=True,
                          ensure_ascii=True) + "\n"
    if CORPUS.exists():
        old = CORPUS.read_text(encoding="utf-8")
        if old != rendered:
            CORPUS.write_text(rendered, encoding="utf-8")
            print(f"FAIL: corpus drifted; REWROTE {CORPUS} "
                  f"({len(cases)} cases) — re-run to confirm stability")
            return 1
    else:
        CORPUS.write_text(rendered, encoding="utf-8")
    n200 = sum(1 for c in cases if c["expect_status"] == 200)
    print(f"PASS: conformance corpus consistent ({len(cases)} cases, "
          f"{n200} render-31 responses, {len(cases) - n200} typed refusals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
