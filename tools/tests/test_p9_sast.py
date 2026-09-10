"""tools/tests/test_p9_sast.py — P9-T9: SAST registry canary + real-tree clean."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
REGISTRY = REPO / "build/sast/rules/sast-rules.yaml"


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True)


def registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def test_sast_check_green_on_real_tree() -> None:
    r = run_tool("sast_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout


def test_every_active_rule_has_firing_fixture() -> None:
    for rule in registry()["rules"]:
        if rule.get("status", "active") == "not_yet":
            continue
        fixture = REPO / rule["fixture"]
        assert fixture.exists(), rule["id"]
        text = fixture.read_text(encoding="utf-8", errors="replace")
        pats = [p for p in rule.get("patterns") or [] if p]
        assert any(p in text for p in pats), \
            f"{rule['id']}: fixture cannot trip the rule (canary law)"


def test_not_yet_rules_owned() -> None:
    for rule in registry()["rules"]:
        if rule.get("status", "active") == "not_yet":
            assert rule.get("owner_phase"), rule["id"]


def test_negative_fixtures_trip_nothing() -> None:
    neg = REPO / "build/sast/fixtures/negative"
    active = [r for r in registry()["rules"]
              if r.get("status", "active") == "active"]
    for f in neg.glob("*"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for rule in active:
            for pat in rule.get("patterns") or []:
                assert pat not in text, \
                    f"negative {f.name} trips {rule['id']} ({pat})"


def test_semgrep_rules_wellformed() -> None:
    sd = REPO / "build/sast/rules/semgrep"
    files = list(sd.glob("*.yaml"))
    assert files
    for sf in files:
        doc = yaml.safe_load(sf.read_text(encoding="utf-8"))
        assert doc and doc.get("rules")


def test_sast_scan_ignores_fixtures() -> None:
    # the canary fixtures must be OUTSIDE every rule's shipped-tree scope:
    # they live under build/sast/fixtures, which no rule lists as scope.
    for rule in registry()["rules"]:
        for scope in rule.get("scope") or []:
            assert "build/sast/fixtures" not in scope, rule["id"]
