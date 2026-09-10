"""tools/tests/test_p9_fuzz.py — P9-T8: fuzz fleet, mojom generator, corpus seeds."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True)


def test_mojom_fuzz_gen_deterministic() -> None:
    a = run_tool("mojom_fuzz_gen.py", "--repo", str(REPO), "--count", "40",
                 "--seed", "7", "--out", str(REPO / "docs/qa/fuzz-stream-a"))
    b = run_tool("mojom_fuzz_gen.py", "--repo", str(REPO), "--count", "40",
                 "--seed", "7", "--out", str(REPO / "docs/qa/fuzz-stream-b"))
    assert a.returncode == 0 and b.returncode == 0
    assert (REPO / "docs/qa/fuzz-stream-a").read_bytes() == \
           (REPO / "docs/qa/fuzz-stream-b").read_bytes()
    assert len((REPO / "docs/qa/fuzz-stream-a").read_text().splitlines()) == 160
    (REPO / "docs/qa/fuzz-stream-a").unlink()
    (REPO / "docs/qa/fuzz-stream-b").unlink()


def test_mojom_fuzz_gen_covers_four_hosts() -> None:
    r = run_tool("mojom_fuzz_gen.py", "--repo", str(REPO), "--count", "10",
                 "--seed", "3", "--json")
    doc = json.loads(r.stdout[r.stdout.index("{"):])
    assert doc["per_host"] == {"commands": 10, "policy": 10,
                               "settings": 10, "themes": 10}


def test_seed_corpus_check_green() -> None:
    r = run_tool("seed_corpus.py", "--repo", str(REPO), "--check")
    assert r.returncode == 0, r.stdout


def test_seed_corpus_every_target_seeded() -> None:
    for t in ("policy-core", "commands-core", "settings-core", "themes-core"):
        cdir = REPO / "build" / "fuzz" / "corpus" / t
        assert cdir.is_dir() and any(cdir.iterdir()), f"{t} unseeded"


def test_fleet_yaml_discovers_four_cores() -> None:
    import yaml
    doc = yaml.safe_load((REPO / "build/fuzz/fleet.yaml").read_text())
    ids = [t["id"] for t in doc["targets"]]
    assert ids == ["policy-core", "commands-core", "settings-core",
                   "themes-core"]
    # libFuzzer entry points must exist for every target (never referenced
    # before existing)
    for t in doc["targets"]:
        assert (REPO / "build/fuzz/libfuzzer" /
                f"{t['libfuzzer_target']}.cc").exists()


def test_policy_fuzz_min_iters_floor_bites(tmp_path: Path) -> None:
    # The empty-run law (n < --min-iters with no crash/violation => FAIL) is
    # a verdict over the run's own counters, so it must be provable without
    # the C++ policy_host binary (which a fresh clone has not built yet —
    # citing it here is a leftover-artifact trap). A fake host that answers
    # every request with a known-good error lets the harness execute exactly
    # --iterations 1 and trip the floor.
    host = tmp_path / "okhost"
    host.write_text("#!/bin/sh\nprintf '{\"error\":\"kVersionMismatch\"}\\n'\n",
                    encoding="utf-8")
    host.chmod(0o755)
    r = run_tool("policy_fuzz.py", "--host", str(host),
                 "--iterations", "1", "--min-iters", "2")
    assert r.returncode == 1
    assert "empty-run law" in r.stdout
