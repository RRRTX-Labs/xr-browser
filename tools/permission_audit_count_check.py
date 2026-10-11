#!/usr/bin/env python3
"""tools/permission_audit_count_check.py — no silent grant (P15 invariant 7; P15-CLOSE C9).

Every change to the permission overlay leaves exactly one audit row, so the
rows can be counted against the store. This gate replays a seeded op sequence
through xr-core/fakes/permissions.py (held byte-identical to the C++ host by
tools/permission_host_parity.py, 80 cases) and, after EVERY op, diffs the store:

  * grants created          == `grant` rows with a grant scope (once/session/7d)
  * grants revoked          == `revoke` rows with a grant scope
  * grants spent or expired == `expiry` rows
  * identity defaults changed == rows with scope `identity_default`
  * deny-list flips × capabilities == rows with scope `identity_deny_list`
    (a flip of the Fortress deny-list leaves one row per capability)

and the totals over the whole run must match too. A refusal must leave no row.
`--plant silent-grant` wraps the fake so one grant lands in the store without
its row (the defect this law exists for); the gate must then redden with a
count mismatch (tools/negatives/p15c_c9.sh).

Usage: permission_audit_count_check.py [--xr-core PATH] [--ops N] [--seed S]
       [--plant silent-grant] [--json]
Exit: 0 pass · 1 mismatch · 2 usage. Stdlib only; reads no clock (`now` is
the op index times a fixed step).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

GRANT_SCOPES = ("once", "session", "7d")
DOMAINS = ("example.com", "news.example", "maps.example", "shop.example")
IDENTS = ("xr:00000000-0000-4000-8000-0000000000a1", "xr:00000000-0000-4000-8000-0000000000b2")
STEP_MS = 3_600_000  # one hour per op: 7d grants expire inside a long run


def load_fake(xr_core: Path):
    spec = importlib.util.spec_from_file_location("xr_fake_permissions", xr_core / "fakes" / "permissions.py")
    if spec is None or spec.loader is None:
        raise FileNotFoundError(xr_core / "fakes" / "permissions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def grants(s: dict) -> dict[str, dict]:
    return {g["id"]: g for r in s["identities"].values() for g in r["grants"]}


def spent(g: dict) -> bool:
    return g["scope"] == "once" and g["remaining_uses"] <= 0


def store_delta(s0: dict, s1: dict, ncaps: int) -> dict[str, int]:
    g0, g1 = grants(s0), grants(s1)
    d = {"grant": sum(1 for k in g1 if k not in g0),
         "revoke": sum(1 for k, g in g1.items() if g["revoked"] and k in g0 and not g0[k]["revoked"]),
         "expiry": sum(1 for k, g in g0.items() if k not in g1 or (spent(g1[k]) and not spent(g))),
         "default": 0, "deny": 0}
    for ident in set(s0["identities"]) | set(s1["identities"]):
        r0, r1 = s0["identities"].get(ident), s1["identities"].get(ident)
        df0 = r0["defaults"] if r0 else {}
        df1 = r1["defaults"] if r1 else {}
        d["default"] += sum(1 for c in set(df0) | set(df1) if df0.get(c) != df1.get(c))
        d["deny"] += ncaps * int(bool(r0 and r0["denied"]) != bool(r1 and r1["denied"]))
    return d


def row_counts(rows: list[dict]) -> dict[str, int]:
    c = {"grant": 0, "revoke": 0, "expiry": 0, "default": 0, "deny": 0}
    for r in rows:
        if r["scope"] == "identity_deny_list":
            c["deny"] += 1
        elif r["scope"] == "identity_default":
            c["default"] += 1
        elif r["event"] in ("grant", "revoke", "expiry"):
            c[r["event"]] += 1
    return c


def next_op(rng: random.Random, s: dict, fake) -> tuple[str, dict]:
    ident = rng.choice(IDENTS)
    live = [g for g in grants(s).values() if not g["revoked"]]
    k = rng.randrange(10)
    if k < 4:
        sc = rng.choice(GRANT_SCOPES)
        return "grant", {"identity": ident, "domain": rng.choice(DOMAINS),
                         "capability": rng.choice(fake.CAPS), "scope": sc,
                         "session_id": "s1" if sc == "session" else ""}
    if k == 4:
        return "set-default", {"identity": ident, "capability": rng.choice(fake.CAPS),
                               "state": rng.choice(fake.STATES)}
    if k == 5:
        return "set-denied", {"identity": ident, "denied": rng.random() < 0.3}
    if k == 6 and live:
        return "consume-once", {"grant_id": rng.choice(live)["id"]}
    if k == 7:
        return "sweep", {"session_id": rng.choice(("s1", "s2", ""))}
    if k == 8:
        return "revoke-site", {"identity": ident, "domain": rng.choice(DOMAINS)}
    return "revoke-all", {"identity": ident}


def run(fake, ops: int, seed: int, plant: str) -> tuple[list[str], dict]:
    rng = random.Random(seed)
    s = fake.empty_store()
    fails: list[str] = []
    totals = {"store": dict.fromkeys(("grant", "revoke", "expiry", "default", "deny"), 0),
              "rows": dict.fromkeys(("grant", "revoke", "expiry", "default", "deny"), 0)}
    planted = False
    for i in range(ops):
        m, a = next_op(rng, s, fake)
        err, s1, rows = fake.apply(m, s, a, (i + 1) * STEP_MS)
        if plant == "silent-grant" and not planted and m == "grant" and not err:
            extra = dict(rows and grants(s1)[f"g{s1['next_seq'] - 1}"] or {})
            if extra:
                extra["id"] = f"g{s1['next_seq']}"
                s1["next_seq"] += 1
                s1["identities"][extra["identity"]]["grants"].append(extra)
                planted = True
        if err and rows:
            fails.append(f"op {i} {m}: refused ({err}) but emitted {len(rows)} row(s)")
        d, c = store_delta(s, s1, len(fake.CAPS)), row_counts(rows)
        for k in d:
            totals["store"][k] += d[k]
            totals["rows"][k] += c[k]
        if d != c:
            fails.append(f"op {i} {m}: count mismatch — store changed {d}, audit rows {c}")
        s = s1
    if totals["store"] != totals["rows"]:
        fails.append(f"totals mismatch — store {totals['store']} vs rows {totals['rows']}")
    if totals["rows"]["grant"] == 0:
        fails.append("the run created no grant (zero-case law: the law was never exercised)")
    return fails, totals


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--ops", type=int, default=600)
    ap.add_argument("--seed", type=int, default=20261010)
    ap.add_argument("--plant", choices=("", "silent-grant"), default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        fake = load_fake(Path(a.xr_core).resolve())
    except (OSError, AttributeError) as exc:
        print(f"usage error: cannot load the permissions fake: {exc}", file=sys.stderr)
        return 2
    fails, totals = run(fake, a.ops, a.seed, a.plant)
    if a.json:
        print(json.dumps({"tool": "permission_audit_count_check", "ops": a.ops, "seed": a.seed,
                          "totals": totals, "violations": fails[:20], "count": len(fails),
                          "status": "pass" if not fails else "fail"}, sort_keys=True, indent=2))
    else:
        for f in fails[:20]:
            print(f"FAIL: {f}")
        print(f"permission_audit_count_check: {a.ops} ops (seed {a.seed}), rows {totals['rows']}, "
              f"{len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
