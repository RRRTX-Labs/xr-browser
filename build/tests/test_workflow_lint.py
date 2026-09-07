"""build/tests/test_workflow_lint.py — the gate that would have caught the
workflow defect that silently disabled this repo's hosted CI from P1 to P4.

github.event.pull_request.base.sha + '..HEAD' is valid-looking YAML and valid-
looking shell, but GitHub Actions expressions have no `+`. It fails at
*compile* time, so the run ends `conclusion: failure` with zero jobs, zero logs
and zero check-runs — indistinguishable from a normal failure through the API,
and invisible to tools/run_checks.sh. These tests keep that class of bug
locally detectable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
sys.path.insert(0, str(BUILD))

import skip_policy  # noqa: E402
import workflow_lint  # noqa: E402

GOOD = """\
name: ok
on: push
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def test_shipped_workflows_pass_the_always_on_checks(tmp_path):
    for wf in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        findings = workflow_lint.check_expressions(wf.read_text(encoding="utf-8"), wf.name)
        assert findings == [], f"{wf.name}: {findings}"


def test_workflow_files_are_discovered():
    files = workflow_lint.workflow_files(REPO)
    assert files, "no workflow files found — the gate would vacuously pass"
    assert all(f.suffix in {".yml", ".yaml"} for f in files)


def test_no_plus_operator_in_any_shipped_expression():
    """The exact P1 defect (governance.yml:83, commit f7178bf)."""
    for wf in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        for path, value in workflow_lint._walk_strings(
                __import__("yaml").safe_load(text)):
            for m in workflow_lint.EXPR_RE.finditer(value):
                masked = workflow_lint._mask_string_literals(m.group(1))
                assert "+" not in masked, (
                    f"{wf.name}: {path}: '+' in {m.group(1)!r} — GitHub has no "
                    f"such operator; use format()")


def test_plus_inside_an_expression_is_caught():
    bad = GOOD.replace("echo hi", "echo hi").replace(
        "      - run: echo hi\n",
        "      - run: echo hi\n        env:\n"
        "          R: ${{ github.event.before + '..HEAD' }}\n")
    findings = workflow_lint.check_expressions(bad, "bad.yml")
    assert findings
    assert any("'+' inside an expression" in f for f in findings)
    assert any("format(" in f for f in findings), "the fix hint must be shown"


def test_plus_inside_a_string_literal_is_not_flagged():
    """False-positive guard: a '+' in a URL or a literal is fine."""
    ok = GOOD.replace("echo hi", "echo 'a+b'").replace(
        "      - run: echo hi\n",
        "      - run: echo hi\n        env:\n"
        "          R: ${{ format('{0}+{1}', 'a', 'b') }}\n")
    assert workflow_lint.check_expressions(ok, "ok.yml") == []


def test_unbalanced_expression_delimiters_are_caught():
    bad = GOOD.replace("echo hi", "echo ${{ github.sha ")
    findings = workflow_lint.check_expressions(bad, "bad.yml")
    assert any("unbalanced expression delimiters" in f for f in findings)


def test_missing_jobs_is_caught():
    findings = workflow_lint.check_expressions("name: x\non: push\n", "bad.yml")
    assert any("no `jobs:`" in f for f in findings)


def test_broken_yaml_is_reported_not_crashed():
    findings = workflow_lint.check_expressions("name: [unclosed\n", "bad.yml")
    assert findings and any("YAML parse error" in f for f in findings)


def test_actionlint_is_registered_as_an_optional_tool():
    """Keeps skip_policy / helper-tools.yaml / the gate in sync."""
    assert "actionlint" in skip_policy.EXTERNAL_TOOLS
    meta = skip_policy.EXTERNAL_TOOLS["actionlint"]
    assert "used_for" in meta and "install" in meta
    # and the dependency record must mention it too
    doc = (REPO / "docs" / "dependencies" / "helper-tools.yaml").read_text(encoding="utf-8")
    assert "name: actionlint" in doc


def test_absent_actionlint_produces_a_visible_skip_and_still_passes(monkeypatch):
    monkeypatch.setattr(skip_policy, "tool_path", lambda name: None)
    findings, skip_reason = workflow_lint.run_actionlint(REPO, [])
    assert findings == []
    assert skip_reason and skip_reason.startswith(skip_policy.SKIP_PREFIX)
    # the overall lint must still succeed on the shipped files
    result = workflow_lint.lint(REPO)
    assert result["status"] == "pass"
    assert result["actionlint"].startswith(skip_policy.SKIP_PREFIX)


@pytest.mark.skipif(skip_policy.tool_path("actionlint") is None,
                    reason=skip_policy.tool_absent_reason("actionlint") or
                    "actionlint not installed")
def test_actionlint_runs_clean_over_the_shipped_workflows():
    findings, skip_reason = workflow_lint.run_actionlint(
        REPO, workflow_lint.workflow_files(REPO))
    assert skip_reason is None
    assert findings == [], findings
