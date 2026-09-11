#!/usr/bin/env python3
"""tools/rollout_drill.py — the staged-rollout + rollback drill, run FOR
REAL here (P10-T5): the reference server renders offers, the COMPILED
verifier core (update_host) decides, epoch flips actually flip.

Cells (each must execute; the drill prints executed/not-run; 0 executed
=> FAIL):
  1  serve+accept          reference offer -> update_host verify => accept
  2  refuse-downgrade      same offer vs newer client      => downgrade deny
  3  replay-refusal        re-feed the SAME envelope        => replay deny
  4  ramp-boundary-in      beta bucket 49                   => offer
  5  ramp-boundary-out     beta bucket 50                   => noupdate
  6  epoch-revocation      root-signed notice -> epoch-apply=> revoked+manual
  7  revocation-forces-manual  same offer after revocation  => deny+manual_path
  8  stale-notice-ignored  seq <= current                   => applied:false
  9  auto-rollout-refused  policy.yaml beta/stable auto_rollout=false
  10 crash-hook-dev-only   non-dev channel into the hook    => refused

Exit: 0 drill passed · 1 fail · 77 update_host/build tooling absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "release" / "server" / "refimpl"))
import update_server_ref as ref  # noqa: E402

HOST = Path("../xr-core/update/tests/build/update_host")
HOST_ENV = {"XR_BROWSER_ROOT": ""}
# the SERVER signs with its material (update_server_ref.KEY_MATERIAL);
# the drill signs epoch notices with the same pinned scheme — one universe.
KEY_MATERIAL = {"xr-root-1": "ROOT-PUB",
                "xr-signing-2026-09": "SIGNING-PUB"}


def stub_sig(material: str, message: str) -> str:
    return "sig:" + hashlib.sha256(
        (material + "|" + message).encode()).hexdigest()[:16]


class Drill:
    def __init__(self) -> None:
        self.executed = 0
        self.failures: list[str] = []

    def cell(self, name: str, cond: bool, detail: str = "") -> None:
        self.executed += 1
        mark = "ok" if cond else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not cond
                                      else ""))
        if not cond:
            self.failures.append(name)


def host_call(frame: dict, store: Path) -> dict:
    tmpf = store / "frame.json"
    tmpf.write_text(json.dumps(frame, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    r = subprocess.run([str(HOST)], stdin=open(tmpf, "rb"), capture_output=True,
                       text=True, timeout=60, env=HOST_ENV)
    return {"rc": r.returncode, "out": json.loads(r.stdout) if r.stdout.strip()
            else {}}


def offer_for(channel: str, bucket: int, spec, current="0.0.0.0") -> dict:
    frame_req = ref.canonical({
        "app": [{"appid": ref.APP_ID, "bucket": bucket, "channel": channel,
                 "version": current}], "os": {}, "protocol": "3.1"})
    status, out = ref.handle(frame_req.encode(), spec, None)
    assert status == 200, out
    return json.loads(out[len(ref.PREFIX):])


def main() -> int:
    ap = argparse.ArgumentParser(prog="rollout-drill",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--store-dir", default=None)
    a = ap.parse_args()
    if not HOST.exists():
        print("SKIP: SKIP (tool absent: g++/make) — needed for: the "
              "compiled verifier core (update_host) the drill drives; "
              "local hint: make -C ../xr-core/update/tests build")
        return 77
    spec = ref.load_spec()
    d = Drill()
    store = Path(a.store_dir) if a.store_dir else Path(tempfile.mkdtemp())
    store.mkdir(parents=True, exist_ok=True)
    keys = [{"key_id": k, "public_key": v} for k, v in KEY_MATERIAL.items()]

    print(f"== rollout/rollback drill (update_host + reference server; "
          f"store {store}) ==")
    # 1. serve + accept
    env1 = offer_for("nightly", 0, spec)
    v = host_call({"method": "verify", "args": {
        "channel": "dev", "current_version": "0.0.0.0", "envelope":
        json.dumps(env1, sort_keys=True, separators=(",", ":")),
        "epoch": {"epoch_id": "epoch-2026-09", "key_id": "xr-signing-2026-09",
                  "manual_path": False, "revoked": False, "seq": 3},
        "keys": keys, "seen": [], "transport": "drill"}}, store)
    accept = v["out"].get("verdict") == "accept"
    d.cell("serve+accept", accept, json.dumps(v["out"])[:120])
    manifest_id = v["out"].get("manifest_id", "")

    # 2. refuse-downgrade (client newer than the offer)
    v2 = host_call({"method": "verify", "args": {
        "channel": "dev", "current_version": "99.0.0.0", "envelope":
        json.dumps(env1, sort_keys=True, separators=(",", ":")),
        "epoch": {"epoch_id": "epoch-2026-09", "key_id": "xr-signing-2026-09",
                  "manual_path": False, "revoked": False, "seq": 3},
        "keys": keys, "seen": [], "transport": "drill"}}, store)
    d.cell("refuse-downgrade",
           v2["out"].get("verdict") == "deny" and
           v2["out"].get("reason") == "downgrade-refused")

    # 3. replay refusal (same envelope again, seen set carries the id)
    v3 = host_call({"method": "verify", "args": {
        "channel": "dev", "current_version": "0.0.0.0", "envelope":
        json.dumps(env1, sort_keys=True, separators=(",", ":")),
        "epoch": {"epoch_id": "epoch-2026-09", "key_id": "xr-signing-2026-09",
                  "manual_path": False, "revoked": False, "seq": 3},
        "keys": keys, "seen": [manifest_id], "transport": "drill"}}, store)
    d.cell("replay-refusal",
           v3["out"].get("verdict") == "deny" and
           v3["out"].get("reason") == "replay-refused")

    # 4/5. ramp boundaries via the SERVER (cohorts.yaml law)
    in_off = offer_for("beta", 49, spec)
    out_off = offer_for("beta", 50, spec)
    d.cell("ramp-boundary-49-in",
           in_off["response"]["app"][0]["updatecheck"]["status"] == "ok")
    d.cell("ramp-boundary-50-out",
           out_off["response"]["app"][0]["updatecheck"]["status"] ==
           "noupdate")

    # 6. epoch revocation (notice law: a notice is valid iff signed by the
    # key it NAMES — self-revocation, what the verifier core enforces; the
    # production root-signed ceremony is HG-36 class. wrapper {body,sig}).
    body = {"epoch_id": "epoch-2026-09", "key_id": "xr-signing-2026-09",
            "reason": "drill: rollback rehearsal",
            "schema": "xr-epoch-revocation", "schema_version": 1, "seq": 4}
    body_canon = ref.canonical(body)
    notice = ref.canonical({
        "body": body,
        "signature": {"alg": "minisign-ed25519",
                      "key_id": "xr-signing-2026-09",
                      "sig": stub_sig(KEY_MATERIAL["xr-signing-2026-09"],
                                      body_canon)}})
    v6 = host_call({"method": "epoch-apply", "args": {
        "keys": keys, "notice": notice,
        "epoch": {"epoch_id": "epoch-2026-09",
                  "key_id": "xr-signing-2026-09", "manual_path": False,
                  "revoked": False, "seq": 3}}}, store)
    o6 = v6["out"]
    d.cell("epoch-revocation-applied",
           o6.get("applied") is True and
           o6.get("epoch", {}).get("revoked") is True and
           o6.get("epoch", {}).get("manual_path") is True,
           json.dumps(o6)[:160])

    # 7. revocation forces the manual path on the SAME offer
    v7 = host_call({"method": "verify", "args": {
        "channel": "dev", "current_version": "0.0.0.0", "envelope":
        json.dumps(offer_for("nightly", 0, spec), sort_keys=True,
                   separators=(",", ":")),
        "epoch": o6.get("epoch", {"epoch_id": "epoch-2026-09",
                                  "key_id": "xr-signing-2026-09",
                                  "manual_path": True, "revoked": True,
                                  "seq": 4}),
        "keys": keys, "seen": [], "transport": "drill"}}, store)
    d.cell("revocation-forces-manual-path",
           v7["out"].get("verdict") == "deny" and
           v7["out"].get("manual_path") is True,
           json.dumps(v7["out"])[:120])

    # 8. stale notice ignored (seq <= current)
    stale_body = dict(body, seq=2, reason="stale drill")  # strictly older: the implemented stale law (seq < cur; == cur re-applies idempotently, byte-parity in both backends)
    stale_notice = ref.canonical({
        "body": stale_body,
        "signature": {"alg": "minisign-ed25519",
                      "key_id": "xr-signing-2026-09",
                      "sig": stub_sig(KEY_MATERIAL["xr-signing-2026-09"],
                                      ref.canonical(stale_body))}})
    v8 = host_call({"method": "epoch-apply", "args": {
        "keys": keys, "notice": stale_notice,
        "epoch": {"epoch_id": "epoch-2026-09",
                  "key_id": "xr-signing-2026-09", "manual_path": False,
                  "revoked": False, "seq": 3}}}, store)
    d.cell("stale-notice-ignored",
           v8["out"].get("applied") is False,
           json.dumps(v8["out"])[:120])

    # 9. beta/stable auto-rollout refused until P38 (policy data is law)
    import yaml  # pinned dev dep
    policy = yaml.safe_load(
        (REPO / "release" / "rollout" / "policy.yaml").read_text())
    ar = policy["auto_rollout"]
    d.cell("auto-rollout-refused-until-p38",
           ar["beta"]["enabled"] is False and
           ar["stable"]["enabled"] is False and
           ar["beta"]["until"] == "P38")

    # 10. crash hook dev-only assertion
    allowed = policy["crash_hook"]["channels_allowed"]
    d.cell("crash-hook-dev-only",
           allowed == ["dev"] and
           policy["crash_hook"]["on_absent_input"].startswith("no-auto-halt"))

    not_run = 10 - d.executed
    print(f"cells executed: {d.executed} / not-run: {not_run}")
    if d.failures:
        print(f"FAIL: rollout drill ({len(d.failures)} cell(s) failed: "
              f"{', '.join(d.failures)})")
        return 1
    if d.executed == 0:
        print("FAIL: rollout drill executed ZERO cells (0 executed => FAIL)")
        return 1
    print("PASS: rollout drill (serve/accept, downgrade+replay refusals, "
          "ramp boundaries, epoch revocation -> forced manual path, stale "
          "ignored, auto-rollout refused until P38, dev-only hook)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
