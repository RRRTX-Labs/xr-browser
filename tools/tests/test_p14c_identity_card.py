"""P14-CLOSE C-5: the Isolation Card's identity rows are generated data, and
the card refuses prose (tools/identity_card.py, called by
tools/isolation_matrix.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import identity_card as ic  # noqa: E402

MATRIX = {"mechanisms": [
    {"id": "storage-scope", "mode": "fake"},
    {"id": "cookies-1p", "mode": "browser"},
    {"id": "favicon-cache", "mode": "exception"},
    {"id": "blob-storage", "mode": "not-yet"},
]}


def _cells(mech: str, verdicts: list[str]) -> list[dict]:
    return [{"mechanism": mech, "verdict": v} for v in verdicts]


def test_rows_follow_the_record_not_prose():
    cells = (_cells("storage-scope", ["PASS"] * 5) +
             _cells("cookies-1p", ["NOT-RUN"] * 5) +
             _cells("favicon-cache", ["EXCEPTION"] * 5) +
             _cells("blob-storage", ["NOT-RUN"] * 5))
    rows = ic.build_rows(cells, MATRIX)
    assert [(r["prop"], r["state"], r["measured"], r["pairs"]) for r in rows] == [
        ("storage-scope", "holds", 5, 5), ("cookies-1p", "not-run", 0, 5),
        ("favicon-cache", "disclosed", 0, 5), ("blob-storage", "not-run", 0, 5)]
    assert rows[1]["method"] == ic.METHOD_BROWSER
    assert rows[3]["method"] == ic.METHOD_NOT_YET
    assert ic.validate_rows(rows) == []


def test_one_failed_pair_is_violated_and_a_partial_pass_never_holds():
    cells = _cells("storage-scope", ["PASS"] * 4 + ["FAIL"])
    assert ic.build_rows(cells, MATRIX)[0]["state"] == "violated"
    cells = _cells("storage-scope", ["PASS"] * 4 + ["NOT-RUN"])
    row = ic.build_rows(cells, MATRIX)[0]
    assert row["state"] == "not-run" and row["measured"] == 0


def test_the_card_refuses_prose_and_unmeasured_claims():
    good = {"prop": "storage-scope", "state": "holds", "measured": 5,
            "pairs": 5, "method": ic.METHOD_MEASURED}
    assert ic.validate_rows([good]) == []
    cases = {
        "prop": dict(good, prop="Storage is fully separate"),
        "method": dict(good, method="trust us"),
        "state 'Isolated'": dict(good, state="Isolated"),
        "'holds' needs every pair": dict(good, measured=4),
        "keys must be exactly": dict(good, note="x"),
        "'not-run' cannot claim": dict(good, state="not-run", measured=1),
        "0 <= m <= n": dict(good, measured=6),
    }
    for needle, row in cases.items():
        reasons = ic.validate_rows([row])
        assert reasons and any(needle in r for r in reasons), (needle, reasons)
    assert ic.validate_rows([]) == ["card: rows must be a non-empty list"]


def test_committed_card_matches_the_generator():
    out = subprocess.run([sys.executable, "tools/isolation_matrix.py",
                          "--repo", ".", "--check"], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "identity card rows diff-clean" in out.stdout


def test_limitations_block_is_spliced_not_appended():
    text = f"head\n{ic.BEGIN}\nold\n{ic.END}\ntail\n"
    new = ic.splice(text, f"{ic.BEGIN}\nnew\n{ic.END}")
    assert new == f"head\n{ic.BEGIN}\nnew\n{ic.END}\ntail\n"
    assert ic.splice("no markers", "x") is None
    json.dumps(new)  # plain text, no hidden state
