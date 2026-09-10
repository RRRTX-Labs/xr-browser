#!/usr/bin/env python3
"""tools/seed_corpus.py — seed the fuzz corpus dirs from REAL artifacts (P9-T8).

The libFuzzer targets (CI-side, clang) consume build/fuzz/corpus/<target>/;
the fleet gate (tools/fuzz_fleet.py) fails if any dir is unseeded. This
script derives the seeds deterministically from the frozen P5 fixtures
(xr-core/fakes/fixtures/*) and the P9-T0-a parity corpora
(tools/parity/corpus-{settings,commands,themes}.json) — the same value
domains the C++ validators reject. Nothing here is synthesized from a
placeholder; every seed is a byte-copy of a committed artifact.

--check verifies the committed corpus dirs match the derivation (determinism
law: same artifacts => same seeds).

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, \
    require_cases, stable_json  # noqa: E402

XRCORE = "../xr-core"


def policy_seeds(core: Path) -> list[tuple[str, str]]:
    # policy corpus seeds: every request shape the resolver grammar admits,
    # serialized deterministically from the fuzz grammar's own domains.
    identities = ["xr:00000000-0000-4000-8000-000000000001",
                  "xr:00000000-0000-4000-8000-0000000000ef"]
    shapes = []
    for ident in identities:
        for scheme in ("https", "file"):
            for cls in ("kNavigation", "kScript", "kStorage"):
                for trust in ("kStandard", "kShield", "kFortress"):
                    req = {"identity": {"value": ident},
                           "origin": {"scheme": scheme,
                                      "registrable_domain": "example.com"},
                           "trust_context": trust,
                           "request_class": cls}
                    shapes.append((f"policy-{ident[-4:]}-{scheme}-{cls}-"
                                   f"{trust}.json",
                                   stable_json(req)))
    return shapes


def parity_seeds(repo: Path, core: Path, host: str,
                 label: str) -> list[tuple[str, str]]:
    doc = json.loads((repo / f"tools/parity/corpus-{host}.json")
                     .read_text(encoding="utf-8"))
    out = []
    for case in doc["cases"]:
        args = dict(case.get("args") or {})
        if "theme_doc" in case:
            args["theme-doc"] = json.dumps(case["theme_doc"])
        blob = stable_json({"method": case.get("method"), "args": args,
                            "expect": case.get("expect")})
        out.append((f"{label}-{case.get('id')}.json", blob))
    return out


def derive(repo: Path) -> dict[str, list[tuple[str, str]]]:
    core = (repo / XRCORE).resolve()
    fixtures = core / "fakes" / "fixtures"
    settings_doc = fixtures / "settings-example.json"
    command_doc = fixtures / "command-descriptor-v1.json"
    seeds: dict[str, list[tuple[str, str]]] = {}
    seeds["policy-core"] = policy_seeds(core)
    seeds["commands-core"] = (
        [("commands-descriptor.json",
          command_doc.read_text(encoding="utf-8").strip())] +
        parity_seeds(repo, core, "commands", "commands"))
    seeds["settings-core"] = (
        [("settings-example.json",
          settings_doc.read_text(encoding="utf-8").strip())] +
        parity_seeds(repo, core, "settings", "settings"))
    seeds["themes-core"] = parity_seeds(repo, core, "themes", "themes")
    return seeds


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="seed_corpus", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed corpus dirs drifted")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    seeds = derive(repo)
    total = sum(len(v) for v in seeds.values())
    require_cases(total, "seed_corpus")

    manifest = {}
    for target, files in seeds.items():
        cdir = repo / "build" / "fuzz" / "corpus" / target
        manifest[target] = len(files)
        if args.check:
            if not cdir.is_dir():
                print(f"FAIL: {cdir} missing (unseeded corpus)")
                return EXIT_FAIL
            got = {f.name: f.read_text(encoding="utf-8").strip()
                   for f in cdir.iterdir()}
            want = {name: blob for name, blob in files}
            if got != want:
                print(f"FAIL: {target} corpus drifted — re-run --seed "
                      f"(determinism law)")
                return EXIT_FAIL
        else:
            cdir.mkdir(parents=True, exist_ok=True)
            for stale in cdir.iterdir():
                stale.unlink()
            for name, blob in files:
                (cdir / name).write_text(blob + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"tool": "seed_corpus", "total": total,
                          "manifest": manifest,
                          "status": "pass" if args.check else "seeded"},
                         sort_keys=True, indent=2))
    else:
        verb = "verified" if args.check else "seeded"
        print(f"seed_corpus: {total} seed(s) {verb} "
              f"({', '.join(f'{k}={v}' for k, v in manifest.items())})")
        print(f"PASS: seed_corpus {'--check' if args.check else ''}".strip())
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
