"""ci_parity tools — parser fidelity + verdict laws (P14-P0-2).

The parity tool's own --self-test is the gate-side negative; this suite pins
the pieces that need real-looking fixture data (URL literals are sanctioned
here per the fetch_allowlist law: "URL literals in tests are FIXTURE DATA …
never fetched") and the chokepoint-constant law for the probe paths.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ci_parity_check as cpc  # noqa: E402
import ci_parity_probes as cpn  # noqa: E402


def test_release_tarball_url_parses_to_the_tool() -> None:
    """The full governance.yml-shaped install step: apt names + the pinned
    actionlint release tarball URL, exactly as the workflow writes it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "governance.yml").write_text(
            "      - name: Install optional helper tools\n"
            "        run: |\n"
            "          sudo apt-get install -y -qq minisign faketime\n"
            "          AL_VERSION=1.7.7\n"
            "          curl -sSL -o /tmp/actionlint.tgz \\\n"
            "            \"https://github.com/rhysd/actionlint/releases/"
            "download/v${AL_VERSION}/"
            "actionlint_${AL_VERSION}_linux_amd64.tar.gz\"\n",
            encoding="utf-8")
        dem = cpc.demanded_tools(root)
        assert {"minisign", "faketime"} <= set(dem)
        assert dem.get("actionlint") == (
            ".github/workflows/governance.yml (pinned release tarball)")


def test_probe_paths_live_in_reviewable_data_not_code() -> None:
    """The probe paths are DATA (docs/state/parity-probe-paths.json — the
    docs/state class the fetch_allowlist checker sanctions); the probes
    module must hold no URL literals of its own, and every data host must be
    on the chokepoint's allowlist (the data can never widen the surface)."""
    fetch = cpn.fetch_module()
    paths = cpn.load_probe_paths(TOOLS.parent)
    assert paths, "the probe-path data file must parse and be non-empty"
    assert set(paths) <= set(fetch.ALLOWED_HOSTS), (
        "probe-path data names a host the chokepoint does not allowlist")
    src = (TOOLS / "ci_parity_probes.py").read_text(encoding="utf-8")
    code = cpn.re.sub(r"\"\"\"[\\s\\S]*?\"\"\"", '""', src)
    code = cpn.re.sub(r"#[^\\n]*", "", code)
    assert "https://" not in code and "http://" not in code, (
        "ci_parity_probes.py must not embed URL literals — the paths are "
        "data in docs/state/parity-probe-paths.json")
    # and every allowlisted host has a path (completeness)
    assert set(fetch.ALLOWED_HOSTS) == set(paths), (
        "every allowlisted host needs a canonical probe path (completeness)")


def test_composite_gap_row_names_the_sc2251_class() -> None:
    rows = cpc.tool_rows({"actionlint"}, {"actionlint": "x", "shellcheck": "x"})
    comp = [r for r in rows if r["tool"] == "actionlint+shellcheck"]
    assert comp and comp[0]["counts_stricter"]
    assert "shellcheck pass will not run here" in comp[0]["status"]


def test_platform_optional_tools_never_count() -> None:
    rows = cpc.tool_rows(set(), {"signtool": "x", "codesign": "x",
                                 "faketime": "x"})
    by = {r["tool"]: r for r in rows}
    assert not by["signtool"]["counts_stricter"]
    assert not by["codesign"]["counts_stricter"]
    assert by["faketime"]["counts_stricter"]


def test_verdict_flips_with_the_host() -> None:
    full = cpc.tool_rows({"actionlint", "shellcheck", "faketime", "minisign"},
                         {"actionlint": "x", "shellcheck": "x",
                          "faketime": "x", "minisign": "x"})
    gap = cpc.tool_rows({"actionlint", "shellcheck"},
                        {"actionlint": "x", "shellcheck": "x", "faketime": "x"})
    assert cpc.verdict_of(full, {"status": "PASS"}, {"closure": "PASS"},
                          []) == ("PASS", [])
    v, lanes = cpc.verdict_of(gap, {"status": "PASS"}, {"closure": "PASS"}, [])
    assert v == "PARTIAL" and any("faketime" in x for x in lanes)


def test_a_blocked_net_row_counts_a_4xx_does_not() -> None:
    blocked = {"host": "h", "result": "blocked", "detail": "x",
               "counts_stricter": True}
    answered = {"host": "h2", "result": "reachable", "detail": "HTTP 404",
                "counts_stricter": False}
    _, lanes = cpc.verdict_of([], {"status": "PASS"}, {"closure": "PASS"},
                              [blocked, answered])
    assert lanes == ["net:h (network-dependent lanes)"]


def test_classify_keeps_the_code() -> None:
    class Fake(Exception):
        pass
    assert cpn.classify(Fake("HTTP Error 503: Service Unavailable"))[2] is True
    k, d, c = cpn.classify(Fake("HTTP 403 fetching u"))
    assert k == "reachable" and "HTTP 403" in d and c is False
    k, _, c = cpn.classify(Fake("host 'x' not on the fetch allowlist; "
                                "refusing 'u'"))
    assert k == "refused" and c is False
