"""ci_triage.py — fixture-backed triage, and the BLOCKED-NET law.

The fixtures under tools/fixtures/ci_triage/ are unauthenticated recordings of
the red SHA `8db682f` (check-runs, the `exit code 126` annotation, the
governance run's jobs). Tests use them so the reader is proven offline and
deterministically; the live path is exercised by the gate's `--self-test` lane
only when the network is there.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
FIXTURES = TOOLS / "fixtures" / "ci_triage"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / "ci_triage.py"), *args],
                          capture_output=True, text=True)


def test_self_test_passes_on_the_recorded_fixtures() -> None:
    proc = _run("--self-test")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "exit code 126" in proc.stdout


def test_offline_triage_surfaces_the_annotation_and_the_failing_step() -> None:
    sha = (FIXTURES / "RED_SHA.txt").read_text(encoding="utf-8").strip()
    proc = _run("--offline", str(FIXTURES), "--sha", sha, "--json")
    assert proc.returncode == 1, "a red SHA must exit 1"
    doc = json.loads(proc.stdout)
    gov = [c for c in doc["check_runs"] if c["name"] == "governance"]
    assert gov, "the governance check-run is missing from the report"
    messages = [a["message"] for a in gov[0]["annotations"]]
    assert any("exit code 126" in m for m in messages), messages
    assert [s["name"] for s in gov[0]["failing_steps"]] == ["Governance checks"]


def test_a_missing_fixture_degrades_to_blocked_net(tmp_path: Path) -> None:
    proc = _run("--offline", str(tmp_path), "--sha", "0" * 40)
    assert proc.returncode == 77, "a missing fixture must be a visible BLOCKED-NET"
    assert "BLOCKED-NET" in proc.stdout and "fixture missing" in proc.stdout
    # and it must not have invented a conclusion on the way out
    assert "verdict" not in proc.stdout


def test_logs_endpoint_is_reported_as_admin_only_not_assumed() -> None:
    sha = (FIXTURES / "RED_SHA.txt").read_text(encoding="utf-8").strip()
    proc = _run("--offline", str(FIXTURES), "--sha", sha)
    assert "admin-only" in proc.stdout, (
        "the /logs finding must be reported from the measured response, not "
        "silently omitted")


# --- P14-P0-2 (C-0.7): RATE-LIMITED vs ADMIN-ONLY are different facts -------
# The P13 incident: a 403 from an exhausted unauthenticated quota
# (/rate_limit core 60/60, reset hourly) was first read as "the endpoint is
# private". The two classifications must read differently and the 429 case
# must never be labelled a privilege wall.


def test_a_429_is_rate_limited_never_admin_only() -> None:
    import ci_triage
    msg = ci_triage.classify_refusal(
        "/repos/RRRTX-Labs/xr-browser/actions/runs/1/logs",
        "HTTP 429 fetching https://api.github.com/repos/RRRTX-Labs/"
        "xr-browser/actions/runs/1/logs")
    assert "RATE-LIMITED" in msg, msg
    assert "ADMIN-ONLY" not in msg, msg
    assert "/rate_limit" in msg, "the row must name the discriminator"


def test_a_403_names_the_quota_discriminator() -> None:
    import ci_triage
    msg = ci_triage.classify_refusal(
        "/repos/RRRTX-Labs/xr-browser/actions/runs/1/logs",
        "HTTP 403 fetching https://api.github.com/repos/RRRTX-Labs/"
        "xr-browser/actions/runs/1/logs")
    assert "ADMIN-ONLY-or-QUOTA" in msg, msg
    assert "/rate_limit" in msg, msg


def test_the_fetcher_wiring_carries_the_classification() -> None:
    """The classifier is not dead code: Fetcher.get's BlockedNet messages go
    through it (a monkeypatched chokepoint raises the canned failures)."""
    import ci_triage

    class Canned(Exception):
        pass

    class FakeFetch:
        GITHUB_API = "https://api.github.com"

        def http_get(self, path: str, timeout: int = 20) -> bytes:
            raise Canned("HTTP 429 fetching " + path)

    f = ci_triage.Fetcher(offline=None)
    orig = ci_triage._fetch_module
    ci_triage._fetch_module = lambda: FakeFetch()
    try:
        try:
            f.get("/repos/x/y", fixture="whatever.json")
            raise AssertionError("a 429 must raise BlockedNet")
        except ci_triage.BlockedNet as exc:
            assert "RATE-LIMITED" in str(exc), str(exc)
    finally:
        ci_triage._fetch_module = orig
