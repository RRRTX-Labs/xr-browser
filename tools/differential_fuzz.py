#!/usr/bin/env python3
"""tools/differential_fuzz.py — the byte-differential oracle (P9-T0-a).

The anti-drift machine P9 exists to build. For each stdio-JSON host pair
(themes/settings/commands/shield), it generates a SEEDED, DETERMINISTIC
stream of
requests, runs the compiled C++ host AND the Python reference fake on the
SAME request, and fails on ANY byte difference in (exit code, stdout) — not
just a verdict difference. A difference here is a contract breach of the
"byte-identical over the whole surface" law, exactly the class T0-a found on
the theme import path.

Generic over the four {method,args} stdio pairs (the shield pair joined
at P11-T2/DoD-3; its generators + configs live in differential_fuzz_kit.py
under the touched-file size law). The policy host is a
subcommand host (resolve/dump/watch/snapshot) with no {method,args} protocol
table, so it is NOT fuzzed here — its parity is enforced by
tools/vectors_check.py + tools/mutation_test.py (recorded in the manifest,
not silently dropped).

Input-domain scope (recorded, not hidden): the oracle generates WELL-FORMED
JSON frames — the surface the host EVALUATES (schema/contrast/duplicate/
oversize/typed refusals and every state method), where T0-a's defect lived
and where the byte-parity law governs the response. The strict-JSON
*parse-rejection* layer is excluded from byte-comparison: the two backends
are independent parsers whose error phrasing differs ("invalid number at
offset 0" vs json's "Expecting value …") — the same carve-out the P8 parity
suite already records for malformed frames (exit code + error code only).
That layer is covered by the C++ parser suite + the corpus's code-compared
parse cases. docs/state/limitations.md carries the §1.13 row.

The zero-case law: a run that executed fewer than --min-iters requests is a
FAILURE, never a pass. g++/make absent (no C++ host) => exit 77 SKIP with the
visible reason (skip-policy law).

Exit: 0 pass · 1 fail (divergence / min-iters) · 2 usage · 77 skip.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from differential_fuzz_kit import pair_configs as _pair_configs  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77

HERE = Path(__file__).resolve().parent

def _run_backend(argv: list[str], req: str, cwd: Path,
                 timeout: float) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, input=req, capture_output=True, text=True,
                              cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, "<timeout>"
    except OSError as exc:
        return -1, f"<exec error: {exc}>"
    return proc.returncode, proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repo", default=".", help="xr-browser root (default: cwd)")
    ap.add_argument("--pairs", default="themes,settings,commands,shield",
                    help="comma-separated pairs to fuzz")
    ap.add_argument("--fake-dir", default="",
                    help="fakes directory override (canary tests mutate a copy)")
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--iters", type=int, default=0,
                    help="exact request count (0 = driven by --timebox)")
    ap.add_argument("--timebox", type=float, default=120.0,
                    help="wall-clock seconds (default 120; evidence uses 600)")
    ap.add_argument("--min-iters", type=int, default=100,
                    help="fewer executed requests than this => FAIL (zero-case law)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    xr_core = (repo.parent / "xr-core").resolve()
    if not xr_core.is_dir():
        print("error: no ../xr-core sibling checkout", file=sys.stderr)
        return EXIT_USAGE

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    if not pairs:
        print("error: --pairs is empty (zero-case law)", file=sys.stderr)
        return EXIT_USAGE

    import shutil
    if shutil.which("g++") is None or shutil.which("make") is None:
        print("SKIP: SKIP (tool absent: g++/make) — needed for: the "
              "byte-differential oracle (compiled C++ host vs Python fake); "
              "local hint: apt-get install g++ make (build-essential)")
        return EXIT_SKIP

    # host data for generators
    try:
        tokens = json.loads(
            (xr_core / "ui/themes/tokens.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        tokens = {"themes": {}, "tokens": {}}
    try:
        schema = json.loads((xr_core / "settings/core/settings_schema_v1.json")
                            .read_text(encoding="utf-8"))
        s_keys = sorted(s["key"] for s in schema.get("settings", [])
                        if isinstance(s, dict) and "key" in s)
    except (OSError, json.JSONDecodeError):
        s_keys = []
    try:
        roster = json.loads((xr_core / "commands/core/roster_v1.json")
                            .read_text(encoding="utf-8"))
        c_ids = sorted(c.get("descriptor", {}).get("id", "")
                       for c in roster.get("commands", [])
                       if isinstance(c, dict))
    except (OSError, json.JSONDecodeError):
        c_ids = []

    fake_dir = Path(args.fake_dir) if args.fake_dir else (xr_core / "fakes")
    configs = _pair_configs(xr_core, fake_dir)
    gen_data: dict[str, Any] = {"themes": tokens, "settings": s_keys,
                                "commands": c_ids}
    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.timebox
    executed = 0
    divergences: list[dict[str, Any]] = []
    per_pair = {p: {"executed": 0, "divergences": 0} for p in pairs}

    for pid in pairs:
        cfg = configs.get(pid)
        if cfg is None:
            print(f"error: unknown pair {pid!r}", file=sys.stderr)
            return EXIT_USAGE
        host_argv = cfg["host"]
        if not Path(host_argv[0]).is_file():
            # build the host first (g++ present; visible failure if it errors)
            r = subprocess.run(cfg["make"], cwd=xr_core, capture_output=True,
                               text=True)
            if r.returncode != 0 or not Path(host_argv[0]).is_file():
                print(f"SKIP: SKIP (build failed for {pid}) — needed for: the "
                      f"differential oracle; {r.stderr.strip()[-200:]}")
                continue

    if args.iters > 0:
        total = args.iters
    else:
        total = None  # timebox-driven

    while total is None or executed < total:
        if time.monotonic() > deadline:
            break
        pid = rng.choice(pairs)
        cfg = configs[pid]
        if not Path(cfg["host"][0]).is_file():
            continue  # pair built-skipped above
        req_obj = cfg["gen"](rng, gen_data.get(pid))
        req = json.dumps(req_obj, separators=(",", ":"))
        rc_h, out_h = _run_backend(cfg["host"], req, xr_core, 10.0)
        rc_f, out_f = _run_backend(cfg["fake"], req, xr_core, 10.0)
        executed += 1
        per_pair[pid]["executed"] += 1
        if rc_h != rc_f or out_h != out_f:
            per_pair[pid]["divergences"] += 1
            divergences.append({"pair": pid, "request": req,
                                "cpp_rc": rc_h, "cpp_out": out_h,
                                "fake_rc": rc_f, "fake_out": out_f})
            if len(divergences) >= 20:
                break  # report the first 20; the run already failed

    n_div = len(divergences)
    result = {
        "tool": "differential_fuzz",
        "seed": args.seed,
        "executed": executed,
        "divergences": n_div,
        "pairs": per_pair,
        "timebox": args.timebox,
    }
    if args.json:
        print(json.dumps({**result, "status": "pass" if n_div == 0 else "fail"},
                         indent=2))
    else:
        for pid, st in per_pair.items():
            print(f"pair {pid}: {st['executed']} requests, "
                  f"{st['divergences']} divergences")
        for d in divergences[:5]:
            print(f"DIVERGENCE {d['pair']}: rc cpp={d['cpp_rc']} "
                  f"fake={d['fake_rc']}")
            print(f"  request: {d['request'][:160]}")
            print(f"  cpp:  {d['cpp_out'][:200]}")
            print(f"  fake: {d['fake_out'][:200]}")
        print(f"{'PASS' if n_div == 0 else 'FAIL'}: differential_fuzz "
              f"({executed} requests, {n_div} divergences)")

    if executed < args.min_iters:
        print(f"FAIL: differential_fuzz executed {executed} < min-iters "
              f"{args.min_iters} (zero-case law)")
        return EXIT_FAIL
    return EXIT_PASS if n_div == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
