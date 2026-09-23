#!/usr/bin/env python3
"""tools/tests/test_p11_exceptions.py — P11-T4 shield exception ledger law.

Negative fixtures for the `## shield exception ledger rows` half of
tools/exception_ledger_check.py: the section must exist (zero rows pass —
the v1 host ships no standing exceptions), every row carries scope +
reason + monotonic expiry + owner, expiry is checked against --as-of with
the host's INCLUSIVE boundary (as_of >= expiry ⇒ expired), wall-clock
dates are refused in this ledger, and site-toggle rows must carry the
host's canonical shape. The §1.13 half is P9's (test_p9_isolation.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent

BASE_113 = ("## §1.13 exception ledger rows\n"
            "| mechanism | owner | expiry | note |\n|---|---|---|---|\n"
            "| gpu-texture-side-channel | owner | 2027-01-01 | n |\n")
SHIELD_HEAD = ("## shield exception ledger rows\n"
               "| scope_id | scope | reason | expiry | owner |\n"
               "|---|---|---|---|---|\n")
COSMETIC_HEAD = ("## cosmetic exception ledger rows\n"
                 "| scope_id | scope | reason | expiry | owner |\n"
                 "|---|---|---|---|---|\n")
MATRIX = {"cells": [{"mechanism": "gpu-texture-side-channel",
                     "verdict": "EXCEPTION"}]}


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOLS / name), *args],
                          capture_output=True, text=True)


def make_repo(tmp_path: Path, shield_md: str | None,
              cosm_md: str = COSMETIC_HEAD) -> tuple[Path, Path]:
    """A repo whose §1.13 half is green, isolating the shield assertions
    (a cosmetic ledger section ships by default — P12-T5 added it)."""
    (tmp_path / "docs").mkdir(exist_ok=True)
    parts = [BASE_113]
    if shield_md is not None:
        parts.append("\n" + shield_md)
    parts.append("\n" + cosm_md)
    (tmp_path / "docs" / "limitations.md").write_text(
        "".join(parts), encoding="utf-8")
    mj = tmp_path / "matrix.json"
    mj.write_text(json.dumps(MATRIX), encoding="utf-8")
    return tmp_path, mj


def ledger(tmp_path: Path, mj: Path, *extra: str
           ) -> subprocess.CompletedProcess[str]:
    return run_tool("exception_ledger_check.py", "--repo", str(tmp_path),
                    "--matrix-json", str(mj), *extra)


def row(sid: str, scope: str, reason: str, expiry: str,
        owner: str = "shield lead") -> str:
    return f"| {sid} | {scope} | {reason} | {expiry} | {owner} |\n"


def test_real_repo_green() -> None:
    r = run_tool("exception_ledger_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "zero rows" in r.stdout


def test_section_missing_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, None)
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "shield exception ledger rows" in r.stdout


def test_zero_rows_pass(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD)
    r = ledger(repo, mj)
    assert r.returncode == 0, r.stdout
    assert "zero rows" in r.stdout


def test_valid_row_passes_before_boundary(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "user-allow", "500"))
    r = ledger(repo, mj, "--as-of", "499")
    assert r.returncode == 0, r.stdout
    assert "ok(shield): ex-a" in r.stdout


def test_row_expired_at_inclusive_boundary(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "user-allow", "500"))
    r = ledger(repo, mj, "--as-of", "500")
    assert r.returncode == 1
    assert "has passed as of" in r.stdout


def test_forever_row_survives_any_as_of(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-f", "rule_id=r-1,list_id=l1", "fp", "-1"))
    r = ledger(repo, mj, "--as-of", "999999999")
    assert r.returncode == 0, r.stdout


def test_missing_reason_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "", "500"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "reason is empty" in r.stdout


def test_unknown_scope_dimension_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "bogus=x", "r", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "not in" in r.stdout


def test_scope_dimension_without_eq_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "example.com", "r", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "is not k=v" in r.stdout


def test_empty_scope_cell_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD + row("ex-a", "", "r", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "dimension required" in r.stdout


def test_duplicate_dimension_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=a.example,site=b.example",
                             "r", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "appears twice" in r.stdout


def test_wallclock_expiry_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "r", "2027-01-01"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "not a monotonic integer" in r.stdout


def test_expiry_below_floor_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "r", "-2"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "< -1" in r.stdout


def test_empty_owner_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "r", "-1", ""))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "empty owner" in r.stdout


def test_toggle_row_canonical_passes(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("site-toggle:example.com", "site=example.com",
                             "user-site-toggle", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 0, r.stdout


def test_toggle_row_wrong_reason_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("site-toggle:example.com", "site=example.com",
                             "manual", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "user-site-toggle" in r.stdout


def test_toggle_row_wrong_scope_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("site-toggle:example.com", "site=other.example",
                             "user-site-toggle", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "canonical shape" in r.stdout


def test_negative_as_of_is_usage(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD)
    r = ledger(repo, mj, "--as-of", "-1")
    assert r.returncode == 2


def test_json_reports_shield_rows(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD +
                         row("ex-a", "site=example.com", "r", "-1"))
    r = ledger(repo, mj, "--json")
    assert r.returncode == 0, r.stdout
    doc = json.loads(r.stdout)
    assert doc["shield_rows"] == 1 and doc["status"] == "pass"
    assert doc["as_of"] == 0


# --- P12-T5: the cosmetic exception ledger (same scope object) ------------
def test_cosmetic_zero_rows_pass_real_repo() -> None:
    r = run_tool("exception_ledger_check.py", "--repo", str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "cosmetic" in r.stdout and "ok(cosmetic)" in r.stdout


def test_cosmetic_section_missing_fails(tmp_path: Path) -> None:
    repo, mj = make_repo(tmp_path, SHIELD_HEAD, "## no cosmetic here\n")
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "cosmetic exception ledger rows" in r.stdout


def test_cosmetic_private_row_is_split_brain(tmp_path: Path) -> None:
    # A cosmetic row with no matching shield row: cosmetic consumes the
    # SHARED P11 scopes object, so a private exception is a split-brain.
    repo, mj = make_repo(
        tmp_path, SHIELD_HEAD,
        COSMETIC_HEAD + row("ex-c", "site=example.com", "r", "-1"))
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "split-brain" in r.stdout


def test_cosmetic_row_with_matching_shield_row_passes(tmp_path: Path) -> None:
    shared = row("ex-a", "site=example.com", "user-allow", "-1")
    repo, mj = make_repo(tmp_path, SHIELD_HEAD + shared,
                         COSMETIC_HEAD + shared)
    r = ledger(repo, mj, "--as-of", "5")
    assert r.returncode == 0, r.stdout
    assert "ok(cosmetic): ex-a" in r.stdout


def test_cosmetic_wallclock_expiry_fails(tmp_path: Path) -> None:
    shared_shield = row("ex-a", "site=example.com", "r", "-1")
    shared_cosm = row("ex-a", "site=example.com", "r", "2027-01-01")
    repo, mj = make_repo(tmp_path, SHIELD_HEAD + shared_shield,
                         COSMETIC_HEAD + shared_cosm)
    r = ledger(repo, mj)
    assert r.returncode == 1
    assert "not a monotonic integer" in r.stdout


def test_json_reports_cosmetic_rows(tmp_path: Path) -> None:
    shared = row("ex-a", "site=example.com", "r", "-1")
    repo, mj = make_repo(tmp_path, SHIELD_HEAD + shared,
                         COSMETIC_HEAD + shared)
    r = ledger(repo, mj, "--json")
    assert r.returncode == 0, r.stdout
    doc = json.loads(r.stdout)
    assert doc["cosmetic_rows"] == 1 and doc["status"] == "pass"
