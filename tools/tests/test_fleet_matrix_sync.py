"""The fuzz-fleet sync law (P14-CLOSE): the hosted fuzz-fleet matrix runs
EVERY target in build/fuzz/fleet.yaml, and builds every make-test target's
lane before the timebox step.

Root cause it closes: P14-T1 added `identity-core` to fleet.yaml (six
targets) while .github/workflows/core-hardening.yml kept its hand-written
five-entry matrix, so the identity fuzzer never ran hosted and nothing
reddened. The set is now DERIVED from fleet.yaml at test time. There is no
count literal anywhere: a seventh target (P15 permissions-overlay) that
lands in fleet.yaml without its matrix entry and build line fails here.
The planted negative removes a core from the parsed workflow and requires
the law to name it.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "core-hardening.yml"
FLEET = REPO / "build" / "fuzz" / "fleet.yaml"


def _load() -> tuple[dict, dict]:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    fleet = yaml.safe_load(FLEET.read_text(encoding="utf-8"))
    return wf, fleet


def sync_failures(wf: dict, fleet: dict) -> list[str]:
    """Every way the hosted matrix can drift from the fleet, as named lines."""
    fails: list[str] = []
    job = wf.get("jobs", {}).get("fuzz-fleet")
    if not job:
        return ["core-hardening.yml has no fuzz-fleet job"]
    matrix = list(job.get("strategy", {}).get("matrix", {}).get("target", []))
    ids = [t["id"] for t in fleet.get("targets", [])]
    if not ids:
        fails.append("fleet.yaml lists no targets (zero-case law)")
    for tid in ids:
        if tid not in matrix:
            fails.append(f"fleet target {tid} is missing from the fuzz-fleet matrix")
    for tid in matrix:
        if tid not in ids:
            fails.append(f"matrix entry {tid} is not a fleet.yaml target")
    if len(matrix) != len(set(matrix)):
        fails.append("fuzz-fleet matrix lists a target twice")
    build_cmds: set[tuple[str, ...]] = set()
    for step in job.get("steps", []):
        for line in str(step.get("run", "")).splitlines():
            words = line.split("#", 1)[0].split()
            if words[:2] == ["make", "-C"]:
                build_cmds.add(tuple(words[2:]))
    for t in fleet.get("targets", []):
        if t.get("runner") == "make-test" and \
                (t["runner_makefile"], "build") not in build_cmds:
            fails.append(f"fleet target {t['id']}: no `make -C {t['runner_makefile']} "
                         f"build` before the timebox step")
    run = " ".join(str(s.get("run", "")) for s in job.get("steps", []))
    if "--only ${{ matrix.target }}" not in run:
        fails.append("the timebox step does not pass --only ${{ matrix.target }}")
    return fails


def test_hosted_fuzz_matrix_equals_fleet() -> None:
    wf, fleet = _load()
    assert sync_failures(wf, fleet) == []


def test_planted_missing_core_reddens() -> None:
    wf, fleet = _load()
    for target in [t["id"] for t in fleet["targets"]]:
        planted = copy.deepcopy(wf)
        mx = planted["jobs"]["fuzz-fleet"]["strategy"]["matrix"]
        mx["target"] = [x for x in mx["target"] if x != target]
        fails = sync_failures(planted, fleet)
        assert f"fleet target {target} is missing from the fuzz-fleet matrix" in fails


def test_planted_missing_build_line_reddens() -> None:
    wf, fleet = _load()
    make_targets = [t for t in fleet["targets"] if t.get("runner") == "make-test"]
    assert make_targets
    victim = make_targets[-1]
    planted = copy.deepcopy(wf)
    for step in planted["jobs"]["fuzz-fleet"]["steps"]:
        if "run" in step:
            step["run"] = "\n".join(
                ln for ln in step["run"].splitlines()
                if ln.strip() != f"make -C {victim['runner_makefile']} build")
    assert any(victim["id"] in f and "build" in f
               for f in sync_failures(planted, fleet))


def test_planted_extra_fleet_target_reddens() -> None:
    wf, fleet = _load()
    planted = copy.deepcopy(fleet)
    planted["targets"].append({"id": "planted-core", "runner": "python-tool"})
    assert "fleet target planted-core is missing from the fuzz-fleet matrix" in \
        sync_failures(wf, planted)
