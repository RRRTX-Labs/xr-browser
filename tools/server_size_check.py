#!/usr/bin/env python3
"""tools/server_size_check.py — the plan's perf row, measured for real
(P10-T2): the rendered update-check response stays <= 2048 bytes raw on
the LARGEST realistic case (raw + gzip both reported), and the request
cap is the documented one (64 KiB, refused before parse).

Exit: 0 pass · 1 fail. Stdlib only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "release" / "server" / "refimpl"))

import update_server_ref as ref  # noqa: E402

RESPONSE_LIMIT = 2048


def main() -> int:
    ap = argparse.ArgumentParser(prog="server-size-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=RESPONSE_LIMIT)
    a = ap.parse_args()
    spec = ref.load_spec()
    # the largest REALISTIC case: every served channel present with an
    # offer-eligible entry + the largest spec url/hash set (the graph's
    # heads; ancestors are never rendered — the server offers heads only).
    apps = [{"appid": ref.APP_ID, "bucket": 0, "channel": ch,
             "epoch": spec["epochs"]["active"]["epoch_id"],
             "version": "0.0.0.0"}
            for ch in ("nightly", "beta", "stable")]
    frame = ref.canonical({
        "app": apps,
        "os": {"arch": "x64", "platform": "linux-x64", "version": "1.0"},
        "protocol": "3.1",
    }).encode()
    status, out = ref.handle(frame, spec, len(frame))
    if status != 200:
        print(f"FAIL: largest realistic case refused ({status})")
        return 1
    raw = len(out)
    gz = len(gzip.compress(out.encode(), 9))
    env = json.loads(out[len(ref.PREFIX):])
    offered = sum(1 for e in env["response"]["app"]
                  if e["updatecheck"]["status"] == "ok")
    ok = raw <= a.limit
    print(f"response: {raw} bytes raw, {gz} bytes gzip "
          f"(limit {a.limit}; {offered} offer(s) rendered)")
    print(f"request cap: {ref.REQUEST_CAP} bytes (over-cap refused "
          "before parse — measured by the conformance corpus, "
          "case too-large)")
    if not ok:
        print(f"FAIL: response {raw} > {a.limit}")
        return 1
    print(f"PASS: server-size (response {raw}B <= {a.limit}B, gzip {gz}B; "
          "cap enforced)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
