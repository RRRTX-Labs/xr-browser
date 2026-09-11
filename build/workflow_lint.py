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
  3. the file must parse as YAML and declare `jobs`;
  4. (P10-T0-a) every `uses:` is pinned to a full 40-hex commit SHA and
     carries its version comment — floating tags (`@v4`), branch names
     (`@main`) and short SHAs are a supply-chain compromise waiting, and
     the enforcement previously lived only in this docstring's claim,
     which is the worst kind of comment;
  5. (P10-T0-a) every job declares `permissions:` (least privilege;
     `write-all` is refused outright) and `timeout-minutes` (a job
     without a backstop can wedge a runner for 6 hours);
  6. (P11-T0-c) the required-grants table in build/workflow_grants.py —
     empirical permission rules (artifact path law, push/gh write verbs =>
     their scopes, over-grant detection). Its docstring records the
     refuted `actions: write` hypothesis from the phase brief, with the
     job-log proof (run 34574063042 / job 103182443929).

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

import yaml  # P10-T0-a: module-level — check_supply_chain parses jobs too

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import emit, main_with_guard, repo_root  # noqa: E402
import skip_policy  # noqa: E402
from workflow_grants import check_grants  # noqa: E402 — P11-T0-c table

ACTIONLINT = "actionlint"
EXPR_RE = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
# P10-T0-a: supply-chain rules. A `uses:` must be `owner/repo[@/sub][@<40hex>]`
# with the version comment on the same line; local `./` actions are this
# repo's own code and need no third-party pin; `docker://` must be
# digest-pinned. Raw-line matching is required because the version comment
# is a YAML comment and never reaches the parsed document.
USES_LINE_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(\s+#.*)?\s*$")
ACTION_PIN_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[0-9a-f]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-f]{64}$")


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


def check_supply_chain(text: str, rel: str) -> list[str]:
    """P10-T0-a rules: pinned uses:, version comment, job permissions+timeout.

    Returns human-readable findings. Deliberately stricter than GitHub: a
    floating `uses:` works fine until the day a release workflow is the
    thing floating — P10 is exactly where that becomes the compromise.
    """
    fails: list[str] = []

    for lineno, line in enumerate(text.splitlines(), 1):
        m = USES_LINE_RE.match(line)
        if not m:
            continue
        value, comment = m.group(1), (m.group(2) or "").strip()
        if value.startswith("./"):
            continue  # local composite/reusable action: our own reviewed code
        if value.startswith("docker://"):
            if not DOCKER_DIGEST_RE.match(value):
                fails.append(
                    f"{rel}:{lineno}: uses: {value!r} is a docker image "
                    f"without a sha256 digest pin — supply-chain rule "
                    f"(plan §9.11) requires image@sha256:<64-hex>")
            continue
        if not ACTION_PIN_RE.match(value):
            fails.append(
                f"{rel}:{lineno}: uses: {value!r} is not pinned to a full "
                f"40-hex commit SHA — floating tags (@v4), branch names "
                f"(@main) and short SHAs are rejected; pin like "
                f"actions/checkout@11d5960a326750d5838078e36cf38b85af677262 "
                f"(supply-chain discipline, plan §9.11/§13)")
            continue
        if not comment.startswith("#"):
            fails.append(
                f"{rel}:{lineno}: pinned uses: {value.split('@')[0]} lacks "
                f"the version comment on the same line (the comment is how "
                f"a reviewer sees which release the SHA names)")

    try:
        doc = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 - parse errors already reported above
        return fails
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    if not isinstance(jobs, dict):
        return fails
    for name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if "permissions" not in job:
            fails.append(
                f"{rel}: job '{name}' declares no permissions: — least "
                f"privilege requires an explicit grant (default "
                f"`permissions: contents: read`, elevations explicit)")
        elif isinstance(job["permissions"], str) and \
                job["permissions"].strip().lower() == "write-all":
            fails.append(
                f"{rel}: job '{name}' requests permissions: write-all — "
                f"refused; name the scopes you need")
        t = job.get("timeout-minutes")
        if t is None:
            fails.append(
                f"{rel}: job '{name}' declares no timeout-minutes: — a job "
                f"without a backstop can wedge a runner for hours")
        elif isinstance(t, bool) or not isinstance(t, int) or t <= 0:
            fails.append(
                f"{rel}: job '{name}' timeout-minutes must be a positive "
                f"integer, got {t!r}")
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
        text = f.read_text(encoding="utf-8")
        findings.extend(check_expressions(text, rel))
        findings.extend(check_supply_chain(text, rel))
        findings.extend(check_grants(text, rel))

    deep, skip_reason = run_actionlint(root, files)
    findings.extend(deep)

    return {
        "files": [str(f.relative_to(root)) for f in files],
        "findings": findings,
        "actionlint": skip_reason or ("ran, clean" if not deep else "ran, findings"),
        "status": "pass" if not findings else "fail",
    }


def cmd(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if getattr(args, "root", None) else repo_root()
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
    p.add_argument("--root", help="lint the workflow dir under this root instead of the repo (fixtures/negatives)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    return cmd(args)


if __name__ == "__main__":
    main_with_guard(main)
