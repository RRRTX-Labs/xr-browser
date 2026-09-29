"""gate_annotation.py — the emitted line format (P13-P0-B, the act-less harness).

The brief's negative for P0-B: "a lane forced to fail in a local `act`-less
harness — i.e. a unit test on the emitted line format — must prove the
annotation text contains the lane name." That is exactly this file: a synthetic
gate transcript is fed in, the emitted workflow command is asserted on its
shape, and the no-failure case is asserted to refuse rather than invent a cause.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]

ANNOTATION_RE = re.compile(r"^::error::[A-Za-z0-9._/-]+: .+ - .+$")

KEEP_GOING_LOG = """\
== P9-T5: perf budgets (plan-transcribed, diff-clean) + gate ==
PASS: perf budgets
== spike: every file:line citation re-verified at the pin ==
FAIL: citation-audit (BLOCKED-NET: 23 citations unreachable from this sandbox)
LANE FAIL (keep-going): python3 build/spike/citation_audit.py
== P8-T6: attention-budget policy of record ==
PASS: attention_check
FAIL: 1 lane(s) failed
"""

PLAIN_FAIL_LOG = """\
== build-system gates ==
PASS: provenance
FAIL: brand-check: 2 endpoint-deny violations in build/gn
"""

EMPTY_LOG = """\
== plan pin ==
PASS: plan_pin_check
"""


def _run(tmp_path: Path, text: str, lane: str = "governance", extra: list[str] | None = None):
    log = tmp_path / "gate.log"
    log.write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(TOOLS / "gate_annotation.py"), "--lane", lane,
         "--log", str(log), *(extra or [])],
        capture_output=True, text=True)


def test_emitted_line_names_the_lane_and_the_first_failing_gate(tmp_path: Path) -> None:
    proc = _run(tmp_path, KEEP_GOING_LOG)
    assert proc.returncode == 0
    line = proc.stdout.strip()
    assert ANNOTATION_RE.match(line), f"format drifted: {line!r}"
    assert line.startswith("::error::governance: "), line
    assert "citation_audit.py" in line, "the failing gate is not named"
    assert "BLOCKED-NET" in line, "the one-line reason is missing"
    # the taxonomy itself: the keep-going tally outranks the trailing tally line
    assert "1 lane(s) failed" not in line


def test_plain_fail_line_is_used_when_the_tally_is_absent(tmp_path: Path) -> None:
    proc = _run(tmp_path, PLAIN_FAIL_LOG, lane="core-hardening")
    assert proc.returncode == 0
    line = proc.stdout.strip()
    assert line.startswith("::error::core-hardening: ")
    assert "brand-check" in line and "endpoint-deny" in line


def test_no_failure_refuses_to_invent_a_cause(tmp_path: Path) -> None:
    proc = _run(tmp_path, EMPTY_LOG)
    assert proc.returncode == 1, "a clean log must not produce a failure annotation"
    line = proc.stdout.strip()
    assert line.startswith("::error::governance: gate failed - ")
    assert "reason unavailable" in line


def test_json_shape_matches_the_text_output(tmp_path: Path) -> None:
    proc = _run(tmp_path, KEEP_GOING_LOG, extra=["--json"])
    assert proc.returncode == 0
    import json
    doc = json.loads(proc.stdout)
    assert doc["lane"] == "governance"
    assert doc["source"] == "keep-going tally"
    assert doc["annotation"].startswith("::error::governance: ")


def test_workflow_commands_are_single_line_and_escaped(tmp_path: Path) -> None:
    log = tmp_path / "gate.log"
    log.write_text("FAIL: a reason with a % and a \n continuation\n", encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(TOOLS / "gate_annotation.py"), "--lane", "l",
         "--log", str(log)], capture_output=True, text=True)
    line = out.stdout.rstrip("\n")
    assert line.count("\n") == 0
    assert "%25" in line and " unescaped" not in line.replace("a reason with a %25", "")
