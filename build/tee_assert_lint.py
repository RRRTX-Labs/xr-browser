#!/usr/bin/env python3
"""build/tee_assert_lint.py — a `| tee` must not be able to swallow a verdict
(P12-T0-c).

Root cause. ``core-hardening.yml`` ran::

    cargo test --locked 2>&1 | tee /tmp/rust-conformance.log
    grep -q "test result: ok" /tmp/rust-conformance.log

Cargo prints one ``test result:`` line PER SUITE, so a job in which three of
four suites fail still satisfies ``grep -q``. Worse, the pipe's exit status is
``tee``'s, not ``cargo``'s — without ``set -o pipefail`` the failing command's
status is discarded outright. A silently swallowed exit code is the oldest way
a green CI lies, and P11 already learned the lesson for its parity step
(``--check`` plus ``grep -q '"verdict": "PASS"'``). This module finishes the
sweep and turns it into a rule.

Law: a step whose ``run`` block pipes a VERDICT-BEARING command into ``tee``
or a redirect must satisfy at least one of:

  (a) ``set -o pipefail`` (or ``set -euo pipefail``) appears in the block, so
      the pipe propagates the real exit status; or
  (b) the block carries an explicit NEGATIVE assertion on the captured output
      — ``! grep -q … FAILED``, a ``test result:`` suite-count comparison, or
      an equivalent ``assert`` — so a partial success cannot satisfy it.

Verdict-bearing means the command is one that reports a pass/fail result:
``cargo``, ``pytest``, ``make``, any ``tools/*.py``, any ``build/*.py``, any
``./scripts/build``. Cosmetic pipes (``| tee`` on ``echo``, ``cat``, ``ls``)
are not in scope.

Zero-case law: a run in which NO pipe was inspected certifies nothing, so
``--require-pipes N`` (default 1) fails when the expected pipes vanish —
otherwise deleting every ``tee`` would "pass" this lint by removing its input.

Usage:  python3 build/tee_assert_lint.py [--root .] [--json] [--self-test]
Exit: 0 pass · 1 fail · 2 usage. Stdlib only (PyYAML, already pinned).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# Commands whose exit status IS a verdict.
VERDICT_CMDS = ("cargo", "pytest", "python3 -m pytest", "make",
                "./scripts/build", "tools/", "build/", "python3 tools/",
                "python3 build/")
# A pipe sink that captures output for later grepping.
SINK_RE = re.compile(r"\|\s*tee\b|>\s*/tmp/|>>\s*/tmp/")
PIPEFAIL_RE = re.compile(r"set\s+(?:-[a-zA-Z]*o\s+pipefail|-euo\s+pipefail"
                         r"|-eo\s+pipefail)")
# An explicit negative assertion on the captured output.
NEGATIVE_ASSERT_RE = re.compile(
    r"!\s*grep\b"                       # ! grep -q "... FAILED"
    r"|grep\s+-c\b[^\n]*\btest result"  # suite-count comparison
    r"|assert\b"                        # python assert on the parsed report
    r"|grep\s+-q\s+[\"'][^\"']*FAILED"  # an explicit FAILED hunt
)


def _steps(doc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(job, step name, run block) for every run step."""
    out: list[tuple[str, str, str]] = []
    for jname, job in (doc.get("jobs") or {}).items():
        for i, step in enumerate(job.get("steps") or []):
            run = step.get("run")
            if isinstance(run, str) and run.strip():
                out.append((jname, step.get("name") or f"step[{i}]", run))
    return out


def _logical_lines(block: str) -> list[str]:
    """Join backslash-continued lines into one logical command.

    Scanning RAW lines under-counts: a verdict-bearing command written across
    a `\\` continuation (the bench and parity steps in core-hardening.yml)
    puts the command on one physical line and `| tee` on the next, so a
    per-line test sees a sink with no verdict command and skips it. That is
    the invisibility class this module exists to close, so it must not commit
    it: two of the five real pipes were being missed before this.
    """
    out: list[str] = []
    buf = ""
    for line in block.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        if buf.strip():
            out.append(buf.strip())
        buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _verdict_lines(block: str) -> list[str]:
    """Logical commands that pipe a verdict-bearing command into a sink."""
    hits: list[str] = []
    for line in _logical_lines(block):
        if not SINK_RE.search(line):
            continue
        if any(c in line for c in VERDICT_CMDS):
            hits.append(line.strip())
    return hits


def check_workflow(path: Path, root: Path) -> tuple[list[str], int]:
    """(violations, pipes_inspected)."""
    import yaml
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return [f"{path}: unparseable YAML ({exc})"], 0
    rel = path.relative_to(root) if root in path.parents else path
    fails: list[str] = []
    n = 0
    for job, step, block in _steps(doc):
        hits = _verdict_lines(block)
        if not hits:
            continue
        n += len(hits)
        has_pipefail = bool(PIPEFAIL_RE.search(block))
        has_negative = bool(NEGATIVE_ASSERT_RE.search(block))
        if has_pipefail or has_negative:
            continue
        shape = "pipefail" if has_pipefail else "negative assert"
        for line in hits:
            fails.append(
                f"{rel}: job `{job}` step `{step}`: a verdict-bearing command "
                f"is piped into a capturing sink with neither `set -o "
                f"pipefail` nor a negative assertion — the exit status is "
                f"swallowed and a partial success can satisfy the grep: "
                f"`{line[:90]}`")
    return fails, n


def lint(root: Path) -> tuple[list[str], int, int]:
    """(violations, pipes_inspected, workflows_scanned)."""
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return [f"{wf}: no workflows directory"], 0, 0
    fails: list[str] = []
    pipes = 0
    files = sorted(wf.glob("*.yml")) + sorted(wf.glob("*.yaml"))
    for f in files:
        f_fails, n = check_workflow(f, root)
        fails += f_fails
        pipes += n
    return fails, pipes, len(files)


def _self_test(root: Path) -> int:
    """The rule must redden on an unguarded tee and stay green on both
    permitted shapes — a lint that cannot fail certifies nothing."""
    import tempfile
    import yaml
    results: dict[str, bool] = {}
    bad = {
        "jobs": {"j": {"steps": [{"name": "s", "run":
            "cargo test --locked 2>&1 | tee /tmp/t.log\n"
            "grep -q \"test result: ok\" /tmp/t.log\n"}]}}}
    good_pipefail = {
        "jobs": {"j": {"steps": [{"name": "s", "run":
            "set -euo pipefail\n"
            "cargo test --locked 2>&1 | tee /tmp/t.log\n"}]}}}
    good_negative = {
        "jobs": {"j": {"steps": [{"name": "s", "run":
            "cargo test --locked 2>&1 | tee /tmp/t.log\n"
            "grep -q \"test result: ok\" /tmp/t.log\n"
            "! grep -q \"test result: FAILED\" /tmp/t.log\n"}]}}}
    cosmetic = {
        "jobs": {"j": {"steps": [{"name": "s", "run":
            "echo hello | tee /tmp/t.log\n"}]}}}
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        for name, doc, expect in (("bad", bad, 1),
                                  ("pipefail", good_pipefail, 0),
                                  ("negative", good_negative, 0),
                                  ("cosmetic", cosmetic, 0)):
            p = t / f"{name}.yml"
            p.write_text(yaml.safe_dump(doc), encoding="utf-8")
            f, n = check_workflow(p, t)
            results[f"{name}_shape"] = (len(f) == expect)
    badk = [k for k, v in results.items() if not v]
    if badk:
        print(f"FAIL: tee_assert_lint self-test — {sorted(badk)}")
        return EXIT_FAIL
    print(f"PASS: tee_assert_lint self-test ({len(results)} pipe shapes "
          f"discriminated: unguarded red, pipefail green, negative-assert "
          f"green, cosmetic pipe out of scope)")
    return EXIT_PASS


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="tee_assert_lint",
                                description=__doc__.splitlines()[0])
    p.add_argument("--root", default=".")
    p.add_argument("--require-pipes", type=int, default=1,
                   help="fail if fewer than N verdict-bearing pipes were "
                        "inspected (zero-case law: deleting every tee must "
                        "not 'pass' this lint)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    if a.self_test:
        return _self_test(root)
    fails, pipes, nfiles = lint(root)
    if pipes < a.require_pipes:
        fails.append(f"zero-case: only {pipes} verdict-bearing pipe(s) "
                     f"inspected across {nfiles} workflow(s), fewer than the "
                     f"required {a.require_pipes} — the input this lint "
                     f"judges has vanished")
    if a.json:
        print(json.dumps({"tool": "tee_assert_lint", "workflows": nfiles,
                          "pipes_inspected": pipes, "violations": fails},
                         sort_keys=True, indent=2))
    if fails:
        print(f"FAIL: tee_assert_lint — {len(fails)} violation(s) across "
              f"{nfiles} workflow(s), {pipes} pipe(s) inspected:")
        for f in fails:
            print(f"  {f}")
        return EXIT_FAIL
    print(f"PASS: tee_assert_lint ({nfiles} workflow(s), {pipes} "
          f"verdict-bearing pipe(s) inspected; every one carries pipefail or "
          f"a negative assertion — no exit status can be swallowed)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
