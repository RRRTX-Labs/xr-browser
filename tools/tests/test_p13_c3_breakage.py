"""The breakage report's refusal surface (P13-T4).

The vectors run in the gate; these tests pin the properties that must not
regress, and the ones a "let's add more context" change would break first. The
distinction the whole contract rests on is that the report is refused BEFORE it
is written — there is no redaction pass, because a report that goes out "mostly
redacted" goes out.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "breakage_report.py"
VECTORS = json.loads((REPO / "docs" / "contracts" / "vectors" /
                      "breakage-report-v1.json").read_text(encoding="utf-8"))
EVENT = {"origin": {"scheme": "https", "registrable_domain": "shop.example"},
         "rule_id": "r-1", "list_id": "l-1", "bundle_version": 3,
         "action": "kBlocked"}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, cwd=REPO)


def _event_file(tmp_path: Path, event: dict) -> Path:
    p = tmp_path / "event.json"
    p.write_text(json.dumps(event), encoding="utf-8")
    return p


def test_vectors_pass() -> None:
    r = _run("--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "refused pre-send with the class named" in r.stdout


def test_every_smuggle_class_is_refused_with_its_name(tmp_path: Path) -> None:
    ev = _event_file(tmp_path, EVENT)
    cases = {
        "url": "broken at https://shop.example/cart?session=abc",
        "cookie": "cookie session=9f3a keeps coming back",
        "user_agent": "Mozilla/5.0 (X11; Linux) fails",
        "selector": "the .cart > .total span { display:none } broke",
        "html": "there is a <div class=cart> that never renders",
    }
    for why_class, note in cases.items():
        r = _run("--from-event", str(ev), "--note", note,
                 "--as-of", "2026-09-30T00:00:00Z", "--validate-only")
        assert r.returncode == 1, f"{why_class}: must be refused"
        assert why_class in r.stderr, (why_class, r.stderr)


def test_origin_must_be_a_bare_domain(tmp_path: Path) -> None:
    ev = _event_file(tmp_path, {**EVENT, "origin": {
        "scheme": "https", "registrable_domain": "shop.example/cart?sid=1"}})
    r = _run("--from-event", str(ev), "--note", "x",
             "--as-of", "2026-09-30T00:00:00Z", "--validate-only")
    assert r.returncode == 1 and "origin" in r.stderr


def test_extra_html_field_is_refused_by_the_SCHEMA(tmp_path: Path) -> None:
    """`additionalProperties: false` is the first line, not the tool's manners."""
    payload = dict(VECTORS["accept"][0]["payload"])
    payload["html"] = "<div>page</div>"
    p = tmp_path / "payload.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    import subprocess as sp
    r = sp.run([sys.executable, str(REPO / "tools" / "xr_schema.py"),
                "--repo", str(REPO), "validate", "breakage-report", str(p)],
               capture_output=True, text=True)
    assert r.returncode == 1 and "additional property" in (r.stdout + r.stderr)


def test_queue_cannot_claim_to_be_live(tmp_path: Path) -> None:
    ev = _event_file(tmp_path, EVENT)
    r = _run("--from-event", str(ev), "--as-of", "2026-09-30T00:00:00Z",
             "--queue", str(tmp_path / "queue"))
    assert r.returncode == 2 and "fixture" in r.stderr


def test_fixture_queue_writes_and_says_so(tmp_path: Path) -> None:
    ev = _event_file(tmp_path, EVENT)
    q = tmp_path / "fixture-queue"
    r = _run("--from-event", str(ev), "--as-of", "2026-09-30T00:00:00Z",
             "--queue", str(q), "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["queue_mode"] == "fixture"
    written = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert written["queue"] == "fixture"
    # SLA is DATA: a target and a class, not a measured median.
    assert written["sla"] == {"label": "corpus-linked-48h", "hours": 48,
                              "class": "corpus-linked"}
    assert "median" not in json.dumps(written)


def test_no_clock_without_as_of(tmp_path: Path) -> None:
    ev = _event_file(tmp_path, EVENT)
    r = _run("--from-event", str(ev), "--note", "x", "--validate-only")
    assert r.returncode == 2 and "--as-of" in r.stderr


def test_the_tool_has_no_network_code() -> None:
    """No new egress path: the transport half is P14's, and this proves it."""
    src = TOOL.read_text(encoding="utf-8")
    for forbidden in ("urllib.request", "http.client", "socket.", "requests"):
        assert forbidden not in src, f"{forbidden} in a tool whose whole point is no egress"
