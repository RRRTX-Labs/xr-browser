#!/usr/bin/env python3
"""tools/permission_host_parity.py — permissions host vs fake byte parity (P15-CLOSE C2).

Replays, against the COMPILED permissions_host and fakes/permissions.py:
  * every case in tools/parity/corpus-permissions.json (stdin form);
  * every case in xr-core/fakes/fixtures/permission-v1.json (argv form);
  * one store-dir sequence (grant -> sweep -> view with a persisted clock),
    run in two fresh `mktemp -d` directories, comparing stdout AND the bytes
    left on disk.
All at the corpus' fixed --as-of (the fake reads no clock; the host's own clock
path is proven by permissions/tests/test_kill9.cc). Any difference prints
`DIVERGE <case-id>` and fails. Zero cases replayed is a failure (zero-case law).

Usage: permission_host_parity.py [--xr-core PATH] [--host BIN] [--fake PY] [--json]
Exit: 0 pass · 1 fail · 2 usage. Stdlib only; builds the host out of tree
(work/scratch/permissions-host-build) when --host is not given.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "tools" / "parity" / "corpus-permissions.json"
BUILD = REPO / "work" / "scratch" / "permissions-host-build"


def build_host(xr_core: Path) -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["make", "-C", str(xr_core / "permissions" / "tests"),
                        f"BUILD={BUILD}", str(BUILD / "permissions_host")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"FAIL: cannot build permissions_host:\n{r.stderr[-600:]}")
    return BUILD / "permissions_host"


def run(argv: list[str], stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout


def snapshot(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default=str(REPO.parent / "xr-core"))
    ap.add_argument("--host", default=None, help="a built permissions_host")
    ap.add_argument("--fake", default=None, help="fake path (default: xr-core/fakes/permissions.py)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    xr_core = Path(a.xr_core).resolve()
    fake = Path(a.fake) if a.fake else xr_core / "fakes" / "permissions.py"
    fixture = xr_core / "fakes" / "fixtures" / "permission-v1.json"
    if not fake.is_file() or not fixture.is_file() or not CORPUS.is_file():
        print(f"usage error: missing fake/fixture/corpus ({fake}, {fixture}, {CORPUS})",
              file=sys.stderr)
        return 2
    if shutil.which("g++") is None and a.host is None:
        print("usage error: g++ absent and no --host given", file=sys.stderr)
        return 2
    host = Path(a.host) if a.host else build_host(xr_core)
    corpus = json.loads(CORPUS.read_text("utf-8"))
    fix = json.loads(fixture.read_text("utf-8"))
    as_of = str(corpus["as_of"])
    H, F = [str(host), "--as-of", as_of], [sys.executable, str(fake), "--as-of", as_of]
    diverged: list[str] = []
    replayed = 0

    for c in corpus["cases"]:
        req = json.dumps({"method": c["method"], "args": c.get("args", {})},
                         separators=(",", ":"))
        h, f = run(H, req), run(F, req)
        want = 0 if c.get("expect", "ok") == "ok" else 1
        replayed += 1
        if h != f or h[0] != want:
            diverged.append(c["id"])
    for c in fix["cases"]:
        argv = [c["method"], json.dumps(c["args"], separators=(",", ":"))]
        h, f = run(H + argv), run(F + argv)
        replayed += 1
        bad = h != f
        if "expect_error" in c:
            out = json.loads(h[1]) if h[1].strip() else {}
            bad = bad or out.get("error") != c["expect_error"]
            if "expect_detail" in c:
                bad = bad or out.get("detail") != c["expect_detail"]
        if bad:
            diverged.append(c["name"])

    seq = [("grant", {"identity": "xr:a", "domain": "example.com", "capability": "camera",
                      "scope": "7d"}, int(as_of) - 7 * 86400000),
           ("grant", {"identity": "xr:a", "domain": "example.org", "capability": "camera",
                      "scope": "session", "session_id": "s1"}, int(as_of)),
           ("sweep", {"session_id": "s2"}, int(as_of) - 86400000),   # clock rolled back
           ("view", {}, int(as_of))]
    with tempfile.TemporaryDirectory(prefix="p15c-parity-") as td:
        dh = Path(tempfile.mkdtemp(dir=td))
        df = Path(tempfile.mkdtemp(dir=td))
        for i, (m, args, t) in enumerate(seq):
            argv = ["--as-of", str(t), m, json.dumps(args, separators=(",", ":"))]
            h = run([str(host), "--store-dir", str(dh)] + argv)
            f = run([sys.executable, str(fake), "--store-dir", str(df)] + argv)
            replayed += 1
            if h != f or h[0] != 0 or snapshot(dh) != snapshot(df):
                diverged.append(f"store-dir-seq-{i}-{m}")

    if a.json:
        print(json.dumps({"tool": "permission_host_parity", "replayed": replayed,
                          "diverged": diverged}, sort_keys=True))
    for d in diverged:
        print(f"DIVERGE {d}")
    if replayed == 0:
        print("FAIL: permission-host-parity replayed zero cases (zero-case law)")
        return 1
    if diverged:
        print(f"FAIL: permission-host-parity ({len(diverged)} of {replayed} case(s) diverged)")
        return 1
    print(f"PASS: permission-host-parity ({replayed} case(s) byte-identical host vs fake, "
          f"incl. a store-dir sequence with a rolled-back clock)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
