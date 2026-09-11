#!/usr/bin/env python3
"""tools/vectors_check.py — golden-vector fake-parity check (P5-T6).

Ground truth = the golden vectors under docs/contracts/vectors/. This tool
drives the xr-core Python fakes and asserts their output equals each vector's
`expected` value BYTE-FOR-BYTE in canonical form (sorted keys, no timestamps).
A drift in either the fake or a vector fails with the offending vector id.

Covered:
  policy-resolver-v1.json  -> xr-core/fakes/policy_resolver.py  (Resolve)
  route-manager-v1.json    -> xr-core/fakes/route_manager.py    (call)

Also emits the sha256 of each canonicalized vector file (byte-stability anchor
for evidence).

Stdlib only. Exit: 0 pass · 1 drift/missing · 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

VECTORS_DIR = "docs/contracts/vectors"
DEFAULT_FAKES = "../xr-core/fakes"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _load_fake(fakes_dir: Path, module: str):
    path = fakes_dir / f"{module}.py"
    if not path.exists():
        raise FileNotFoundError(str(path))
    # fakes import a sibling `_base`; ensure the dir is importable.
    if str(fakes_dir) not in sys.path:
        sys.path.insert(0, str(fakes_dir))
    spec = importlib.util.spec_from_file_location(f"xrfake_{module}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_policy(mod, vec: dict[str, Any]) -> Any:
    return mod.resolve(vec["request"])


def _run_route(mod, vec: dict[str, Any]) -> Any:
    return mod.call(vec["method"], vec["args"])


def _run_update(mod, vec: dict[str, Any]) -> Any:
    """update-v1 cases carry method/args/expect (not name/args/expected) and
    verify expectations pin a SUBSET of the output (the host adds
    seen_size/manifest_id/verifier), so project the fake result through the
    same expectation semantics the C++ golden test uses."""
    got = mod.call(vec["method"], vec["args"])
    want = vec["expect"]
    if not isinstance(got, dict):
        return got
    if "error" in want:
        # project exactly the keys the expectation pins (error[/reason/detail])
        return {k: got.get(k) for k in want}
    if "verdict" in want:
        return {"verdict": got.get("verdict"), "reason": got.get("reason"),
                "manual_path": got.get("manual_path")}
    return got


RUNNERS = {
    "policy-resolver-v1.json": ("policy_resolver", _run_policy),
    "route-manager-v1.json": ("route_manager", _run_route),
    "update-v1.json": ("update", _run_update),
}


def check(repo: Path, fakes_dir: Path) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    info: dict[str, Any] = {"tool": "vectors_check", "files": {}}
    vdir = repo / VECTORS_DIR
    for fname, (module, runner) in RUNNERS.items():
        fpath = vdir / fname
        if not fpath.exists():
            failures.append(f"{fname}: vector file missing")
            continue
        raw = fpath.read_text()
        doc = json.loads(raw)
        # byte-stability anchor: hash the re-canonicalized file bytes.
        digest = hashlib.sha256(raw.encode()).hexdigest()
        mod = _load_fake(fakes_dir, module)
        n_ok = 0
        vectors = doc.get("vectors") or doc.get("cases") or []
        for vec in vectors:
            got = runner(mod, vec)
            want = vec.get("expected", vec.get("expect"))
            if canonical(got) != canonical(want):
                failures.append(
                    f"{fname}:{vec.get('name', vec.get('id'))}: fake output != vector\n"
                    f"    want: {canonical(want)}\n    got:  {canonical(got)}"
                )
            else:
                n_ok += 1
        info["files"][fname] = {
            "count": len(vectors),
            "passed": n_ok,
            "sha256": digest,
        }
    return failures, info


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="vectors_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--fakes", default=None,
                   help="path to xr-core/fakes (default: <repo>/../xr-core/fakes)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    fakes_dir = Path(args.fakes).resolve() if args.fakes else (repo / DEFAULT_FAKES).resolve()
    if not fakes_dir.exists():
        print(f"FAIL: fakes dir not found: {fakes_dir}", file=sys.stderr)
        return EXIT_FAIL
    try:
        failures, info = check(repo, fakes_dir)
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return EXIT_FAIL

    if args.json:
        out = dict(info)
        out["status"] = "pass" if not failures else "fail"
        if failures:
            out["failures"] = failures
        print(json.dumps(out, indent=2))
    else:
        for f in failures:
            print(f"FAIL: {f}")
        for fname, d in info["files"].items():
            print(f"  {fname}: {d['passed']}/{d['count']} ok  sha256={d['sha256'][:16]}…")
        print(f"{'PASS' if not failures else 'FAIL'}: vectors_check")
    return EXIT_PASS if not failures else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
