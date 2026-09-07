#!/usr/bin/env python3
"""tools/xrctl_policy.py — `xrctl policy …` subcommand (Plan P6-T6).

The support-engineer surface for the policy resolver, driving BOTH
backends interchangeably:

  * fake — xr-core/fakes/policy_resolver.py (P5-frozen behavioral reference)
  * cpp  — xr-core/policy/tests/build/policy_host (the P6 C++ core, stdio
           façade speaking the same protocol)

Subcommands:
  policy resolve '<json>'   — resolve one request (default backend: fake)
  policy dump [--managed] [--json] [--store-dir DIR]
                             — labeled state: cache stats, store docs,
                               snapshot sizes, ledger rows; --json parity
  policy watch [--store-dir DIR]
                             — poll generation counters (documented
                               poll-mode; long-running IPC watch = P11+)
  policy snapshot-stats [--store-dir DIR]
                             — encode full + diff snapshots, report sizes
                               vs the 32 KB budget

`policy dump` output sections are labeled and byte-parity between --json
and the human format is enforced by tests (tools/tests/test_xrctl_policy.py).

Stdlib only. Exit: 0 ok · 1 error · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_OK, EXIT_ERR, EXIT_USAGE = 0, 1, 2

# Module-relative defaults (CWD-independent, mirroring cmd_call's repo logic).
_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAKES = str(_REPO_ROOT / ".." / "xr-core" / "fakes")
DEFAULT_HOST = str(_REPO_ROOT / ".." / "xr-core" / "policy" / "tests" / "build" / "policy_host")


def _load_fake(fakes_dir: Path):
    if str(fakes_dir) not in sys.path:
        sys.path.insert(0, str(fakes_dir))
    import importlib.util
    path = fakes_dir / "policy_resolver.py"
    spec = importlib.util.spec_from_file_location("xrctl_policy_fake", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cpp_host(host: Path, args: list[str], stdin: str | None = None) -> tuple[int, str]:
    r = subprocess.run([str(host), *args], input=stdin, capture_output=True, text=True)
    return r.returncode, r.stdout


def cmd_resolve(args: argparse.Namespace) -> int:
    try:
        payload: Any = json.loads(args.request_json)
    except json.JSONDecodeError as e:
        print(f"error: bad JSON request: {e}", file=sys.stderr)
        return EXIT_USAGE
    if args.backend == "fake":
        mod = _load_fake(Path(args.fakes))
        print(mod.canonical(mod.resolve(payload)))
        return EXIT_OK
    host = Path(args.host)
    if not host.is_file():
        print(f"error: cpp backend not built ({host}); run "
              f"`make -C xr-core/policy/tests build` (g++ required)", file=sys.stderr)
        return EXIT_ERR
    rc, out = _run_cpp_host(host, [], stdin=json.dumps(payload))
    print(out.rstrip("\n"))
    return EXIT_OK if rc == 0 else EXIT_ERR


def cmd_dump(args: argparse.Namespace) -> int:
    host = Path(args.host)
    if args.backend == "fake":
        # The fake is stateless: a reduced, honest dump (fixture identity set
        # + a sample resolve of every tier), clearly labeled.
        mod = _load_fake(Path(args.fakes))
        if args.json:
            tiers = {}
            for t in ("kStandard", "kShield", "kFortress"):
                req = {"identity": {"value": "xr:00000000-0000-4000-8000-000000000001"},
                       "origin": {"scheme": "https", "registrable_domain": "example.com"},
                       "request_class": "kNavigation", "trust_context": t}
                tiers[t] = mod.resolve(req)["ok"] if "ok" in mod.resolve(req) else None
            print(json.dumps({"backend": "fake", "stateless": True,
                              "fixture_identities": sorted(mod.KNOWN_IDENTITIES),
                              "tier_samples": tiers}, sort_keys=True,
                             separators=(",", ":")))
        else:
            print("== xr policy (fake backend — stateless) ==")
            print("fixture identities:")
            for i in sorted(mod.KNOWN_IDENTITIES):
                print(f"  {i}")
        return EXIT_OK
    if not host.is_file():
        print(f"error: cpp backend not built ({host})", file=sys.stderr)
        return EXIT_ERR
    argv = ["dump"] + (["--managed"] if args.managed else []) + ["--json" if args.json else "--human"]
    if args.store_dir:
        argv += ["--store-dir", args.store_dir]
    # policy_host dump uses --json for canonical; human is default.
    if not args.json:
        argv = [a for a in argv if a != "--human"]
    rc, out = _run_cpp_host(host, argv)
    print(out.rstrip("\n"))
    return EXIT_OK if rc == 0 else EXIT_ERR


def cmd_watch(args: argparse.Namespace) -> int:
    host = Path(args.host)
    if not host.is_file():
        print(f"error: cpp backend not built ({host})", file=sys.stderr)
        return EXIT_ERR
    argv = ["watch"] + (["--store-dir", args.store_dir] if args.store_dir else [])
    rc, out = _run_cpp_host(host, argv)
    print(out.rstrip("\n"))
    return EXIT_OK if rc == 0 else EXIT_ERR


def cmd_snapshot_stats(args: argparse.Namespace) -> int:
    host = Path(args.host)
    if not host.is_file():
        print(f"error: cpp backend not built ({host})", file=sys.stderr)
        return EXIT_ERR
    # Resolve a representative state through the host, then snapshot it.
    req = json.dumps({"identity": {"value": "xr:00000000-0000-4000-8000-000000000001"},
                      "origin": {"scheme": "https", "registrable_domain": "example.com"},
                      "request_class": "kNavigation"})
    _run_cpp_host(host, [], stdin=req)
    rc_full, full = _run_cpp_host(host, ["snapshot"])
    rc_diff, diff = _run_cpp_host(host, ["snapshot", "--diff"])
    if rc_full != 0 or rc_diff != 0:
        print("error: snapshot encoding failed", file=sys.stderr)
        return EXIT_ERR
    budget = 32 * 1024
    sizes = {"full_bytes": len(full.strip()), "diff_bytes": len(diff.strip()),
             "budget_bytes": budget}
    report = {"backend": "cpp", **sizes,
              "full_within_budget": sizes["full_bytes"] <= budget,
              "diff_within_budget": sizes["diff_bytes"] <= budget}
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print("== xr policy snapshot stats (cpp backend) ==")
        print(f"full snapshot:  {sizes['full_bytes']} bytes "
              f"({'within' if report['full_within_budget'] else 'OVER'} 32 KB budget)")
        print(f"diff snapshot:  {sizes['diff_bytes']} bytes "
              f"({'within' if report['diff_within_budget'] else 'OVER'} 32 KB budget)")
    return EXIT_OK if report["full_within_budget"] and report["diff_within_budget"] else EXIT_ERR


def build_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("policy", help="policy resolver surface (P6-T6)")
    p.add_argument("--backend", choices=["fake", "cpp"], default="fake",
                   help="fake = frozen Python reference; cpp = P6 C++ core")
    p.add_argument("--fakes", default=DEFAULT_FAKES)
    p.add_argument("--host", default=DEFAULT_HOST)
    sub2 = p.add_subparsers(dest="policy_cmd", required=True)

    r = sub2.add_parser("resolve", help="resolve one JSON request")
    r.add_argument("request_json")

    d = sub2.add_parser("dump", help="labeled state dump (support surface)")
    d.add_argument("--managed", action="store_true", help="include enterprise section")
    d.add_argument("--json", action="store_true")
    d.add_argument("--store-dir", default=None)

    w = sub2.add_parser("watch", help="generation counters (poll mode)")
    w.add_argument("--store-dir", default=None)

    s = sub2.add_parser("snapshot-stats", help="snapshot sizes vs 32 KB budget")
    s.add_argument("--json", action="store_true")
    s.add_argument("--store-dir", default=None)


def run(args: argparse.Namespace) -> int:
    handlers = {"resolve": cmd_resolve, "dump": cmd_dump, "watch": cmd_watch,
                "snapshot-stats": cmd_snapshot_stats}
    return handlers[args.policy_cmd](args)
