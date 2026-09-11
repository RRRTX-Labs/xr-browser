#!/usr/bin/env python3
"""release/server/tests/test_server_fuzz.py — structure-aware fuzzer for
the update-server reference (P10-T2; the plan's Tests row: >=600 s, 0
violations).

Oracle (the law): the server NEVER emits a manifest the client verifier
would accept without a valid signature/epoch — every 200 response is
re-verified with the client's own stub rules (sig over canonical(response)
under the active epoch's pinned material; epoch == the spec's active
epoch; canonical byte identity), and every 400 is a canonical typed
refusal. Second oracle: statelessness — the same bytes handled twice yield
identical responses. Third: the server never raises (a panic is a
violation, not a crash to catch).

Mutations are STRUCTURE-AWARE: they start from valid request frames and
mutate fields/levels the grammar defines (appid/channel/bucket/version/
epoch/os/protocol), plus raw byte classes (flip/insert/delete/junk/prefix/
framing/cap). Seeded; XR_FUZZ_SECONDS budget (default 30, evidence 600)
with XR_FUZZ_MIN_ITERS floor (P9 law). Stdlib only.
Exit: 0 pass · 1 fail.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".." / "refimpl"))

import update_server_ref as ref  # noqa: E402

SEED = 20260911
PREFIX = ref.PREFIX


def verify_like_client(env: dict) -> str | None:
    """The client-side stub verify, server-side. Returns a violation
    reason or None."""
    if set(env) != {"epoch", "response", "schema", "schema_version",
                    "signature"}:
        return "envelope not closed"
    if env.get("schema") != "xr-update-envelope":
        return "schema mismatch"
    if env.get("protocol-ish") is not None:
        return "impossible"
    sig = env.get("signature") or {}
    if set(sig) != {"alg", "key_id", "sig"}:
        return "signature not closed"
    if sig.get("alg") != "minisign-ed25519":
        return "wrong alg"
    material = ref.KEY_MATERIAL.get(sig.get("key_id"))
    if material is None:
        return "unpinned key material"
    resp = env.get("response")
    if not isinstance(resp, dict):
        return "response not an object"
    expect = ref.stub_sig(material, ref.canonical(resp))
    if sig.get("sig") != expect:
        return "signature invalid over canonical response"
    spec = FUZZ_SPEC
    active = spec["epochs"]["active"]
    epoch = env.get("epoch") or {}
    if epoch.get("epoch_id") != active["epoch_id"] or \
            epoch.get("key_id") != active["key_id"]:
        return "foreign epoch on a manifest response"
    if ref.canonical(env) + "\n" != LAST_BYTES[0][len(PREFIX):]:
        return "response not canonical"
    return None


FUZZ_SPEC = {}
LAST_BYTES = [""]


def base_frames() -> list[bytes]:
    app = {"appid": ref.APP_ID, "bucket": 7, "channel": "nightly",
           "version": "0.9.21.0"}
    good = ref.canonical({"app": [app], "os": {"platform": "linux"},
                          "protocol": "3.1"})
    return [good.encode(), (PREFIX + good).encode(),
            ref.canonical({"app": [dict(app, channel="beta"),
                                   dict(app, bucket=99)],
                           "os": {"platform": "win"}, "protocol": "3.1"}).encode()]


def mutate(frame: bytes, rng: random.Random) -> tuple[bytes, int | None]:
    """One structure-aware mutation class per call."""
    cl = None
    cls = rng.randrange(9)
    if cls == 0:  # field flip
        try:
            doc = json.loads(frame.decode())
            if isinstance(doc, dict):
                key = rng.choice(list(doc) or ["app"])
                doc[key] = rng.choice([None, 3, "3.0", {}, [], "x"])
                return ref.canonical(doc).encode(), cl
        except Exception:
            return frame, cl
    if cls == 1:  # app-entry mutation
        try:
            doc = json.loads(frame.decode())
            app = doc["app"][0]
            field = rng.choice(["appid", "bucket", "channel", "version",
                                "epoch"])
            app[field] = rng.choice(["", "x" * 200, -1, 100, True, None,
                                     "dev", "01.2.3.4", "1.2.3.4.5",
                                     "epoch-rogue"])
            return ref.canonical(doc).encode(), cl
        except Exception:
            return frame, cl
    if cls == 2:  # unknown field injection at a random level
        try:
            doc = json.loads(frame.decode())
            rng.choice([
                lambda d: d.update(rogue=1),
                lambda d: d["os"].update(rogue=1),
                lambda d: d["app"][0].update(rogue=1),
            ])(doc)
            return ref.canonical(doc).encode(), cl
        except Exception:
            return frame, cl
    if cls == 3:  # byte flip
        if not frame:
            return frame, cl
        i = rng.randrange(len(frame))
        return frame[:i] + bytes([frame[i] ^ (1 << rng.randrange(7))]) \
            + frame[i + 1:], cl
    if cls == 4:  # junk insert
        i = rng.randrange(len(frame) + 1)
        junk = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 8)))
        return frame[:i] + junk + frame[i:], cl
    if cls == 5:  # truncate
        if not frame:
            return frame, cl
        i = rng.randrange(len(frame))
        cl = i + rng.choice([0, 1, 5, len(frame)])
        return frame[:i], cl
    if cls == 6:  # prefix games
        return rng.choice([
            PREFIX + frame.decode(errors="replace"),
            PREFIX + PREFIX + frame.decode(errors="replace"),
            frame.decode(errors="replace").lstrip(")}"),
        ]).encode(), cl
    if cls == 7:  # oversize
        return b"x" * rng.randrange(ref.REQUEST_CAP,
                                    ref.REQUEST_CAP + 64), cl
    # cls == 8: valid-but-varied (the differential baseline)
    try:
        doc = json.loads(frame.decode())
        if isinstance(doc, dict) and isinstance(doc.get("app"), list) and \
                doc["app"]:
            doc["app"][0]["bucket"] = rng.randrange(0, 100)
            doc["app"][0]["channel"] = rng.choice(
                ["nightly", "beta", "stable", "dev"])
        return ref.canonical(doc).encode(), cl
    except Exception:
        return frame, cl


def main() -> int:
    budget = int(os.environ.get("XR_FUZZ_SECONDS", "30"))
    min_iters = int(os.environ.get("XR_FUZZ_MIN_ITERS", "1000"))
    rng = random.Random(SEED)
    FUZZ_SPEC.clear()
    FUZZ_SPEC.update(ref.load_spec())
    pool = base_frames()
    t0 = time.monotonic()
    iters = 0
    accepted = 0
    denied = 0
    violations = 0
    while time.monotonic() - t0 < budget or iters < min_iters:
        frame, cl = mutate(rng.choice(pool), rng)
        try:
            status, out = ref.handle(frame, FUZZ_SPEC, cl)
        except Exception as exc:  # a raise is a violation, not a crash
            print(f"FAIL: server raised after {iters} iters: {exc!r}")
            return 1
        iters += 1
        # statelessness oracle
        if ref.handle(frame, FUZZ_SPEC, cl) != (status, out):
            print(f"FAIL: stateful after {iters} iters")
            return 1
        if status == 200:
            accepted += 1
            LAST_BYTES[0] = out
            env = json.loads(out[len(PREFIX):])
            v = verify_like_client(env)
            if v:
                print(f"FAIL: oracle violation after {iters} iters: {v}\n"
                      f"frame: {frame[:160]!r}\nresponse: {out[:160]!r}")
                return 1
            if len(out) > 2048:
                print(f"FAIL: 200 response {len(out)} > 2048 after "
                      f"{iters} iters")
                return 1
        else:
            denied += 1
            try:
                errdoc = json.loads(out)
                if set(errdoc) != {"detail", "error"} or \
                        ref.canonical(errdoc) + "\n" != out:
                    print(f"FAIL: 400 not canonical typed refusal after "
                          f"{iters} iters: {out[:120]!r}")
                    return 1
            except Exception:
                print(f"FAIL: 400 not JSON after {iters} iters: "
                      f"{out[:120]!r}")
                return 1
    # revocation must change bytes (the epoch-flip law, exercised live)
    spec2 = copy.deepcopy(FUZZ_SPEC)
    spec2["epochs"]["revoked"] = [{
        "client_effect": "forced manual path",
        "epoch_id": FUZZ_SPEC["epochs"]["active"]["epoch_id"],
        "key_id": FUZZ_SPEC["epochs"]["active"]["key_id"],
        "reason": "drill", "seq": 99}]
    app = {"appid": ref.APP_ID, "bucket": 0, "channel": "nightly",
           "version": "0.9.21.0",
           "epoch": FUZZ_SPEC["epochs"]["active"]["epoch_id"]}
    frame = ref.canonical({"app": [app], "os": {}, "protocol": "3.1"}).encode()
    if ref.handle(frame, FUZZ_SPEC, None)[1] == ref.handle(frame, spec2, None)[1]:
        print("FAIL: revocation did not change the response bytes")
        return 1
    print(f"fuzz: {iters} iters, {accepted} render-31 responses, {denied} "
          f"typed refusals, {violations} violations (seed {SEED}, "
          f"budget {budget} s)")
    assert violations == 0
    print("PASS: server fuzz (never-accept-without-valid-signature/epoch, "
          "statelessness, canonical refusals, cap)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
