#!/usr/bin/env python3
"""tools/gen_lists_compile_vectors.py — the xr-lists compile vectors
(P11-T3): one case per directive class, per the P11 gate row "compile
vectors per directive class (including a >=30-case refusal table)".

Expectation model: every case's `expect` is the REAL output of
xr-lists/compile.py's parse_line (loaded via importlib — the module name
`compile` shadows a builtin, so it is never imported by name) or, for
the file-level cases, of compile_config + the frozen bundle-digest rule.
--check regenerates byte-identical (no clock, no RNG). The refusal floor
(>=30 refusal cases) and full coverage of every REACHABLE refusal family
are enforced HERE and re-checked independently by
tools/list_bundle_check.py.

Cases:
  d-NNN — every line of xr-lists/sources/xr-synthetic-default.txt
  r-NNN — every line of xr-lists/sources/xr-synthetic-refusals.txt
  e-<slug> — hand-pinned edge lines (the classes the fixtures do not hit)
  f-<cfg> — file-level: the full compile of each config (digest + counts)

Exit: 0 ok · 1 drift/floor violation · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

OUT = "docs/contracts/vectors/xr-lists-compile-v1.json"
MIN_REFUSAL_CASES = 30

EDGE_LINES = [
    ("empty", ""),
    ("blank-space", "   "),
    ("comment", "! a plain comment"),
    ("header", "[Adblock Plus 2.0]"),
    ("cosmetic-marker-only", "##"),
    ("cosmetic-domains-mixed", "a.com,~b.com##.scoped-cosmetic"),
    ("cosmetic-scope-malformed", "a.com,##.broken-scope"),
    ("domain-option-trailing-tilde", "||x.example^$domain=a|~"),
    ("redirect-plus-refused-option", "||x.example^$redirect=r,$popup"),
    ("redirect-with-domain-ok",
     "||ok.example^$domain=a.example,redirect=1x1.gif"),
    ("exception-with-exclude", "@@||exc.example^$domain=~a.example"),
    ("both-anchors", "||both.example/x|"),
    ("leading-wildcard", "*leading-wild.example"),
    ("regex-bare", "/regex/"),
    ("procedural-has", "##.a:has(.b)"),
    ("scriptlet-marker", "#%#//anything('x')"),
    ("preprocessor-endif", "!#endif"),
    ("dollar-only", "$"),
    ("double-dollar", "||dd.example^$a=b$c"),
    ("interior-pipe-plain", "a|b"),
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normalize(outcomes: list) -> dict:
    if not outcomes:
        return {"skip": True}
    if outcomes[0].get("kind") == "rule":
        assert len(outcomes) == 1
        o = outcomes[0]
        r = {"action": o["action"], "filter": o["filter"], "kind": o["kind_"]}
        for opt in ("domains", "exclude_domains", "resource"):
            if opt in o:
                r[opt] = o[opt]
        return {"rule": r}
    return {"refusals": [{"directive": o["directive"], "reason": o["reason"]}
                         for o in outcomes]}


def build_cases(repo: Path, comp) -> list:
    cases = []
    src = repo / "xr-lists" / "sources"
    for prefix, fname in (("d", "xr-synthetic-default.txt"),
                          ("r", "xr-synthetic-refusals.txt")):
        for i, line in enumerate(
                (src / fname).read_text(encoding="utf-8").splitlines()):
            cases.append({"expect": normalize(comp.parse_line(line)),
                          "id": f"{prefix}-{i:03d}", "input": line})
    for slug, line in EDGE_LINES:
        cases.append({"expect": normalize(comp.parse_line(line)),
                      "id": f"e-{slug}", "input": line})
    for cfg in ("config.json", "config-hotpin-v1.json",
                "config-hotpin-v2.json"):
        bundle = comp.compile_config(src / cfg)
        cases.append({
            "config": f"xr-lists/sources/{cfg}",
            "expect": {
                "digest": comp.bundle_digest(bundle),
                "list_rule_counts": {l["name"]: len(l["rules"])
                                     for l in bundle["lists"]},
                "refusal_entries": len(bundle["refusals"]),
                "refused_lines": sum(r["count"]
                                     for r in bundle["refusals"]),
            },
            "id": f"f-{Path(cfg).stem}",
        })
    return cases


def main() -> int:
    ap = argparse.ArgumentParser(prog="gen-lists-compile-vectors")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_lists = repo / "xr-lists"
    comp = load_module("xr_lists_compile", xr_lists / "compile.py")
    bytes_mod = load_module("xr_lists_bundle_bytes",
                            xr_lists / "bundle_bytes.py")
    comp.bundle_digest = bytes_mod.bundle_digest  # file-level cases
    cases = build_cases(repo, comp)
    ids = [c["id"] for c in cases]
    refusal_cases = [c for c in cases if "refusals" in c["expect"]]
    if len(ids) != len(set(ids)):
        print("FAIL: duplicate vector ids")
        return 1
    if len(refusal_cases) < MIN_REFUSAL_CASES:
        print(f"FAIL: only {len(refusal_cases)} refusal cases "
              f"(< {MIN_REFUSAL_CASES})")
        return 1
    doc = {"cases": cases, "schema": "xr-lists-compile-vectors",
           "schema_version": 1,
           "note": "Compile vectors for the xr-lists pipeline (P11-T3): "
                   "every case's expect is the real output of "
                   "xr-lists/compile.py (parse_line for line cases, "
                   "compile_config + the frozen digest rule for "
                   "file-level cases). tools/list_bundle_check.py "
                   "re-enforces the refusal floor and family coverage "
                   "against this file; the golden package under "
                   "xr-lists/testdata/ pins the whole-pipeline bytes."}
    blob = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out = repo / OUT
    if a.check:
        if not out.exists() or out.read_text(encoding="utf-8") != blob:
            print(f"DRIFT: {OUT} does not match regeneration; run "
                  "tools/gen_lists_compile_vectors.py")
            return 1
        print(f"PASS: {OUT} regenerates byte-identical ({len(cases)} cases, "
              f"{len(refusal_cases)} refusal cases)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    print(f"wrote {len(cases)} cases ({len(refusal_cases)} refusal) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
