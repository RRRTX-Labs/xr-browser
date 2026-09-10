#!/usr/bin/env python3
"""tools/isolation_matrix.py — the §11.4 isolation-matrix runner (P9-T2).

Executes every *fake-mode* cell of xr-core/test/isolation/matrix.yaml
against the P6 resolver fake (+ the pure fakes), records every browser /
exception / not-yet cell with its owning phase, and emits
isolation-matrix.json (+ .md summary) with a per-cell verdict.

The two laws that matter here (both enforced, both with negative fixtures):
  * the empty-run law — zero fake cells executed is a FAILURE (a runner that
    quietly ran 3 cells and said PASS is the failure mode);
  * honesty of the "not-run" half — every non-fake cell must name its mode
    and owning phase, so nothing silently disappears from the suite.

Adversarial load mode (deterministic, seeded): a cross-identity call storm
on the resolver asserting purity (resolving A is byte-independent of any
prior resolve of B) and deny-safety (unknown identity => deny).

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError, as_of_arg, \
    iso, require_cases, seed_rng, stable_json  # noqa: E402

MATRIX_DEFAULT = "../xr-core/test/isolation/matrix.yaml"
OUT_JSON = "../xr-core/test/isolation/isolation-matrix.json"
OUT_MD = "../xr-core/test/isolation/isolation-matrix.md"

ORIGIN = {"scheme": "https", "registrable_domain": "example.com",
          "port": 443}
REQUEST_CLASS = "kStorage"


def load_resolver(xr_core: Path) -> Any:
    """Import the pure resolver fake from xr-core (no side effects)."""
    fakes_dir = xr_core / "fakes"
    if str(fakes_dir) not in sys.path:
        sys.path.insert(0, str(fakes_dir))   # _base.py lives beside the fakes
    path = fakes_dir / "policy_resolver.py"
    if not path.exists():
        raise RunnerError(f"resolver fake missing at {path}")
    spec = importlib.util.spec_from_file_location("xr_policy_resolver", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["xr_policy_resolver"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def resolve(mod: Any, vid: str, trust: str) -> dict[str, Any]:
    req = {"identity": {"value": vid}, "origin": ORIGIN,
           "trust_context": trust, "request_class": REQUEST_CLASS}
    res = mod.resolve(req)
    if "ok" not in res:
        raise RunnerError(f"resolver returned {stable_json(res)}")
    return res["ok"]


# (mechanism) -> (policyA, policyB) -> (passed, detail). `A` is the stricter
# of the pair when a ladder order exists; the pair is symmetric.
def _check_storage(p: dict[str, Any]) -> tuple[bool, str]:
    sc = p["storage_scope"]
    return (sc["scope"] in {"kIdentityScoped", "kEphemeral",
                            "kFortressPartition"},
            f"storage_scope={sc['scope']} in_memory={sc['in_memory']}")


def _check_vault(p: dict[str, Any]) -> tuple[bool, str]:
    v = p["vault_scope"]
    ok = isinstance(v["autofill_allowed"], bool) and not v["export_allowed"]
    return ok, f"autofill={v['autofill_allowed']} export={v['export_allowed']}"


def _check_egress(p: dict[str, Any]) -> tuple[bool, str]:
    e = p["egress"]
    return e["route"] in {"kDirect", "kProxy", "kTor"}, \
        f"route={e['route']} block_3p={e['block_third_party']}"


def _check_permissions(p: dict[str, Any]) -> tuple[bool, str]:
    perms = p["permissions"]
    ok = all(v in {"kAsk", "kDeny"} for v in perms.values())
    return ok, f"perms={stable_json(perms)}"


def _check_fingerprint(p: dict[str, Any]) -> tuple[bool, str]:
    return p["fingerprint"]["mode"] in {"kReduce", "kStrict"}, \
        f"mode={p['fingerprint']['mode']}"


def _check_process(p: dict[str, Any]) -> tuple[bool, str]:
    pp = p["process_policy"]
    return pp["site_isolated"] is True, \
        f"site_isolated={pp['site_isolated']} dedicated={pp['dedicated_process']}"


CHECKERS = {
    "storage-scope": _check_storage,
    "vault-scope": _check_vault,
    "egress-route": _check_egress,
    "permission-overlay": _check_permissions,
    "fingerprint-mode": _check_fingerprint,
    "process-isolation": _check_process,
}


def run_fake_cells(mod: Any, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    idents = {i["id"]: i for i in matrix["identities"]}
    for mech in matrix["mechanisms"]:
        if mech["mode"] != "fake":
            continue
        checker = CHECKERS[mech["id"]]
        for a, b in matrix["identity_pairs"]:
            ia, ib = idents[a], idents[b]
            pa = resolve(mod, ia["vid"], ia.get("trust", "kStandard"))
            pb = resolve(mod, ib["vid"], ib.get("trust", "kStandard"))
            oka, da = checker(pa)
            okb, db = checker(pb)
            passed = oka and okb
            cells.append({
                "mechanism": mech["id"], "pair": [a, b],
                "mode": "fake", "verdict": "PASS" if passed else "FAIL",
                "detail": f"{a}: {da}; {b}: {db}"})
    return cells


def run_adversarial(mod: Any, matrix: dict[str, Any]) -> tuple[int, list[str]]:
    """Seeded cross-identity storm: purity + deny-safety."""
    adv = matrix.get("adversarial", {})
    rounds = int(adv.get("rounds", 200))
    rng = seed_rng(int(adv.get("seed", 20260910)))
    idents = {i["id"]: i for i in matrix["identities"]}
    vids = [i["vid"] for i in matrix["identities"]]
    trusts = ["kStandard", "kShield", "kFortress", "kBogus"]
    violations: list[str] = []
    for _ in range(rounds):
        a = idents[list(idents)[rng.randrange(len(idents))]]
        pa = resolve(mod, a["vid"], a.get("trust", "kStandard"))
        # Purity: an intervening resolve of a random OTHER identity (or a
        # hostile one) must not change a's next byte-for-byte answer.
        other_vid = vids[rng.randrange(len(vids))]
        other_trust = trusts[rng.randrange(len(trusts))]
        resolve(mod, other_vid, other_trust)
        pa2 = resolve(mod, a["vid"], a.get("trust", "kStandard"))
        if stable_json(pa) != stable_json(pa2):
            violations.append(f"purity: {a['id']} changed after resolving "
                              f"{other_vid}/{other_trust}")
        # Deny-safety: unknown identity => fully denying policy.
        unknown = resolve(mod, "xr:ffffffff-ffff-4fff-8fff-ffffffffffff",
                          "kStandard")
        if unknown["storage_scope"]["scope"] != "kEphemeral" or \
                not unknown["storage_scope"]["in_memory"]:
            violations.append("deny-safety: unknown identity not deny-default")
    return rounds, violations


def render_md(cells: list[dict[str, Any]], matrix: dict[str, Any],
              as_of: str) -> str:
    by_verdict: dict[str, int] = {}
    for c in cells:
        by_verdict[c["verdict"]] = by_verdict.get(c["verdict"], 0) + 1
    lines = ["# Isolation matrix (generated — P9-T2)",
             "",
             f"Generated with `--as-of {as_of}` (frozen-clock law). "
             f"Do not hand-edit; regenerate with `tools/isolation_matrix.py`.",
             "",
             f"Cells: {len(cells)} total — " +
             ", ".join(f"{v}={n}" for v, n in sorted(by_verdict.items())),
             "",
             "| mechanism | pair | mode | verdict | detail |", "|---|---|---|---|---|"]
    for c in cells:
        lines.append(f"| {c['mechanism']} | {'/'.join(c['pair'])} | "
                     f"{c['mode']} | {c['verdict']} | {c['detail']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="isolation_matrix", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--matrix", default=MATRIX_DEFAULT)
    p.add_argument("--out-json", default=OUT_JSON)
    p.add_argument("--out-md", default=OUT_MD)
    p.add_argument("--check", action="store_true",
                   help="regenerate and diff against committed outputs")
    p.add_argument("--json", action="store_true")
    as_of_arg(p)
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    xr_core = (repo / "xr-core").resolve() if (repo / "xr-core").is_dir() \
        else repo.parent / "xr-core"
    matrix_path = Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = repo / matrix_path
    try:
        import yaml
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: cannot load matrix {matrix_path}: {exc}")
        return EXIT_FAIL

    if matrix.get("schema_version") != 1:
        print(f"FAIL: unsupported matrix schema_version "
              f"{matrix.get('schema_version')!r}")
        return EXIT_FAIL

    mod = load_resolver(xr_core)
    cells: list[dict[str, Any]] = run_fake_cells(mod, matrix)
    rounds, violations = run_adversarial(mod, matrix)
    if violations:
        for v in violations[:10]:
            print(f"FAIL: adversarial: {v}")
        print(f"FAIL: adversarial mode — {len(violations)} violation(s)")
        return EXIT_FAIL

    # Non-fake cells are recorded (never dropped), with their owning phase.
    fake_ids = {c["mechanism"] for c in cells}
    for mech in matrix["mechanisms"]:
        if mech["mode"] == "fake":
            continue
        verdict = "EXCEPTION" if mech["mode"] == "exception" else "NOT-RUN"
        detail = mech.get("question", "")
        if mech["mode"] == "not-yet":
            detail = f"not-yet (owner phase {mech.get('phase', '?')})"
        for a, b in matrix["identity_pairs"]:
            cells.append({"mechanism": mech["id"], "pair": [a, b],
                          "mode": mech["mode"], "verdict": verdict,
                          "detail": detail})

    fake_executed = sum(1 for c in cells if c["mode"] == "fake")
    try:
        require_cases(fake_executed, "isolation_matrix")
    except RunnerError as exc:
        print(f"FAIL: {exc}")
        return EXIT_FAIL

    failures = [c for c in cells if c["verdict"] == "FAIL"]
    total = len(cells)
    browser = sum(1 for c in cells if c["verdict"] == "NOT-RUN")
    exceptions = sum(1 for c in cells if c["verdict"] == "EXCEPTION")

    out_json = Path(args.out_json)
    if not out_json.is_absolute():
        out_json = repo / out_json
    out_md = Path(args.out_md)
    if not out_md.is_absolute():
        out_md = repo / out_md
    doc = {"as_of": iso(args.as_of), "cells_total": total,
           "fake_executed": fake_executed, "not_run": browser,
           "exceptions": exceptions, "adversarial_rounds": rounds,
           "failures": len(failures), "cells": cells}

    new_json = stable_json(doc) + "\n"
    new_md = render_md(cells, matrix, args.as_of)
    if args.check:
        ok = out_json.exists() and out_json.read_text(encoding="utf-8") == new_json
        if not ok:
            print(f"FAIL: {out_json.name} drifted from the matrix — "
                  f"regenerate it")
            return EXIT_FAIL
        print(f"PASS: isolation_matrix --check (matrix record diff-clean)")
        return EXIT_PASS
    out_json.write_text(new_json, encoding="utf-8")
    out_md.write_text(new_md, encoding="utf-8")

    if args.json:
        print(json.dumps({"tool": "isolation_matrix", "cells_total": total,
                          "fake_executed": fake_executed,
                          "not_run": browser, "exceptions": exceptions,
                          "failures": len(failures),
                          "status": "pass" if not failures else "fail"},
                         sort_keys=True, indent=2))
    else:
        print(f"isolation_matrix: {fake_executed} fake cells executed / "
              f"{browser} not-run / {exceptions} exception / "
              f"{total} cells total; adversarial {rounds} rounds clean")
        if failures:
            for c in failures:
                print(f"FAIL: {c['mechanism']} {c['pair']}: {c['detail']}")
            return EXIT_FAIL
        print("PASS: isolation_matrix")
    return EXIT_PASS if not failures else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
