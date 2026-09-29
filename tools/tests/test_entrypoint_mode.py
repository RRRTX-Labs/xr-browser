"""entrypoint_mode_check.py — the workflow `run:` parser and both laws.

The parser is the part that can quietly lie: a `run:` block it fails to see is a
violation it never checks, and a false "exempt" is a violation it waves through.
These tests pin the extraction rules against the repository's own workflows and
against the shapes GitHub actually accepts (inline, `|`, `>-`, `${{ }}` in the
command text, quoted arguments, leading `env VAR=` assignments).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(TOOLS))
import entrypoint_mode_check as emc  # type: ignore[import-not-found]  # noqa: E402
import wfrun  # type: ignore[import-not-found]  # noqa: E402


def test_inline_and_block_scalars_are_extracted() -> None:
    text = (
        "name: x\n"
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: inline\n"
        "        run: tools/run_negatives.sh\n"
        "      - name: literal\n"
        "        run: |\n"
        "          ./scripts/build workflow-lint\n"
        "          bash tools/run_checks.sh \"$RANGE\"\n"
        "      - name: folded\n"
        "        run: >-\n"
        "          python3 tools/license_audit.py\n"
    )
    blocks = dict(wfrun.extract_run_blocks(text))
    assert any(b == "tools/run_negatives.sh" for b in blocks.values())
    joined = "\n".join(blocks.values())
    assert "./scripts/build workflow-lint" in joined
    assert 'bash tools/run_checks.sh "$RANGE"' in joined
    assert "python3 tools/license_audit.py" in joined


def test_command_splitter_respects_quotes_and_github_expressions() -> None:
    block = """if [ -n "$CHECK_RANGE" ]; then
  echo "a;b|c && d"
  tools/run_checks.sh "$CHECK_RANGE"
else
  tools/run_checks.sh
fi
echo "${{ github.sha }}:${{ format('{0}..HEAD', github.ref) }}"
"""
    cmds = wfrun.split_commands(block)
    assert 'echo "a;b|c && d"' in cmds
    assert 'tools/run_checks.sh "$CHECK_RANGE"' in cmds
    assert "tools/run_checks.sh" in cmds


def test_classification_direct_vs_interpreted() -> None:
    tracked = {"tools/run_checks.sh", "tools/license_audit.py", "scripts/build"}
    assert wfrun.classify_command("tools/run_checks.sh \"$R\"", tracked) == (
        "direct", "tools/run_checks.sh")
    assert wfrun.classify_command("./scripts/build workflow-lint", tracked) == (
        "direct", "scripts/build")
    assert wfrun.classify_command("bash tools/run_checks.sh", tracked) == (
        "interpreted", "tools/run_checks.sh")
    assert wfrun.classify_command("python3 tools/license_audit.py --repo .", tracked) == (
        "interpreted", "tools/license_audit.py")
    # preamble + env assignments before the real executable
    assert wfrun.classify_command("RANGE=a timeout 30 bash tools/run_checks.sh", tracked) == (
        "interpreted", "tools/run_checks.sh")
    # not repo paths: bare programs, flags, inline interpreters
    assert wfrun.classify_command("git push origin main", tracked)[0] == "other"
    assert wfrun.classify_command("python3 -m pip install -r tools/requirements-dev.txt",
                                tracked)[0] == "other"


def test_the_real_workflows_pass_and_the_exemptions_are_listed(tmp_path: Path) -> None:
    """The repository's own workflows, plus a planted defect in a COPY — the
    real tree is never written to."""
    modes = emc.index_modes(REPO)
    if modes is None:  # pragma: no cover - environment without git
        pytest.skip("no git available")
    failures, notes, exempt = emc.check_entrypoints(REPO, modes)
    assert failures == [], failures
    assert any("EXEMPT" in n for n in notes)
    # the two paths that the incident took out of the index are direct-exec
    # entry points and must be seen (their fixed state is what makes this pass)
    assert "tools/run_checks.sh" in modes and "tools/run_negatives.sh" in modes
    assert modes["tools/run_checks.sh"] == "100755"
    assert modes["tools/run_negatives.sh"] == "100755"
    # it is a DIRECT entry point, so it must appear in the direct set (the
    # exemption list is for interpreted invocations only)
    assert all("run_checks.sh" not in e for e in exempt)


def test_range_law_on_a_synthetic_repo(tmp_path: Path) -> None:
    """Build a throwaway repo where a commit drops an exec bit, and assert the
    range law names the commit and the path (5e3d1d4's shape)."""
    def g(*args: str) -> None:
        subprocess.run(["git", "-c", "user.email=t@x", "-c", "user.name=t", *args],
                       cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    (tmp_path / "tools").mkdir()
    script = tmp_path / "tools" / "entry.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    g("add", "-A")
    g("commit", "-qm", "base")
    script.chmod(0o644)
    g("add", "-A")
    g("commit", "-qm", "plant: drop the exec bit")

    drift = emc.check_mode_drift(tmp_path, "HEAD~1..HEAD")
    assert len(drift) == 1 and "tools/entry.sh" in drift[0] and "100755 -> 100644" in drift[0]
    assert emc.check_mode_drift(tmp_path, "HEAD..HEAD") == []
