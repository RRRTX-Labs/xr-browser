#!/usr/bin/env python3
"""release/server/refimpl/update_server_ref.py — the Python REFERENCE
implementation of the XR update server (P10-T2).

This is the language-neutral core's executable form: it reads the spec
YAMLs (../spec/), accepts one 3.1 request frame, and renders the exact
response bytes per release/server/spec/render-31.md. NO network, NO
state, NO accounts: handle(request_bytes, content_length=None) is pure
(same input ⇒ same bytes; the statelessness conformance cases pin it).

The deployable is release/server/rust/ (std-only Rust, zero crates); the
two MUST agree byte-for-byte on release/server/tests/conformance.json —
any divergence is a red gate (the P9 differential-parity lesson).

Signing: TEST-ONLY stub scheme over canonical(response) — the SAME stub
material the client test fixture pins (SIGNING-PUB for
xr-signing-2026-09). Production signing is HSM-held (HG-36); the server
binds it as injected key material, never as code.

CLI:
  --self-check          render + assert the invariants locally, print PASS
  --gen-spec-readme     (re)generate ../spec/README.md from the spec YAMLs
  --check               with --gen-spec-readme: byte-parity or exit 1
  --handle FILE         render one request frame from FILE to stdout
Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"
REQUEST_CAP = 65536
PREFIX = ")]}'\n"
APP_ID = "labs.rrrtx.xr"
MAX_APPID = 128

# TEST-ONLY stub key material (mirrors xr-core/update/tests/env_helper.h +
# xr-browser/tools/gen_update_vectors.py KEY_MATERIAL; no real keys exist).
KEY_MATERIAL = {
    "xr-root-1": "ROOT-PUB",
    "xr-signing-2026-09": "SIGNING-PUB",
}

CHANNELS = ("nightly", "beta", "stable", "dev")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def stub_sig(material: str, message: str) -> str:
    return "sig:" + hashlib.sha256(
        (material + "|" + message).encode()).hexdigest()[:16]


def parse_version(v: str) -> tuple[int, ...] | None:
    """Canonical dotted-quad 'M.m.b.p' or None (non-canonical refused)."""
    parts = v.split(".")
    if len(parts) != 4:
        return None
    out = []
    for p in parts:
        if not p.isdigit() or (len(p) > 1 and p[0] == "0"):
            return None
        if int(p) > 65535:
            return None
        out.append(int(p))
    return tuple(out)


def load_spec() -> dict[str, Any]:
    import yaml  # pinned dev dependency (tools/DEPS.md)
    spec: dict[str, Any] = {}
    for name in ("version-graph", "channels", "cohorts", "epochs"):
        spec[name] = yaml.safe_load(
            (SPEC_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return spec


def err(status: int, code: str, detail: str) -> tuple[int, str]:
    body = canonical({"detail": detail, "error": code})
    return status, body + "\n"


def handle(frame: bytes, spec: dict[str, Any],
           content_length: int | None = None) -> tuple[int, str]:
    """Pure request → (http_status, response_bytes). No I/O, no state."""
    if len(frame) > REQUEST_CAP:
        return err(400, "kTooLarge", f"request above {REQUEST_CAP} cap")
    if content_length is not None:
        if content_length > len(frame):
            return err(400, "kTruncated",
                       f"content-length {content_length} > body {len(frame)}")
        if content_length < len(frame):
            return err(400, "kBadLength",
                       f"content-length {content_length} < body {len(frame)}")
    body = frame.decode("utf-8", errors="replace")
    if body.startswith(PREFIX):
        body = body[len(PREFIX):]
    try:
        req = json.loads(body)
    except Exception:
        return err(400, "kMalformedRequest", "bad json")
    if not isinstance(req, dict):
        return err(400, "kMalformedRequest", "request not an object")
    if set(req) != {"protocol", "os", "app"}:
        return err(400, "kUnknownField",
                   "request keys must be exactly protocol/os/app")
    if req["protocol"] != "3.1":
        return err(400, "kWrongProtocol", f"protocol {req['protocol']!r}")
    if not isinstance(req["os"], dict):
        return err(400, "kMalformedRequest", "os must be an object")
    apps = req["app"]
    if not isinstance(apps, list) or not apps:
        return err(400, "kMalformedRequest", "app must be a non-empty array")

    vg = spec["version-graph"]["channels"]
    ch_spec = spec["channels"]["channels"]
    cohorts = spec["cohorts"]["per_channel"]
    active = spec["epochs"]["active"]
    revoked = {r.get("epoch_id") for r in spec["epochs"].get("revoked", [])}

    out_apps: list[dict[str, Any]] = []
    for app in apps:
        if not isinstance(app, dict) or set(app) - {
                "appid", "version", "channel", "bucket", "epoch"}:
            return err(400, "kUnknownField", "bad app entry")
        appid = app.get("appid")
        if not isinstance(appid, str) or not (0 < len(appid) <= MAX_APPID):
            return err(400, "kBadAppid", f"appid {appid!r}")
        channel = app.get("channel")
        if channel not in CHANNELS:
            return err(400, "kBadChannel", f"channel {channel!r}")
        bucket = app.get("bucket")
        if not isinstance(bucket, int) or isinstance(bucket, bool) or \
                not (0 <= bucket <= 99):
            return err(400, "kBadBucket", f"bucket {bucket!r}")
        epoch = app.get("epoch")
        if epoch is not None and not isinstance(epoch, str):
            return err(400, "kUnknownField", "epoch must be a string")
        # os entry is closed too (parsed, ignored)
        os_block = req["os"]
        if set(os_block) - {"platform", "version", "arch"}:
            return err(400, "kUnknownField", "bad os entry")

        entry: dict[str, Any] = {"appid": appid}
        if appid != APP_ID:
            entry["status"] = "error-unknownApplication"
            out_apps.append(entry)
            continue
        cs = ch_spec[channel]
        uc: dict[str, Any] = {}
        if not cs["served"]:
            uc["status"] = "noupdate"  # dev: dev-only-until-P16-exit
        elif cs["paused"]:
            uc["status"] = spec["channels"]["pause_semantics"]
        elif epoch is not None and epoch in revoked:
            uc["status"] = "error-epochRevoked"
        elif bucket >= cohorts[channel]["ramp_percent"]:
            uc["status"] = "noupdate"
        else:
            rawv = app.get("version", "")
            cur = parse_version(rawv) if isinstance(rawv, str) else None
            if cur is None:
                return err(400, "kBadVersion",
                           f"version {rawv!r} non-canonical")
            head = vg[channel]["head"]
            hv = parse_version(head["version"])
            assert hv is not None
            if cur >= hv:
                uc["status"] = "noupdate"
            else:
                uc["status"] = "ok"
                uc["manifest"] = {
                    "packages": {"package": [{
                        "fp": head["version"],
                        "hash_sha256": head["hash_sha256"],
                        "name": f"xr-{head['version']}.crx",
                        "size": head["size"],
                    }]},
                    "run": "",
                    "version": head["version"],
                }
                uc["urls"] = {"url": [{"codebase": head["url"]}]}
        entry["status"] = "ok"
        entry["updatecheck"] = uc
        out_apps.append(entry)

    response = {
        "app": out_apps,
        "daystart": {"elapsed_days": 0},
        "protocol": "3.1",
        "server": "pub",
    }
    envelope = {
        "epoch": {"epoch_id": active["epoch_id"], "key_id": active["key_id"],
                  "seq": active["seq"]},
        "response": response,
        "schema": "xr-update-envelope",
        "schema_version": 1,
        "signature": {
            "alg": "minisign-ed25519",
            "key_id": active["key_id"],
            "sig": stub_sig(KEY_MATERIAL[active["key_id"]],
                            canonical(response)),
        },
    }
    return 200, PREFIX + canonical(envelope) + "\n"


SPEC_README_HEADER = """# release/server/spec — the language-neutral update-server spec

GENERATED by `release/server/refimpl/update_server_ref.py --gen-spec-readme`
(--check is diff-clean law). Source of truth: the four YAMLs + render-31.md.
Consumed by BOTH backends: this reference and release/server/rust/.

"""


def gen_spec_readme(spec: dict[str, Any]) -> str:
    lines = [SPEC_README_HEADER]
    for name in ("channels", "cohorts", "epochs", "version-graph"):
        doc = spec[name]
        lines.append(f"## {name}.yaml — schema {doc['schema']} v{doc['schema_version']}\n\n")
        if name == "channels":
            for ch, cs in doc["channels"].items():
                lines.append(f"- **{ch}**: served={cs['served']} "
                             f"paused={cs['paused']} ramp={cs['ramp_percent']}%")
            lines.append(f"- pause semantics: `{doc['pause_semantics']}`")
        elif name == "cohorts":
            lines.append(f"- buckets: {doc['buckets']}; law: `{doc['ramp_law']}`")
            for ch, cs in sorted(doc["per_channel"].items()):
                lines.append(f"- {ch}: ramp {cs['ramp_percent']}% "
                             f"({cs['boundary_note']})")
        elif name == "epochs":
            a = doc["active"]
            lines.append(f"- active: {a['epoch_id']} key {a['key_id']} seq {a['seq']}")
            lines.append(f"- revoked: {len(doc['revoked'])} epoch(s)")
            lines.append(f"- key material: TEST-ONLY stubs (no real keys, ADR-0004)")
        else:
            for ch, g in sorted(doc["channels"].items()):
                lines.append(f"- {ch}: head {g['head']['version']} "
                             f"({g['head']['size']} bytes), "
                             f"{len(g['ancestors'])} ancestor(s)")
        lines.append("")
    return "\n".join(lines) + "\n"


def self_check() -> int:
    spec = load_spec()
    # happy path: nightly, old version, in-ramp bucket
    req = canonical({"app": [{"appid": APP_ID, "bucket": 0, "channel":
                              "nightly", "version": "0.9.21.0"}],
                     "os": {"platform": "linux"}, "protocol": "3.1"})
    status, out = handle(req.encode(), spec)
    assert status == 200, out
    assert out.startswith(PREFIX)
    env = json.loads(out[len(PREFIX):])
    # re-canonicalizing the parsed envelope reproduces the bytes (canonical law)
    assert canonical(env) + "\n" == out[len(PREFIX):], "response not canonical"
    # the signature verifies under the client stub (material-bound)
    expect = stub_sig(KEY_MATERIAL[env["signature"]["key_id"]],
                      canonical(env["response"]))
    assert env["signature"]["sig"] == expect, "self sig mismatch"
    assert env["response"]["app"][0]["updatecheck"]["status"] == "ok"
    # statelessness: same input twice ⇒ same bytes
    assert handle(req.encode(), spec) == (status, out)
    # response size law (raw)
    assert len(out) <= 2048, f"response {len(out)} > 2048"
    # unknown field refused, wrong protocol refused, oversized refused
    bad = canonical({"app": req and [{"appid": APP_ID, "bucket": 0,
                                      "channel": "nightly",
                                      "version": "0.9.21.0"}],
                     "extra": 1, "os": {}, "protocol": "3.1"})
    assert handle(bad.encode(), spec)[0] == 400
    assert handle(b'{"protocol":"3.0","os":{},"app":[{"appid":"labs.rrrtx.xr",'
                  b'"bucket":0,"channel":"nightly","version":"0.9.21.0"}]}',
                  spec)[0] == 400
    assert handle(b"x" * (REQUEST_CAP + 1), spec)[0] == 400
    print(f"PASS: update_server_ref self-check (render+verify+statelessness+"
          f"cap; response {len(out)} bytes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="update_server_ref",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--gen-spec-readme", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--handle", type=str, default=None,
                    help="path to one request frame ('-' = stdin)")
    a = ap.parse_args(argv)
    if a.self_check:
        return self_check()
    spec = load_spec()
    if a.gen_spec_readme:
        out = SPEC_DIR / "README.md"
        rendered = gen_spec_readme(spec)
        if a.check:
            want = out.read_text(encoding="utf-8")
            if want != rendered:
                print("FAIL: spec/README.md stale (run --gen-spec-readme)")
                return 1
            print("PASS: spec/README.md diff-clean")
            return 0
        out.write_text(rendered, encoding="utf-8")
        print(f"wrote {out}")
        return 0
    if a.handle:
        raw = (sys.stdin.buffer.read() if a.handle == "-"
               else Path(a.handle).read_bytes())
        status, out = handle(raw, spec)
        sys.stdout.write(out)
        return 0 if status == 200 else 1
    ap.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
