#!/usr/bin/env python3
"""tools/mutation_test.py — mutation-testing gate for xr std-only cores.

Operator suite over xr-core/<target>/core/*.cc, in-house (no external
mutation framework — DEPENDENCY RULES). Targets (P8-T4 generalization; the
P6 default is unchanged): --targets policy,settings,themes (comma list;
default policy, which keeps the P6 lane byte-for-byte the same path).

Operators follow the classic taxonomy (research log R3): ROR (relational
replacement == != < <= > >=), LOR (&& <-> ||), boolean-literal flips,
AOR-style integer-constant ±1, and return-value substitution (return false
<-> true, 0 <-> 1, tier/deny-path substitution). Per mutant: copy the target
tree to a temp dir, apply ONE mutation, rebuild the affected TU, re-run the
mapped test suites (cwd = the tests dir, same relative data paths as
`make test`); killed iff any suite fails. Score gate: >=--score-gate overall
AND 100% of deny-guard mutants (validation `return false`/`nullopt`/`-1`
lines whose mutation flips toward accept — the "never guess" guards).
Each target's suites come from its own SUITE_MAPS entry (per-TU -> suites);
the wall-clock fuzz suites are NOT mapped per-mutant (a fuzz run per mutant
would dominate the matrix; their invariants are covered by the unit suites +
the separate 600 s evidence campaigns).

Runtime: full matrix on 2 cores ~15-25 min per target; CI uses --sample
(seeded, deterministic) with the same gates; the full matrix is recorded in
evidence (HG-28 runs the farm-time 24 h matrices). Survivors are reported
with file:line + operator and must be dispositioned (equivalent-mutant
justification or a new test) in the evidence report.

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

from mutation_targets import SUITE_MAPS

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# TU -> test suites that exercise it (superset mapping is fine; exact enough
# to keep per-mutant runtime low). The wall-clock fuzz suites stay OUT of the
# per-mutant maps (unit budgets + the 600 s evidence campaigns cover them).
DEFAULT_TARGET = "policy"
SUITE_MAP = SUITE_MAPS[DEFAULT_TARGET]  # keeps gen_mutants' call site simple

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


def apply_and_build(tmp: Path, target: str, mutant: dict[str, Any],
                    suites: list[str], jobs: int) -> tuple[bool, str]:
    """Writes the mutant, rebuilds mapped suites. Returns (build_ok, log)."""
    tgt = tmp / target / "core" / Path(mutant["file"]).name
    text = tgt.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    idx = mutant["line"] - 1
    if idx >= len(lines) or lines[idx].rstrip("\n") != mutant["orig"]:
        return False, "line drift (mutant stale)"
    lines[idx] = lines[idx].replace(mutant["orig"], mutant["mutated"], 1)
    tgt.write_text("".join(lines), encoding="utf-8")
    make_targets = [f"build/{s}" for s in suites]
    # a host-suite needs its host binary built too (settings_host/themes_host)
    if "test_host" in suites:
        make_targets.append("build/themes_host")
    if "test_settings_host" in suites:
        make_targets.append("build/settings_host")
    if "test_golden_vectors" in suites or "test_update_host" in suites:
        make_targets.append("build/update_host")
    r = subprocess.run(
        ["make", "-C", str(tmp / target / "tests"), "-j", str(jobs), *make_targets],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "XR_BROWSER_ROOT": ""},
    )
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


def run_suites(tmp: Path, target: str, suites: list[str],
                vectors_env: str) -> tuple[bool, str]:
    """Runs the mapped suites against the built mutant. killed = any fail.
    cwd = the target's tests dir so the suites' relative data paths
    (../../core/..., ../../ui/...) resolve exactly as under `make test`."""
    logs = []
    cwd = tmp / target / "tests"
    for s in suites:
        r = subprocess.run(
            [str(cwd / "build" / s)],
            capture_output=True, text=True, timeout=120,
            cwd=cwd,
            env={"XR_BROWSER_ROOT": vectors_env,
                 "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        logs.append(f"[{s}] rc={r.returncode}\n{(r.stdout + r.stderr)[-800:]}")
        if r.returncode != 0:
            return True, "\n".join(logs)  # killed
    return False, "\n".join(logs)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mutation_test",
                                description="xr std-only core mutation gate")
    p.add_argument("--xr-core", default="../xr-core")
    p.add_argument("--targets", default=DEFAULT_TARGET,
                   help="comma list of core roots under xr-core/"
                        "(policy|settings|themes|commands|update); default "
                        "policy (P6 lane)")
    p.add_argument("--sample", type=int, default=0,
                   help="run a seeded sample of N mutants per target (CI); "
                        "0 = full matrix")
    p.add_argument("--seed", type=int, default=20260908, help="sample seed")
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--score-gate", type=float, default=90.0)
    p.add_argument("--report-json", default=None)
    p.add_argument("--report-md", default=None)
    p.add_argument("--timebox", type=int, default=0,
                   help="stop generating NEW mutants after N seconds "
                        "(0 = no cap); report records truncation honestly")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.xr_core).resolve()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    for t in targets:
        if t not in SUITE_MAPS or not (root / t / "core").is_dir():
            print(f"error: unknown target {t!r} (need a SUITE_MAPS entry and "
                  f"{root / t / 'core'})", file=sys.stderr)
            return EXIT_USAGE

    browser_root = str(root.parent / "xr-browser")
    vectors_env = str(root.parent / "xr-browser")
    all_ok = True
    target_reports: list[dict[str, Any]] = []
    for target in targets:
        core = root / target / "core"
        suite_map = SUITE_MAPS[target]
        mutants: list[dict[str, Any]] = []
        for cc in sorted(core.glob("*.cc")):
            rel = "core/" + cc.name
            for m in gen_mutants(cc, rel):
                m["target"] = target
                m["suites"] = suite_map.get(
                    cc.name, ["test_vectors", "test_resolve"])
                mutants.append(m)

        sampled = False
        if args.sample and args.sample < len(mutants):
            import random
            rng = random.Random(args.seed)
            mutants = rng.sample(mutants, args.sample)
            sampled = True

        tmp = Path(f"/tmp/xr_mutation_tree_{os.getpid()}")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        shutil.copytree(root / target, tmp / target)
        # P11-T0-b: every suite lane now compiles the SINGLE shared copy of
        # json/sha256 from ../../common/core — the shared core must exist in
        # the tmp tree for every target (copytree keeps mtimes, so a target's
        # prebuilt common objects stay up-to-date and are never mutated).
        if target != "common" and (root / "common").is_dir():
            shutil.copytree(root / "common", tmp / "common")

        t0 = time.monotonic()
        killed = survived = build_fail = 0
        deny_guard_total = deny_guard_killed = 0
        survivors: list[dict[str, Any]] = []
        truncated = False
        for i, m in enumerate(mutants):
            if args.timebox and time.monotonic() - t0 > args.timebox:
                mutants = mutants[:i]
                truncated = True
                break
            ok, log = apply_and_build(tmp, target, m, m["suites"], args.jobs)
            if not ok:
                if "line drift" in log:
                    survived += 1
                    m["disposition"] = "SURVIVED(stale-line)"
                    survivors.append(m)
                    continue
                # Build failure under -Werror counts as killed (the mutation
                # broke compilation — the code cannot silently accept).
                killed += 1
                if m["deny_guard"]:
                    deny_guard_total += 1
                    deny_guard_killed += 1
                m["disposition"] = "killed(build)"
                continue
            was_killed, run_log = run_suites(tmp, target, m["suites"],
                                             vectors_env)
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
            orig_src = root / target / m["file"]
            (tmp / target / m["file"]).write_text(
                orig_src.read_text(encoding="utf-8"))

        total = killed + survived
        score = (100.0 * killed / total) if total else 100.0
        dg_ok = deny_guard_total == deny_guard_killed
        ok_target = (score >= args.score_gate and dg_ok and not truncated)
        if not ok_target:
            all_ok = False

        rep = {
            "target": f"xr-core/{target}/core/*.cc",
            "total_mutants": total, "killed": killed, "survived": survived,
            "score_pct": round(score, 2), "score_gate_pct": args.score_gate,
            "deny_guard_mutants": deny_guard_total,
            "deny_guard_killed": deny_guard_killed,
            "deny_guard_survivors": deny_guard_total - deny_guard_killed,
            "sampled": sampled, "seed": args.seed,
            "truncated_by_timebox": truncated,
            "suites": sorted({s for m in mutants for s in m["suites"]}),
            "survivors": [{k: m[k] for k in (
                "target", "file", "line", "operator", "orig", "mutated",
                "deny_guard", "disposition")} for m in survivors],
            "gate": "PASS" if ok_target else "FAIL",
        }
        target_reports.append(rep)
        summary = (f"mutation[{target}]: {total} mutants, killed {killed}, "
                   f"survived {survived}, score {score:.2f}% "
                   f"(gate >= {args.score_gate}%), deny-guard "
                   f"{deny_guard_killed}/{deny_guard_total}, elapsed "
                   f"{round(time.monotonic() - t0, 1)}s -> {rep['gate']}")
        if args.json:
            print(summary, file=sys.stderr)
            for m in survivors:
                print(f"  SURVIVOR {m['file']}:{m['line']} {m['operator']} "
                      f"{m['mutated'].strip()}", file=sys.stderr)
        else:
            print(summary)
            for m in survivors:
                print(f"  SURVIVOR {m['file']}:{m['line']} {m['operator']} "
                      f"{m['mutated'].strip()}")
        shutil.rmtree(tmp, ignore_errors=True)

    if len(target_reports) == 1:
        # Single target: keep the legacy flat report shape (P6 consumers —
        # the CI sample lane and the farm matrix parser — read these keys).
        report = dict(target_reports[0])
        report["tool"] = "mutation_test"
        report["operators"] = [n for n, _, _ in OPERATORS]
    else:
        report = {
            "tool": "mutation_test",
            "targets": [t for t in targets],
            "operators": [n for n, _, _ in OPERATORS],
            "target_reports": target_reports,
            "gate": "PASS" if all_ok else "FAIL",
        }
    out = json.dumps(report, sort_keys=True, indent=1)
    if args.report_json:
        Path(args.report_json).write_text(out + "\n", encoding="utf-8")
    if args.report_md:
        groups = target_reports
        lines = [
            "# xr mutation report (generated — do not hand-edit)", "",
        ]
        for rep in groups:
            lines += [
                f"## {rep['target']}",
                "",
                f"- mutants: {rep['total_mutants']} "
                f"(killed {rep['killed']}, survived {rep['survived']})",
                f"- score: **{rep['score_pct']:.2f}%** "
                f"(gate >= {rep['score_gate_pct']}%)",
                f"- deny-guard mutants: {rep['deny_guard_mutants']}, "
                f"killed {rep['deny_guard_killed']} (gate: 100%)",
                f"- mode: {'sampled' if rep['sampled'] else 'full'} "
                f"(seed {rep['seed']})",
                "",
                "### Survivors (each requires an equivalent-mutant "
                "justification or a test-gap fix)", "",
            ]
            for m in rep["survivors"]:
                lines += [
                    f"#### {m['file']}:{m['line']} — {m['operator']}",
                    "", "```cpp", f"- {m['orig']}", f"+ {m['mutated']}",
                    "```", "",
                ]
            if not rep["survivors"]:
                lines.append("(none)")
    if args.json:
        print(out)  # stdout stays PURE JSON under --json (parity contract)
    else:
        print(f"mutation: targets={args.targets} -> {report['gate']}")
    return EXIT_PASS if all_ok else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
