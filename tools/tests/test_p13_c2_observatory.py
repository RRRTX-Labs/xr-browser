"""The Observatory's export law (P13-T3), pinned where the rest of the suite is.

tools/observatory_export.py --check runs the same corpus in the gate; these tests
pin the properties that must not regress, and — more important — that a refusal
is a REFUSAL: the bytes never reach the writer. "We validate" and "it cannot get
out" are different claims and only the second one is a privacy guarantee.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
GOLDEN = REPO / "docs" / "contracts" / "tests" / "golden-block-event.json"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / "observatory_export.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


def test_real_check_passes() -> None:
    r = _run("--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "no refused byte reached the writer" in r.stdout


def test_default_drops_query_and_fragment() -> None:
    r = _run("--fixture", str(_fixture([{"seq": 1, "target": "https://t.example/a.js?uid=9#x"}])),
             "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out[0]["target"] == "https://t.example/a.js"
    assert "uid=9" not in r.stdout and "#x" not in r.stdout


def test_full_keeps_the_query_but_never_the_credentials() -> None:
    fx = _fixture([{"seq": 1, "target": "https://t.example/a.js?uid=9#frag"}])
    r = _run("--fixture", str(fx), "--json", "--full")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)[0]["target"] == "https://t.example/a.js?uid=9"
    assert "frag" not in r.stdout
    # credentials are refused even in --full, and the secret is NOWHERE.
    bad = _fixture([{"seq": 2, "target": "https://u:sekret@t.example/a.js"}])
    r = _run("--fixture", str(bad), "--json", "--full")
    assert r.returncode == 1
    assert "credentials" in r.stderr and "sekret" not in (r.stdout + r.stderr)


def test_a_field_named_cookie_is_refused_by_name() -> None:
    bad = _fixture([{"seq": 3, "target": "https://t.example/a.js", "cookie": "x"}])
    r = _run("--fixture", str(bad), "--json")
    assert r.returncode == 1 and "cookie" in r.stderr


def test_a_filter_rule_that_looks_like_a_fragment_survives() -> None:
    """The refusal classes must not eat the product's own data."""
    fx = _fixture([{"seq": 4, "target": "https://t.example/a.js", "rule": "###tracker-ad"}])
    r = _run("--fixture", str(fx), "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)[0]["rule"] == "###tracker-ad"


def test_csv_and_json_carry_the_same_field_set() -> None:
    row = json.loads(GOLDEN.read_text(encoding="utf-8"))
    fx = _fixture([row])
    j = json.loads(_run("--fixture", str(fx), "--json").stdout)
    c = _run("--fixture", str(fx), "--csv").stdout.splitlines()
    assert list(j[0].keys()) == c[0].split(",")


def test_the_golden_row_is_exportable_from_the_committed_tree() -> None:
    r = _run("--check")
    assert "parity row(s)" in r.stdout and r.returncode == 0


def _fixture(rows: list[dict]) -> Path:
    p = Path("/tmp") / f"obs-fx-{abs(hash(json.dumps(rows, sort_keys=True)))}.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    return p
