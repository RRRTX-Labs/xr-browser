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


# ---------------------------------------------------------------------------
# P10-T0-a: the supply-chain rules are code now, not a docstring claim.
# ---------------------------------------------------------------------------

WF_PINNED = """\
name: ok
on: push
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
        with:
          fetch-depth: 0
      - run: echo hi
"""


def test_shipped_workflows_pass_supply_chain_checks():
    for wf in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        findings = workflow_lint.check_supply_chain(wf.read_text(encoding="utf-8"), wf.name)
        assert findings == [], f"{wf.name}: {findings}"


def test_pinned_workflow_with_comment_passes():
    assert workflow_lint.check_supply_chain(WF_PINNED, "ok.yml") == []


def test_floating_tag_is_rejected():
    bad = WF_PINNED.replace(
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "actions/checkout@v4")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("not pinned to a full 40-hex" in f for f in findings), findings


def test_branch_ref_is_rejected():
    bad = WF_PINNED.replace(
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "actions/checkout@main")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("not pinned to a full 40-hex" in f for f in findings), findings


def test_short_sha_is_rejected():
    bad = WF_PINNED.replace(
        "@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "@11d5960 # v4.4.0")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("not pinned to a full 40-hex" in f for f in findings), findings


def test_missing_version_comment_is_rejected():
    bad = WF_PINNED.replace(
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("lacks the version comment" in f for f in findings), findings


def test_local_action_needs_no_pin():
    ok = WF_PINNED.replace(
        "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "uses: ./.github/actions/local-step")
    assert workflow_lint.check_supply_chain(ok, "ok.yml") == []


def test_docker_without_digest_is_rejected():
    bad = WF_PINNED.replace(
        "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        "uses: docker://alpine:latest")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("sha256 digest" in f for f in findings), findings


def _jobless(template: str, drop: str) -> str:
    return template.replace(drop, "")


def test_missing_permissions_is_rejected():
    bad = _jobless(WF_PINNED, "    permissions:\n      contents: read\n")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("declares no permissions:" in f for f in findings), findings


def test_write_all_permissions_is_rejected():
    bad = WF_PINNED.replace("      contents: read\n", "      write-all\n")
    # write-all may be spelled as the bare string form too
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("write-all" in f for f in findings), findings


def test_missing_timeout_is_rejected():
    bad = _jobless(WF_PINNED, "    timeout-minutes: 10\n")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("declares no timeout-minutes:" in f for f in findings), findings


def test_non_integer_timeout_is_rejected():
    bad = WF_PINNED.replace("timeout-minutes: 10", "timeout-minutes: forever")
    findings = workflow_lint.check_supply_chain(bad, "bad.yml")
    assert any("positive integer" in f for f in findings), findings
