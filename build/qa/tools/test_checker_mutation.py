#!/usr/bin/env python3
"""build/qa/tools/test_checker_mutation.py — mutation-check the checker (P9).

Plan P9, "Tests: meta-tests: mutation-check the checker". A runner whose
canary can be silently deleted proves nothing. For each target runner below
we (1) run its canary fixture through the REAL runner and assert it trips
(rc != 0, expected reason), then (2) inject ONE documented defect into a
COPY of the runner's source and assert the same canary now ESCAPES (rc == 0).
An escaping canary proves the checker was load-bearing; a mutation that does
not escape means the runner is already broken (or the defect was ill-chosen)
and this tool exits 1.

Offline, stdlib-only (the canary fixtures are authored here as literals, so
no yaml dependency). Exit: 0 = every mutation escaped its canary (the suite
would turn red on a real defect) · 1 = a mutation failed to escape or a
control failed · 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import re
import tempfile
from pathlib import Path

# Each target: the runner, the textual defect (find -> replace, first match),
# a factory that writes the canary fixture into a temp dir and returns the
# argv for the runner, and the reason the control run must print.
# (name, defect_find, defect_replace, fixture_fn(workdir, repo) -> argv,
#  expect_reason)
TARGETS = [
    # 1. perf_gate — an always-true budget compare turns every regression
    #    into MET. Canary: a 10x-over-budget bench that MUST MISS.
    (
        "tools/perf_gate.py",
        "        if value <= budget:\n",
        "        if True:  # MUTATED: budget compare always MET\n",
        "perf_gate",
        "MISSED",
    ),
    # 2. surfaces_check — deleting the homeless-surface branch lets a §11
    #    surface with no home pass (the phase's worst possible outcome).
    (
        "tools/surfaces_check.py",
        "        else:\n            fails.append(f\"{sid}: no home (stop-condition)\")\n",
        "        elif False:  # MUTATED: homeless surface never flagged\n            fails.append(f\"{sid}: no home (stop-condition)\")\n",
        "surfaces_check",
        "no home",
    ),
    # 3. evidence_check — removing the not_done_by_design invariant lets a
    #    PARTIAL/BLOCKED/HUMAN-GATED row ship without an explanation (P8's
    #    hole).
    (
        "tools/evidence_check.py",
        "        if any(_is_open_status(str(r.get(\"status\", \"\"))) for r in rows):\n",
        "        if False and any(_is_open_status(str(r.get(\"status\", \"\"))) for r in rows):\n",
        "evidence_check",
        "not_done_by_design",
    ),
]

# ---------------------------------------------------------------------------
# canary fixtures
# ---------------------------------------------------------------------------
_PERF_BENCH = (
    '{"name":"canary","rig_class":"trend","unit":"us","rows":'
    '[{"metric":"resolve_cold_us","value_us":999999.0,"unit":"us"}]}'
)

_SURFACES_CANARY = """schema_version: 1
surfaces:
{s}
  - id: "11.5"
    name: vault suite
    green: "KDBX golden corpus (P28)"
"""


def _surfaces_body() -> str:
    """14 well-homed manual surfaces + one (11.5) with NO home key at all."""
    rows = []
    for i in range(1, 16):
        if i == 5:
            continue
        rows.append(f'  - id: "11.{i}"\n'
                    f'    name: s{i}\n'
                    f'    home: manual\n'
                    f'    green: "g{i}"\n'
                    f'    rows:\n'
                    f'      - {{item: i, owner: o, cadence: q}}')
    return _SURFACES_CANARY.format(s="\n".join(rows))


def _evidence_bundle(workdir: Path) -> tuple[str, ...]:
    d = workdir / "ev" / "evidence" / "P9"
    d.mkdir(parents=True)
    (d / "human-gates.md").write_text("# P9 gates\n\nfarm rows.\n",
                                      encoding="utf-8")
    (d / "evidence.json").write_text(json.dumps({
        "phase": "P9", "generated": "2026-01-01", "plan": "p",
        "not_done_by_design": [],
        "dod_rows": [{"id": "D1", "dod": "x", "status": "BLOCKED-NET",
                      "evidence": ["HG-31"]}],
    }), encoding="utf-8")
    return ("--repo", str(workdir / "ev"), "--strict", "--only", "P9")


def _fixture(kind: str, workdir: Path, repo: Path) -> list[str]:
    if kind == "perf_gate":
        p = workdir / "bench.json"
        p.write_text(_PERF_BENCH, encoding="utf-8")
        return ["--repo", str(repo), "--bench", str(p)]
    if kind == "surfaces_check":
        p = workdir / "surfaces.yaml"
        p.write_text(_surfaces_body(), encoding="utf-8")
        return ["--repo", str(repo), "--surfaces", str(p)]
    if kind == "evidence_check":
        return list(_evidence_bundle(workdir))
    raise AssertionError(kind)


def _mutated_copy(repo: Path, workdir: Path, runner_rel: str,
                  find: str, replace: str) -> Path:
    """Copy the runner into a temp tools/ dir (build/ symlinked so package
    imports resolve), then apply the defect. Returns the mutated path."""
    src = repo / runner_rel
    dest = workdir / "tools" / Path(runner_rel).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    # same-dir sibling modules the runner imports (P10-T0-d split:
    # evidence_check imports evidence_ci) must travel with the copy.
    # P11-T4 fix (research-log-P11.md D6): T0-d gave evidence_check a
    # BARE `import runner_caps` — the from-form-only regex missed it and
    # every mutated copy crashed with ModuleNotFoundError (the meta-gate
    # reddened, masked in earlier runs by fatal gates ahead of it). Both
    # import forms are tracked now; `sib.exists()` keeps stdlib imports
    # (json, re, sys, …) out.
    src_text = src.read_text(encoding="utf-8")
    sib_names = re.findall(r"^from (\w+) import ", src_text, flags=re.M)
    sib_names += re.findall(r"^import (\w+)\s*(?:#|$)", src_text, flags=re.M)
    for m in sib_names:
        sib = src.parent / f"{m}.py"
        if sib.exists():
            (dest.parent / sib.name).write_text(
                sib.read_text(encoding="utf-8"), encoding="utf-8")
    text = src.read_text(encoding="utf-8")
    assert find in text, f"defect anchor not found in {runner_rel}"
    assert text.count(find) == 1, f"defect anchor not unique in {runner_rel}"
    dest.write_text(text.replace(find, replace, 1), encoding="utf-8")
    return dest


def _run(repo: Path, argv: list[str], workdir: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *argv], cwd=str(repo),
                       capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + "\n" + r.stderr)


def _ensure_links(workdir: Path, repo: Path) -> None:
    (workdir / "build").symlink_to(repo / "build", target_is_directory=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    results = []
    failures = []
    for runner_rel, find, replace, kind, reason in TARGETS:
        with tempfile.TemporaryDirectory(prefix="chk-mut-") as td:
            workdir = Path(td)
            _ensure_links(workdir, repo)
            canary_argv = _fixture(kind, workdir, repo)
            # control: the real runner trips the canary
            rc_ctl, out_ctl = _run(repo, [str(repo / runner_rel), *canary_argv],
                                   workdir)
            if rc_ctl == 0 or reason not in out_ctl:
                failures.append(
                    f"{runner_rel}: control canary did not trip "
                    f"(rc={rc_ctl}); output:\n{out_ctl[-800:]}")
                results.append({"runner": runner_rel, "control": "FAIL",
                                "mutation": "skipped"})
                continue
            # mutation: the defect must let the canary escape
            mutated = _mutated_copy(repo, workdir, runner_rel, find, replace)
            rc_mut, out_mut = _run(repo, [str(mutated), *canary_argv], workdir)
            if rc_mut != 0:
                failures.append(
                    f"{runner_rel}: mutation did not escape the canary "
                    f"(rc={rc_mut}); output:\n{out_mut[-800:]}")
                results.append({"runner": runner_rel, "control": "tripped",
                                "mutation": "FAIL (still red)"})
            else:
                results.append({"runner": runner_rel, "control": "tripped",
                                "mutation": "escaped"})

    if args.json:
        print(json.dumps({"tool": "test_checker_mutation",
                          "targets": len(TARGETS),
                          "results": results,
                          "status": "pass" if not failures else "fail"},
                         sort_keys=True, indent=2))
    else:
        for r in results:
            print(f"{r['runner']}: control={r['control']}, "
                  f"mutation={r['mutation']}")
        print(f"test_checker_mutation: {len(TARGETS)} target(s), "
              f"{len(failures)} failure(s) "
              f"({'PASS' if not failures else 'FAIL'})")
        for f in failures:
            print(f"FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
