#!/usr/bin/env python3
"""tools/mutation_test.py — mutation-testing gate for the policy core (P6-T4).

Operator suite over xr-core/policy/core/*.cc, in-house (no external mutation
framework — DEPENDENCY RULES). Operators follow the classic taxonomy
(research log R3): ROR (relational replacement == != < <= > >=), LOR
(&& <-> ||), boolean-literal flips, AOR-style integer-constant ±1, and
return-value substitution (return false <-> true, 0 <-> 1, tier/deny-path
substitution). Per mutant: copy the tree to a temp dir, apply ONE mutation,
rebuild the affected TU, re-run the mapped test suites; killed iff any suite
fails. Score gate: >=90% overall AND 100% of deny-guard mutants (validation
`return false`/`nullopt`/`-1` lines whose mutation flips toward accept —
the "never guess" guards).

Runtime: full matrix ~15-25 min on 2 cores; CI uses --sample (seeded,
deterministic) with the same gates; the full matrix is the farm job (HG-28).
Survivors are reported with file:line + operator and must be explained in
evidence/P6/mutation-report.md (equivalent-mutant justification) or closed
with a new test.

Stdlib only. Exit: 0 gate passed · 1 gate failed · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# TU -> test suites that exercise it (superset mapping is fine; exact enough
# to keep per-mutant runtime low).
SUITE_MAP = {
    "json.cc": ["test_vectors", "test_resolve", "test_json"],
    "json_parse.cc": ["test_vectors", "test_resolve", "test_json"],
    "sha256.cc": ["test_vectors"],
    "effective_policy.cc": ["test_vectors", "test_resolve", "test_snapshot"],
    "resolve.cc": ["test_vectors", "test_resolve"],
    "resolve_io.cc": ["test_vectors", "test_resolve"],
    "cache.cc": ["test_cache"],
    "snapshot.cc": ["test_snapshot"],
    "store.cc": ["test_store", "test_service"],
    "events.cc": ["test_events"],
    "service.cc": ["test_service"],
}

# One mutation per (line, operator-instance): operator name, regex, rewrite.
OPERATORS: list[tuple[str, re.Pattern[str], str]] = [
    ("ROR:== -> !=", re.compile(r"(?<![!<>=])==(?!=)"), "!="),
    ("ROR:!= -> ==", re.compile(r"!=(?!=)"), "=="),
    ("ROR:< -> <=", re.compile(r"(?<![<>=])<(?![<=])"), "<="),
    ("ROR:<= -> <", re.compile(r"<=(?!=)"), "<"),
    ("ROR:> -> >=", re.compile(r"(?<![<>=])>(?![>=])"), ">="),
    ("ROR:>= -> >", re.compile(r">=(?!=)"), ">"),
    ("LOR:&& -> ||", re.compile(r"&&"), "||"),
    ("LOR:|| -> &&", re.compile(r"\|\|"), "&&"),
    ("BOOL:true -> false", re.compile(r"\btrue\b"), "false"),
    ("BOOL:false -> true", re.compile(r"\bfalse\b"), "true"),
    ("AOR:0 -> 1", re.compile(r"(?<![\w.])0(?![\w.])"), "1"),
    ("AOR:1 -> 2", re.compile(r"(?<![\w.])1(?![\w.])"), "2"),
    ("AOR:2 -> 3", re.compile(r"(?<![\w.])2(?![\w.])"), "3"),
]

DENY_GUARD_RE = re.compile(
    r"return\s+(false|std::nullopt|nullptr|-1)\s*;|return\s+false\b")

SKIP_LINE_RE = re.compile(r"^\s*//|^\s*\*|#include|^\s*case |^\s*constexpr|^\s*static const")


def gen_mutants(path: Path, rel: str) -> list[dict[str, Any]]:
    """Yields one mutant per (line, first operator match)."""
    mutants: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for lineno, line in enumerate(lines, start=1):
        if SKIP_LINE_RE.search(line) or not line.strip():
            continue
        for name, pat, repl in OPERATORS:
            m = pat.search(line)
            if m is None:
                continue
            new_line = line[:m.start()] + repl + line[m.end():]
            if new_line == line:
                continue
            deny_guard = bool(DENY_GUARD_RE.search(line))
            mutants.append({
                "file": rel, "line": lineno, "operator": name,
                "orig": line.rstrip("\n"), "mutated": new_line.rstrip("\n"),
                "deny_guard": deny_guard,
            })
            break  # one mutation per line (first applicable operator)
    return mutants


def apply_and_build(tmp: Path, mutant: dict[str, Any], suites: list[str],
                    jobs: int) -> tuple[bool, str]:
    """Writes the mutant, rebuilds mapped suites. Returns (build_ok, log)."""
    target = tmp / "policy" / "core" / Path(mutant["file"]).name
    text = target.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    idx = mutant["line"] - 1
    if idx >= len(lines) or lines[idx].rstrip("\n") != mutant["orig"]:
        return False, "line drift (mutant stale)"
    lines[idx] = lines[idx].replace(mutant["orig"], mutant["mutated"], 1)
    target.write_text("".join(lines), encoding="utf-8")
    make_targets = [f"build/{s}" for s in suites]
    r = subprocess.run(
        ["make", "-C", str(tmp / "policy" / "tests"), "-j", str(jobs), *make_targets],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "XR_BROWSER_ROOT": ""},
    )
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


def run_suites(tmp: Path, suites: list[str], vectors_env: str) -> tuple[bool, str]:
    """Runs the mapped suites against the built mutant. killed = any fail."""
    logs = []
    for s in suites:
        r = subprocess.run(
            [str(tmp / "policy" / "tests" / "build" / s)],
            capture_output=True, text=True, timeout=120,
            env={"XR_BROWSER_ROOT": vectors_env, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        logs.append(f"[{s}] rc={r.returncode}\n{(r.stdout + r.stderr)[-800:]}")
        if r.returncode != 0:
            return True, "\n".join(logs)  # killed
    return False, "\n".join(logs)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mutation_test", description="policy-core mutation gate")
    p.add_argument("--xr-core", default="../xr-core")
    p.add_argument("--sample", type=int, default=0,
                   help="run a seeded sample of N mutants (CI); 0 = full matrix")
    p.add_argument("--seed", type=int, default=20260908, help="sample seed (deterministic)")
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--score-gate", type=float, default=90.0)
    p.add_argument("--report-json", default=None)
    p.add_argument("--report-md", default=None)
    p.add_argument("--timebox", type=int, default=0,
                   help="stop generating NEW mutants after N seconds (0 = no cap); "
                        "report records truncation honestly")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    core = Path(args.xr_core).resolve() / "policy" / "core"
    if not core.is_dir():
        print(f"error: policy core not found: {core}", file=sys.stderr)
        return EXIT_USAGE

    # Collect all mutants across the core TUs.
    browser_root = str(Path(args.xr_core).resolve().parent / "xr-browser")
    all_mutants: list[dict[str, Any]] = []
    for cc in sorted(core.glob("*.cc")):
        rel = "core/" + cc.name
        ms = gen_mutants(cc, rel)
        for m in ms:
            m["suites"] = SUITE_MAP.get(cc.name, ["test_vectors", "test_resolve"])
        all_mutants.extend(ms)

    sampled = False
    if args.sample and args.sample < len(all_mutants):
        import random
        rng = random.Random(args.seed)
        all_mutants = rng.sample(all_mutants, args.sample)
        sampled = True

    # Scratch tree: full copy of policy/ (+ tests) so the real tree is never
    # touched by mutations.
    tmp = Path(f"/tmp/p6_mutation_tree_{os.getpid()}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    shutil.copytree(Path(args.xr_core).resolve() / "policy", tmp / "policy")

    t0 = time.monotonic()
    killed = survived = build_fail = 0
    deny_guard_total = deny_guard_killed = 0
    survivors: list[dict[str, Any]] = []
    truncated = False
    for i, m in enumerate(all_mutants):
        if args.timebox and time.monotonic() - t0 > args.timebox:
            all_mutants = all_mutants[:i]
            truncated = True
            break
        ok, log = apply_and_build(tmp, m, m["suites"], args.jobs)
        if not ok:
            # Build failure under -Werror counts as killed (the mutation
            # broke compilation — the code cannot silently accept).
            killed += 1
            if m["deny_guard"]:
                deny_guard_total += 1
                deny_guard_killed += 1
            m["disposition"] = "killed(build)"
            continue
        was_killed, run_log = run_suites(tmp, m["suites"], str(Path(args.xr_core).resolve().parent / "xr-browser") if False else str(Path(args.xr_core).resolve().parent / "xr-browser"))
        if m["deny_guard"]:
            deny_guard_total += 1
            if was_killed:
                deny_guard_killed += 1
        if was_killed:
            killed += 1
            m["disposition"] = "killed(test)"
        else:
            survived += 1
            m["disposition"] = "SURVIVED"
            m["run_log"] = run_log[-1500:]
            survivors.append(m)
        # restore original for the next mutant
        orig_src = Path(args.xr_core).resolve() / "policy" / m["file"]
        (tmp / "policy" / m["file"]).write_text(orig_src.read_text(encoding="utf-8"))

    total = killed + survived
    score = (100.0 * killed / total) if total else 100.0
    dg_ok = deny_guard_total == deny_guard_killed

    report = {
        "tool": "mutation_test", "target": "xr-core/policy/core/*.cc",
        "operators": [n for n, _, _ in OPERATORS],
        "total_mutants": total, "killed": killed, "survived": survived,
        "score_pct": round(score, 2), "score_gate_pct": args.score_gate,
        "deny_guard_mutants": deny_guard_total,
        "deny_guard_killed": deny_guard_killed,
        "deny_guard_survivors": deny_guard_total - deny_guard_killed,
        "sampled": sampled, "seed": args.seed, "truncated_by_timebox": truncated,
        "elapsed_seconds": round(time.monotonic() - t0, 1),
        "suites": sorted({s for m in all_mutants for s in m["suites"]}),
        "survivors": [{k: m[k] for k in ("file", "line", "operator", "orig", "mutated",
                                          "deny_guard", "disposition")}
                      for m in survivors],
        "gate": "PASS" if (score >= args.score_gate and dg_ok) else "FAIL",
    }
    out = json.dumps(report, sort_keys=True, indent=1)
    if args.report_json:
        Path(args.report_json).write_text(out + "\n", encoding="utf-8")
    if args.report_md:
        lines = [
            "# P6 mutation report (generated — do not hand-edit)",
            "",
            f"- target: `xr-core/policy/core/*.cc`",
            f"- mutants: {total} (killed {killed}, survived {survived})",
            f"- score: **{score:.2f}%** (gate ≥ {args.score_gate}%)",
            f"- deny-guard mutants: {deny_guard_total}, killed {deny_guard_killed} "
            f"(gate: 100%)",
            f"- mode: {'sampled' if sampled else 'full'} (seed {args.seed})",
            f"- elapsed: {report['elapsed_seconds']}s",
            "",
            "## Survivors (each requires an equivalent-mutant justification",
            "or a test-gap fix)",
            "",
        ]
        for m in survivors:
            lines += [
                f"### {m['file']}:{m['line']} — {m['operator']}"
                f"{' (DENY-GUARD)' if m['deny_guard'] else ''}",
                "", "```cpp", f"- {m['orig']}", f"+ {m['mutated']}", "```", "",
            ]
        if not survivors:
            lines.append("(none)")
        Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out if args.json else
          f"mutation: {total} mutants, killed {killed}, survived {survived}, "
          f"score {score:.2f}% (gate >= {args.score_gate}%), "
          f"deny-guard {deny_guard_killed}/{deny_guard_total}, "
          f"elapsed {report['elapsed_seconds']}s -> {report['gate']}")
    shutil.rmtree(tmp, ignore_errors=True)
    return EXIT_PASS if report["gate"] == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
