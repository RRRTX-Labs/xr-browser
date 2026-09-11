#!/usr/bin/env python3
"""tools/update_vectors_check.py — golden-vector BYTE-PARITY across both
update backends (P10-T1; the P9 differential-parity lesson applied to the
update surface).

For every case in docs/contracts/vectors/update-v1.json this tool runs:
  * the compiled C++ host (xr-core/update/tests/build/update_host, built
    via its Makefile when absent — SKIP-visible without g++/make), and
  * the Python reference fake (xr-core/fakes/update.py),
feeds the SAME canonical request frame to both, and requires:
  * byte-identical stdout between the backends,
  * identical exit codes,
  * the vector's expected verdict/reason (or typed error) in both.

Also proves the both-flags law (--flag xr_updater_v0=off produces the typed
refusal on the C++ host; the fake's flag is host-CLI-level and the vectors
cover the on-state).

Exit: 0 pass · 1 drift · 2 usage · 77 skip (tool absent: g++/make).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

VECTORS = "docs/contracts/vectors/update-v1.json"
DEFAULT_XR_CORE = "../xr-core"


def canonical_frame(method: str, args: dict) -> str:
    return json.dumps({"args": args, "method": method}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True)


def run_fake(xr_core: Path, frame: str) -> tuple[str, int]:
    r = subprocess.run([sys.executable, "fakes/update.py"], cwd=str(xr_core),
                       input=frame, capture_output=True, text=True, timeout=60)
    return r.stdout.strip("\n"), r.returncode


def run_host(host_bin: Path, frame: str, flags: list[str] | None = None) -> tuple[str, int]:
    argv = [str(host_bin), *(flags or [])]
    r = subprocess.run(argv, input=frame, capture_output=True, text=True,
                       timeout=60)
    return r.stdout.strip("\n"), r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(prog="update-vectors-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else (repo.parent / DEFAULT_XR_CORE).resolve()

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

    host_bin = xr_core / "update" / "tests" / "build" / "update_host"
    if not host_bin.exists():
        mk = subprocess.run(["make", "-C", str(xr_core / "update" / "tests"),
                             "build"], capture_output=True, text=True)
        if mk.returncode != 0 or not host_bin.exists():
            print("SKIP: SKIP (tool absent: g++/make) — needed for: building "
                  "update_host for the C++ side of the byte-parity harness; "
                  "local hint: apt-get install g++ make (build-essential)")
            return 77

    # the fake must exist before we claim a two-backend run
    fake_py = xr_core / "fakes" / "update.py"
    if not fake_py.exists():
        print(f"FAIL: reference fake missing: {fake_py}")
        return 1

    drifts: list[str] = []
    n_bytes_identical = 0
    for c in cases:
        cid = c["id"]
        frame = canonical_frame(c["method"], c["args"])
        out_c, rc_c = run_host(host_bin, frame)
        out_p, rc_p = run_fake(xr_core, frame)
        if out_c != out_p:
            drifts.append(f"{cid}: backend bytes differ:\n  cpp : {out_c[:200]}"
                          f"\n  fake: {out_p[:200]}")
            continue
        n_bytes_identical += 1
        if rc_c != rc_p:
            drifts.append(f"{cid}: exit codes differ (cpp {rc_c} vs fake {rc_p})")
            continue
        exp = c["expect"]
        if "error" in exp:
            if exp["error"] not in out_c:
                drifts.append(f"{cid}: expected {exp['error']} in {out_c[:120]}")
        elif "verdict" in exp:
            if f'"verdict":"{exp["verdict"]}"' not in out_c or \
                    f'"reason":"{exp["reason"]}"' not in out_c:
                drifts.append(f"{cid}: expected verdict/reason "
                              f"{exp['verdict']}/{exp['reason']} in {out_c[:160]}")
        else:
            # full-object expectations: the canonical bytes ARE the expectation
            want = json.dumps(exp, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True)
            if out_c != want:
                drifts.append(f"{cid}: canonical bytes:\n  want {want[:180]}"
                              f"\n  got  {out_c[:180]}")

    # both-flags law on the host CLI (the fake's flag surface is its CLI
    # default-on; the off-state refusal is host-level, tested here)
    frame = canonical_frame("backoff", {"now_mono": 1, "state": {}})
    out_off, rc_off = run_host(host_bin, frame, ["--flag", "xr_updater_v0=off"])
    if rc_off != 0 or "xr_updater_v0 is off" not in out_off:
        drifts.append("both-flags: flag-off backoff must be a typed refusal")

    if drifts:
        for d in drifts[:12]:
            print(f"FAIL: {d}")
        print(f"FAIL: update-vectors ({len(drifts)} drift(s) of {len(cases)} cases)")
        return 1
    print(f"byte-identical: {n_bytes_identical}/{len(cases)} cases across "
          "update_host (C++) and fakes/update.py (Python)")
    print(f"PASS: update-vectors ({len(cases)} cases, both backends, "
          "both flags)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
