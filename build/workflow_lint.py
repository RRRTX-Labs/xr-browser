"""build/workflow_lint.py — lint .github/workflows before GitHub does (P4).

Why this exists. For the whole life of this repo every push-triggered run of
governance.yml ended `conclusion: failure` with **zero jobs**, created_at ==
updated_at. The cause was one character: `github.event.pull_request.base.sha +
'..HEAD'` at governance.yml:83. GitHub Actions expressions have no `+`
operator; a lex error is fatal at *compile* time, so the run dies before a job
is ever created — no step output, no log archive, nothing in check-runs. It
was invisible locally because nothing in tools/ or build/ parsed workflow
expressions, and `tools/run_checks.sh` passed the whole time.

So: this tool is the cheap, always-on, zero-dependency check for that bug
class, plus a passthrough to actionlint (GitHub's own expression/schema
checker) when it is installed. actionlint is optional and follows the L6 SKIP
policy — absent means a visible SKIP line, never a silent pass.

Always-on checks (no external tool required):
  1. every `${{ ... }}` must be closed;
  2. `+` inside an expression, outside a string literal: GitHub has no
     concatenation or arithmetic operator, so this is always a compile error
     (use format('{0}..HEAD', x) instead);
  3. the file must parse as YAML and declare `jobs`.

Exit: 0 pass / 1 fail / 2 usage (build tool contract).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import emit, main_with_guard, repo_root  # noqa: E402
import skip_policy  # noqa: E402

ACTIONLINT = "actionlint"
EXPR_RE = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)


def workflow_files(root: Path) -> list[Path]:
    d = root / ".github" / "workflows"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.suffix in {".yml", ".yaml"} and p.is_file())


def _mask_string_literals(expr: str) -> str:
    """Blank out '...' literals so operators inside strings are not flagged."""
    out: list[str] = []
    in_str = False
    i = 0
    while i < len(expr):
        c = expr[i]
        if c == "'":
            # '' is an escaped single quote inside a literal
            if in_str and i + 1 < len(expr) and expr[i + 1] == "'":
                out.append("  ")
                i += 2
                continue
            in_str = not in_str
            i += 1
            continue
        out.append(" " if in_str else c)
        i += 1
    return "".join(out)


def _walk_strings(node: Any) -> list[tuple[str, str]]:
    """Return (path, string) for every string in a nested YAML structure."""
    found: list[tuple[str, str]] = []

    def rec(n: Any, path: str) -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                rec(v, f"{path}.{k}")
        elif isinstance(n, list):
            for i, v in enumerate(n):
                rec(v, f"{path}[{i}]")
        elif isinstance(n, str):
            found.append((path, n))

    rec(node, "$")
    return found


def check_expressions(text: str, rel: str) -> list[str]:
    """The always-on checks. Returns human-readable findings."""
    fails: list[str] = []

    # 1. balanced ${{ ... }}
    opens = text.count("${{")
    closes = text.count("}}")
    if opens != closes:
        fails.append(f"{rel}: unbalanced expression delimiters — {opens} '${{' "
                     f"vs {closes} '}}' (a stray one is a compile error, and "
                     f"GitHub reports it as a run with zero jobs)")

    # 2/3. per-expression operator checks
    import yaml
    try:
        doc = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 - report, do not crash
        fails.append(f"{rel}: YAML parse error: {exc}")
        return fails

    if isinstance(doc, dict) and not doc.get("jobs"):
        fails.append(f"{rel}: no `jobs:` — GitHub will not create a run")

    for path, value in _walk_strings(doc):
        for m in EXPR_RE.finditer(value):
            expr = m.group(1)
            masked = _mask_string_literals(expr)
            if "+" in masked:
                col = masked.index("+")
                fails.append(
                    f"{rel}: {path}: '+' inside an expression — GitHub "
                    f"expressions have no concatenation or arithmetic "
                    f"operator; use format('{{0}}..HEAD', x) "
                    f"(expression: {expr.strip()[:70]!r}; "
                    f"this is fatal at compile time: the run fails with zero "
                    f"jobs and no logs, which is exactly how P1..P4 lost every "
                    f"hosted run)")
            if masked.count("(") != masked.count(")"):
                fails.append(f"{rel}: {path}: unbalanced parentheses in "
                             f"expression: {expr.strip()[:70]!r}")
    return fails


def run_actionlint(root: Path, files: list[Path]) -> tuple[list[str], str | None]:
    """Deep check via actionlint. Returns (findings, skip_reason)."""
    path = skip_policy.tool_path(ACTIONLINT)
    if not path:
        return [], skip_policy.tool_absent_reason(ACTIONLINT)
    proc = subprocess.run(
        [path, "-no-color", *[str(f) for f in files]],
        cwd=str(root), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return [], None
    lines = [l for l in out.splitlines() if l.strip()]
    return [f"actionlint: {l}" for l in lines] or \
        [f"actionlint failed (exit {proc.returncode}) with no output"], None


def lint(root: Path, files: list[Path] | None = None) -> dict[str, Any]:
    files = files or workflow_files(root)
    if not files:
        return {"files": [], "findings": [], "actionlint": "no workflow files",
                "status": "pass"}

    findings: list[str] = []
    for f in files:
        rel = str(f.relative_to(root)) if f.is_absolute() else str(f)
        findings.extend(check_expressions(f.read_text(encoding="utf-8"), rel))

    deep, skip_reason = run_actionlint(root, files)
    findings.extend(deep)

    return {
        "files": [str(f.relative_to(root)) for f in files],
        "findings": findings,
        "actionlint": skip_reason or ("ran, clean" if not deep else "ran, findings"),
        "status": "pass" if not findings else "fail",
    }


def cmd(args: argparse.Namespace) -> int:
    root = repo_root()
    result = lint(root)
    if getattr(args, "json", False):
        emit(True, result, failures=result["findings"])
        return 0 if result["status"] == "pass" else 1
    else:
        for f in result["files"]:
            print(f"  checked: {f}")
        print(f"  actionlint: {result['actionlint']}")
        for finding in result["findings"]:
            print(f"  FAIL: {finding}")
        if result["status"] == "pass":
            print("PASS: workflow-lint")
        else:
            print(f"FAIL: workflow-lint ({len(result['findings'])} finding(s))")
    return 0 if result["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="workflow-lint", description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return p


def main() -> int:
    args = build_parser().parse_args()
    return cmd(args)


if __name__ == "__main__":
    main_with_guard(main)
