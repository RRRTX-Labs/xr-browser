#!/usr/bin/env python3
"""tools/fuzz_fleet.py — the fuzz fleet runner (P9-T8).

Discovers the four C++ cores from build/fuzz/fleet.yaml (data, not code) and
runs each in-house seeded fuzzer under the timebox law: >=60 s in the gate,
>=600 s in evidence (XR_FUZZ_SECONDS), with a hard --min-iters floor — a lane
that executed nothing is a FAILURE (empty-run law). Collects
iters/seeds/violations per target.

The corpus dirs (build/fuzz/corpus/<target>/) hold REAL seed documents from
the frozen parity corpora + P5 fixtures. They are consumed by the CI-side
clang/libFuzzer entry points (build/fuzz/libfuzzer/, built only where clang
exists — never in this sandbox). The in-sandbox gate checks that every
corpus dir is NON-EMPTY (a seeded corpus is the libFuzzer lane's empty-run
law) and that each target's in-house fuzzer runs clean under the timebox.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage · 77 skip (tool absent: g++/make).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, \
    RunnerError, require_cases, skip_visible, stable_json  # noqa: E402

FLEET = "build/fuzz/fleet.yaml"


def load_fleet(repo: Path) -> dict:
    import yaml
    p = repo / FLEET
    if not p.exists():
        raise RunnerError(f"missing {FLEET}")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise RunnerError(f"{FLEET}: unsupported schema_version")
    return doc


def corpus_is_seeded(repo: Path, target: dict) -> bool:
    cdir = repo / target["corpus_dir"]
    return cdir.is_dir() and any(cdir.iterdir())


def run_target(repo: Path, target: dict, seconds: int,
               seed: int) -> dict:
    if target["runner"] == "python-tool":
        cmd = [sys.executable, str(repo / target["tool"]),
               "--timebox", str(seconds), "--seed", str(seed),
               "--min-iters", str(target.get("min_iters", 100))]
        env = dict(os.environ)
        cwd = repo
    else:
        # in-house fuzz binaries read their schema relative to their tests
        # dir (../../<core>/core/*.json); run from the Makefile dir, exactly
        # as `make -C <core>/tests test` does.
        cwd = (repo / target["runner_makefile"]).resolve()
        binary = (cwd / target["runner_binary"]).resolve()
        if not binary.exists():
            raise RunnerError(f"{target['id']}: binary missing at {binary} — "
                              f"run `make -C {target['runner_makefile']} "
                              f"test` first (g++ required)")
        cmd = [str(binary)]
        env = dict(os.environ, XR_FUZZ_SECONDS=str(seconds),
                   XR_FUZZ_SEED=str(seed))
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          cwd=cwd, timeout=seconds + 120)
    out = (proc.stdout or "") + (proc.stderr or "")
    return {"target": target["id"], "rc": proc.returncode, "output": out,
            "seconds": seconds, "seed": seed}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="fuzz_fleet", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--timebox", type=int, default=0,
                   help="seconds per target (default: fleet gate value or "
                        "XR_FUZZ_SECONDS)")
    p.add_argument("--seed", type=int, default=20260910)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()

    if shutil.which("g++") is None or shutil.which("make") is None:
        return skip_visible("fuzz_fleet",
                            "SKIP (tool absent: g++/make) — needed for: the "
                            "four in-house C++ fuzz targets; local hint: "
                            "apt-get install g++ make (build-essential)")

    fleet = load_fleet(repo)
    seconds = args.timebox or int(os.environ.get("XR_FUZZ_SECONDS",
                                  fleet.get("timebox_gate_s", 60)))
    targets = list(fleet["targets"])
    if not targets:
        print("FAIL: fuzz_fleet: zero targets (empty-run law)")
        return EXIT_FAIL

    # a corpus dir that was never seeded is the libFuzzer lane's empty-run
    for t in targets:
        if not corpus_is_seeded(repo, t):
            print(f"FAIL: {t['id']}: corpus dir {t['corpus_dir']} is empty "
                  f"(a libFuzzer lane with no seeds certifies nothing)")
            return EXIT_FAIL

    results: list[dict] = []
    for t in targets:
        try:
            results.append(run_target(repo, t, seconds, args.seed))
        except RunnerError as exc:
            print(f"FAIL: {exc}")
            return EXIT_FAIL
        except subprocess.TimeoutExpired:
            print(f"FAIL: {t['id']} timed out")
            return EXIT_FAIL

    for r in results:
        if r["rc"] != 0:
            print(f"FAIL: {r['target']} rc={r['rc']}")
            tail = r["output"].strip().splitlines()[-4:]
            for line in tail:
                print("  " + line[:160])
            return EXIT_FAIL
    require_cases(len(results), "fuzz_fleet")
    if args.json:
        print(stable_json({"tool": "fuzz_fleet", "targets": len(results),
                           "seconds": seconds, "status": "pass"}))
    else:
        print(f"fuzz_fleet: {len(results)} target(s) x {seconds}s clean "
              f"(corpus dirs seeded)")
        print("PASS: fuzz_fleet")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
