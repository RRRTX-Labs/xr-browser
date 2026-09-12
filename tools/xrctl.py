#!/usr/bin/env python3
"""tools/xrctl.py — dev-only CLI to drive the xr.mojom fakes (T7).

DEV TOOL ONLY. Not a user-facing CLI, no UX claims, no TTY assumptions. It
resolves an interface name to its Python fake and forwards a JSON payload over
the documented stdio protocol (xr-core/fakes/README.md), printing the canonical
JSON result.

  xrctl.py call policy_resolver Resolve '{"identity":{"value":"xr:...-001"},...}'
  xrctl.py call route_manager LoseAllFailClosed '{}'
  xrctl.py list

Stdlib only. Exit: 0 ok · 1 error · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK, EXIT_ERR, EXIT_USAGE = 0, 1, 2

DEFAULT_FAKES = "../xr-core/fakes"

INTERFACES = {
    "policy_resolver": "PolicyResolver",
    "identity": "IdentityManager",
    "shield": "Shield",
    "route_manager": "RouteManager",
    "vault": "VaultService",
    "guard": "GuardLedger",
    "downloads": "DownloadSafety",
    "activity_log": "ActivityLog",
}


def _load(fakes_dir: Path, module: str):
    path = fakes_dir / f"{module}.py"
    if not path.exists():
        raise FileNotFoundError(str(path))
    if str(fakes_dir) not in sys.path:
        sys.path.insert(0, str(fakes_dir))
    spec = importlib.util.spec_from_file_location(f"xrctl_{module}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_call(args) -> int:
    fakes_dir = Path(args.fakes).resolve() if args.fakes else (Path(args.repo).resolve() / DEFAULT_FAKES).resolve()
    if args.interface not in INTERFACES:
        print(f"error: unknown interface {args.interface!r}", file=sys.stderr)
        return EXIT_USAGE
    try:
        payload: Any = json.loads(args.args_json)
    except json.JSONDecodeError as e:
        print(f"error: bad JSON args: {e}", file=sys.stderr)
        return EXIT_USAGE
    try:
        mod = _load(fakes_dir, args.interface)
    except FileNotFoundError as e:
        print(f"error: fake not found: {e}", file=sys.stderr)
        return EXIT_ERR

    if args.interface == "policy_resolver":
        # PolicyResolver takes Resolve args directly.
        result = mod.resolve(payload)
    else:
        result = mod.call(args.method, payload)
    if isinstance(result, tuple):
        # The shield fake (P11-T2) follows the house CLI shape and returns
        # (envelope, rc): the exit-code contract belongs to the HOST BINARY
        # layer (pinned by the golden vectors), while xrctl's contract is
        # the typed result envelope — unwrap it here. (P11-T5: this generic
        # path raised TypeError on the shield fake's required flag arg and
        # then leaked the raw tuple; both hosted-CI debts fixed here + a
        # flag default in the fake.)
        result = result[0]
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return EXIT_OK


def cmd_list(args) -> int:
    for k, v in INTERFACES.items():
        print(f"{k}\t{v}")
    return EXIT_OK


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="xrctl", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--fakes", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("call", help="drive a fake method")
    c.add_argument("interface")
    c.add_argument("method")
    c.add_argument("args_json")
    sub.add_parser("list", help="list interfaces")
    # P6-T6: the policy surface (fake + cpp backends).
    import xrctl_policy
    xrctl_policy.build_parser(sub)
    args = p.parse_args(argv)
    handlers = {"call": cmd_call, "list": cmd_list}
    if args.cmd == "policy":
        return xrctl_policy.run(args)
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
