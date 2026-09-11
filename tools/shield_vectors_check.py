#!/usr/bin/env python3
"""tools/shield_vectors_check.py — golden-vector BYTE-PARITY across both
shield backends (P11-T2; the update_vectors_check.py pattern applied to
the shield surface).

For every case in docs/contracts/vectors/shield-v1.json this tool runs:
  * the compiled C++ host (xr-core/shield/tests/build/shield_host, built
    via its Makefile when absent — SKIP-visible without g++/make), and
  * the Python reference fake (xr-core/fakes/shield.py),
feeds the SAME canonical request frame (or `raw` frame verbatim) plus the
case's `flags` to both, and requires:
  * byte-identical stdout between the backends AND versus the vector's
    `expect` (canonical bytes),
  * identical exit codes, matching the pinned `exit` or the derivation
    rule (error kMalformedInput/kUnknownMethod => 1, else 0).

Exit: 0 pass · 1 drift · 2 usage · 77 skip (tool absent: g++/make).
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

VECTORS = "docs/contracts/vectors/shield-v1.json"
DEFAULT_XR_CORE = "../xr-core"


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def frame_for(case: dict) -> str:
    if "raw" in case:
        return case["raw"]
    return canonical({"args": case["args"], "method": case["method"]})


def run(cmd: list[str], frame: str) -> tuple[str, int]:
    r = subprocess.run(cmd, input=frame, capture_output=True, text=True,
                       timeout=60)
    return r.stdout.strip("\n"), r.returncode


def want_rc(case: dict) -> int:
    if "exit" in case:
        return int(case["exit"])
    expect = case["expect"]
    if isinstance(expect, dict) and "error" in expect and "ok" not in expect:
        return 1 if expect["error"] in ("kMalformedInput",
                                        "kUnknownMethod") else 0
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="shield-vectors-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else \
        (repo / DEFAULT_XR_CORE).resolve()

    vec_path = repo / VECTORS
    try:
        doc = json.loads(vec_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {vec_path}: {exc}")
        return 1
    cases = doc.get("cases") or []
    if not cases:
        print("FAIL: zero vector cases — a runner that runs nothing "
              "certifies nothing")
        return 1
    if len(cases) < 150:
        print(f"FAIL: {len(cases)} cases (<150 — the P11-T2 floor)")
        return 1

    host_bin = xr_core / "shield" / "tests" / "build" / "shield_host"
    if not host_bin.exists():
        mk = subprocess.run(["make", "-C", str(xr_core / "shield" / "tests"),
                             "build"], capture_output=True, text=True)
        if mk.returncode != 0 or not host_bin.exists():
            print("SKIP: SKIP (tool absent: g++/make) — needed for: building "
                  "shield_host for the C++ side of the byte-parity harness; "
                  "local hint: apt-get install g++ make (build-essential)")
            return 77
    fake = xr_core / "fakes" / "shield.py"
    if not fake.exists():
        print(f"FAIL: fake not found at {fake}")
        return 2

    drift = 0
    for case in cases:
        cid = case["id"]
        frame = frame_for(case)
        flags = shlex.split(case.get("flags", ""))
        want = canonical(case["expect"])
        rc_want = want_rc(case)
        h_out, h_rc = run([str(host_bin), *flags], frame)
        f_out, f_rc = run([sys.executable, str(fake), *flags], frame)
        if h_out != want or f_out != want or h_rc != rc_want or \
                f_rc != rc_want:
            drift += 1
            print(f"DRIFT {cid} (want rc={rc_want})\n"
                  f"  want: {want[:220]}\n"
                  f"  host(rc={h_rc}): {h_out[:220]}\n"
                  f"  fake(rc={f_rc}): {f_out[:220]}")
    if drift:
        print(f"FAIL: {drift}/{len(cases)} vector cases drifted")
        return 1
    print(f"PASS: {len(cases)} shield vectors byte-identical across "
          "shield_host (C++) and fakes/shield.py (Python)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
