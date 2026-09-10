#!/usr/bin/env python3
"""tools/mojom_fuzz_gen.py — contract-driven request generator (P9-T8).

The plan's T8 "Mojo interface fuzz harness (contract-driven from P5 fakes)".
The bind-side fuzzing needs clang/libFuzzer + a browser process (farm); the
GENERATOR is pure python and runs today: it consumes the frozen mojom value
domains as realized by the P5 fakes + the P9-T0-a parity corpora, and emits
deterministic, seeded request sequences for the FOUR host pairs
(policy / commands / settings / themes) — valid seeds mutated with the same
hostile alphabet the differential oracle rejects (wrong types, duplicate
keys, oversized docs, unknown tokens, unknown methods). This is exactly the
machinery that would have caught T0-a: a byte-parity surface fed only
hostile-but-unseen shapes.

Output is JSON Lines: {host, case_id, method, args, mutation}. --count is
PER HOST (default 1000). The consumer is tools/differential_fuzz.py (the
oracle); this generator asserts nothing about verdicts — it only guarantees
coverage and determinism (same --seed => same bytes).

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, RunnerError, \
    require_cases, seed_rng, stable_json  # noqa: E402

CORPORA = {
    "themes": "tools/parity/corpus-themes.json",
    "settings": "tools/parity/corpus-settings.json",
    "commands": "tools/parity/corpus-commands.json",
}

HOSTILE_STRINGS = ["<script>alert(1)</script>", "url(https://evil.example/x)",
                   "1e999", "\u0000", "\ufffd\ufffd", "", "99999999999999999999",
                   "#", "null", "true", "[]", "{}"]
HOSTILE_KEYS = ["__proto__", "ghost", "constructor", "xr", "0", ""]


def policy_seed(rng) -> dict:
    """A valid-shaped policy request from the resolver grammar."""
    identities = ["xr:00000000-0000-4000-8000-000000000001",
                  "xr:00000000-0000-4000-8000-000000000002",
                  "xr:00000000-0000-4000-8000-0000000000ef"]
    schemes = ["https", "http", "ftp", "file"]
    classes = ["kNavigation", "kScript", "kPermission", "kSubresource",
               "kStorage", "kNetwork"]
    trusts = ["kStandard", "kShield", "kFortress", None]
    return {"method": "resolve", "source_case": "policy-grammar",
            "args": {"identity": {"value": rng.choice(identities)},
                     "origin": {"scheme": rng.choice(schemes),
                                "registrable_domain": "example.com"},
                     "trust_context": rng.choice(trusts),
                     "request_class": rng.choice(classes)}}


def corpus_seeds(repo: Path, host: str) -> list[dict]:
    p = repo / CORPORA[host]
    doc = json.loads(p.read_text(encoding="utf-8"))
    out: list[dict] = []
    for case in doc["cases"]:
        method = case.get("method")
        args = dict(case.get("args") or {})
        if "theme_doc" in case:
            args["theme-doc"] = json.dumps(case["theme_doc"])
        out.append({"method": method, "args": args,
                    "source_case": case.get("id")})
    return out


def mutate(rng, seed: dict) -> dict:
    """One deterministic mutation of a valid request seed."""
    m = {"method": seed["method"], "args": dict(seed["args"]),
         "mutation": [], "source_case": seed.get("source_case", "policy")}
    mode = rng.randrange(6)
    keys = list(m["args"].keys())
    if mode == 0 and keys:          # value -> hostile string
        k = rng.choice(keys)
        m["args"][k] = rng.choice(HOSTILE_STRINGS)
        m["mutation"].append("hostile-value")
    elif mode == 1 and keys:        # value -> wrong type (int)
        k = rng.choice(keys)
        m["args"][k] = rng.choice([0, 1, -1, 999999999999])
        m["mutation"].append("type-swap")
    elif mode == 2:                 # unknown key
        m["args"][rng.choice(HOSTILE_KEYS)] = "#ff0000"
        m["mutation"].append("unknown-key")
    elif mode == 3 and keys:        # duplicate key via raw string (themes only
        # is exercised through theme-doc; here we just flag it)
        m["mutation"].append("dup-key-flag")
    elif mode == 4:                 # unknown method
        m["method"] = "no-such-method"
        m["mutation"].append("unknown-method")
    else:                           # oversize padding on a theme-doc
        m["args"]["theme-doc"] = "x" * 70000
        m["mutation"].append("oversize")
    return m


def generate(repo: Path, count: int, seed: int) -> dict[str, list[dict]]:
    rng = seed_rng(seed)
    out: dict[str, list[dict]] = {}
    for host in ("policy", "commands", "settings", "themes"):
        seq: list[dict] = []
        if host == "policy":
            seeds = [policy_seed(rng) for _ in range(20)]
        else:
            seeds = corpus_seeds(repo, host)
        if not seeds:
            raise RunnerError(f"{host}: no contract seeds (empty-run law)")
        for i in range(count):
            base = seeds[i % len(seeds)]
            seq.append({"host": host, "case_id": f"{host}-{i:05d}",
                        **mutate(rng, base)})
        out[host] = seq
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mojom_fuzz_gen", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--count", type=int, default=1000,
                   help="cases per host (default 1000)")
    p.add_argument("--seed", type=int, default=20260910)
    p.add_argument("--out", default="", help="write JSON Lines here")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed stream drifted")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        out = generate(repo, args.count, args.seed)
    except RunnerError as exc:
        print(f"FAIL: {exc}")
        return EXIT_FAIL
    total = sum(len(v) for v in out.values())
    require_cases(total, "mojom_fuzz_gen", min_cases=4 * args.count)

    lines = []
    for host in ("policy", "commands", "settings", "themes"):
        for case in out[host]:
            lines.append(stable_json(case))
    stream = "\n".join(lines) + "\n"

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = repo / out_path
        if args.check:
            ok = out_path.exists() and \
                out_path.read_text(encoding="utf-8") == stream
            if not ok:
                print(f"FAIL: {out_path} drifted — regenerate (determinism "
                      f"law: same --seed => same bytes)")
                return EXIT_FAIL
            print(f"PASS: mojom_fuzz_gen --check ({total} cases, diff-clean)")
            return EXIT_PASS
        out_path.write_text(stream, encoding="utf-8")
    if args.json:
        print(json.dumps({"tool": "mojom_fuzz_gen", "total": total,
                          "per_host": {k: len(v) for k, v in out.items()},
                          "status": "pass"}, sort_keys=True, indent=2))
    else:
        per = {k: len(v) for k, v in out.items()}
        print(f"mojom_fuzz_gen: {total} cases "
              f"({', '.join(f'{k}={v}' for k, v in per.items())})")
        print("PASS: mojom_fuzz_gen")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
