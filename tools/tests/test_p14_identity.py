"""P14 identity tests: frozen-surface parity + the living-surface laws.

Laws exercised here (P14-T1's own tests, the policy-precedent split):

1. tools/parity/corpus-identity.json — every case replays BYTE-IDENTICALLY
   between the compiled identity_host and fakes/identity.py (stdout bytes +
   exit code), because the frozen mojom v1 surface is a parity contract,
   not a courtesy (P9 law applied to the identity pair).
2. fakes/fixtures/identity-v1.json replays against BOTH backends.
3. The LIVING subcommand surface (no fake counterpart — accounted for as
   data in tools/parity/manifest.json, the policy_host precedent) is
   regression-locked here: the laws that make identity identity —
   provision REQUIRES entropy (the host cannot mint from the fixture
   table), the scheduler's soft cap evicts LRU and RECORDS it, wake never
   resurrects a purged domain, the autoswitch probe is REFUSED, the
   ceremony inventory lists every applied default, attribution closes
   against the total and refuses contradictory samples.
4. host_protocol_check + parity_completeness stay green with the identity
   pair present (the derived-pair law; a host nobody counted is dead).

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"
CORPUS = TOOLS / "parity" / "corpus-identity.json"
FIXTURE = XR_CORE / "fakes" / "fixtures" / "identity-v1.json"
# The build is OUT-OF-TREE: building in the sibling would leave
# identity/tests/build/ behind and every pin-faithful gate would then rightly
# call xr-core DIRTY (the files it reads must be the pinned files).
BUILD_DIR = REPO / "work" / "scratch" / "pytest-identity-build"
HOST = BUILD_DIR / "identity_host"
FAKE = XR_CORE / "fakes" / "identity.py"

HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None


@pytest.fixture(scope="module")
def host() -> Path:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — C++ identity host skipped (skip-policy)")
    r = subprocess.run(["make", "-C", str(XR_CORE / "identity" / "tests"),
                        "build", f"BUILD={BUILD_DIR}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"make failed for identity:\n{r.stderr[-400:]}")
    return HOST


def _run(argv: list[str], req: str) -> tuple[int, str]:
    """Run a backend. `req` rides as argv[-1] for subcommand calls (the
    host's documented form: argv[2]); pass stdin= for the frozen form."""
    p = subprocess.run(argv + [req] if len(argv) > 1 else argv,
                       input=None, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout.strip()


def _case_req(case: dict) -> str:
    return json.dumps({"method": case["method"], "args": case["args"]},
                      sort_keys=True, separators=(",", ":"))


def _run_stdin(argv: list[str], req: str) -> tuple[int, str]:
    p = subprocess.run(argv, input=req, capture_output=True, text=True,
                       timeout=60)
    return p.returncode, p.stdout.strip()


# ---------------------------------------------------------------------------
# 1. corpus byte-parity (the frozen surface is a contract)
# ---------------------------------------------------------------------------

def test_corpus_covers_every_protocol_method() -> None:
    doc = (XR_CORE / "identity" / "host_protocol.md").read_text("utf-8")
    corpus = json.loads(CORPUS.read_text("utf-8"))
    covered = {c["method"] for c in corpus["cases"]}
    # the FROZEN Methods table only (## Methods .. ## Subcommands): the
    # living subcommands have no fake counterpart and are covered by the
    # C++ suite + this file (the manifest's living_surface row).
    import re
    methods_section = doc.split("## Methods", 1)[1].split("## Subcommands", 1)[0]
    rows = set(re.findall(r"^\| `([A-Za-z]+)` \|", methods_section, re.M))
    assert rows, "Methods table not found in host_protocol.md"
    assert rows <= covered, f"methods without corpus cases: {rows - covered}"
    assert corpus["pair"] == "identity"
    for c in corpus["cases"]:
        assert c["expect"] in ("ok", "reject")


def test_corpus_byte_parity_host_vs_fake(host: Path) -> None:
    corpus = json.loads(CORPUS.read_text("utf-8"))
    assert len(corpus["cases"]) >= 15
    for case in corpus["cases"]:
        req = _case_req(case)
        rc_h, out_h = _run_stdin([str(host)], req)
        rc_f, out_f = _run_stdin([sys.executable, str(FAKE)], req)
        assert rc_h == rc_f, (case["id"], rc_h, rc_f)
        assert out_h == out_f, (case["id"], out_h, out_f)
        if case["expect"] == "ok":
            assert rc_h == 0, (case["id"], rc_h)


def test_frozen_fixture_replays_identically(host: Path) -> None:
    fixture = json.loads(FIXTURE.read_text("utf-8"))
    for case in fixture["cases"]:
        req = json.dumps({"method": case["method"], "args": case["args"]},
                         sort_keys=True, separators=(",", ":"))
        rc_h, out_h = _run_stdin([str(host)], req)
        rc_f, out_f = _run_stdin([sys.executable, str(FAKE)], req)
        assert (rc_h, out_h) == (rc_f, out_f), case["name"]
        if "expect_error" in case:
            assert json.loads(out_h)["error"] == case["expect_error"]


# ---------------------------------------------------------------------------
# 2. the living surface (no fake — the laws are the lock)
# ---------------------------------------------------------------------------

def test_provision_requires_entropy(host: Path) -> None:
    rc, out = _run([str(host), "provision"], "{}")
    assert rc == 1 and json.loads(out)["error"] == "kMalformedInput"
    rc, out = _run([str(host), "provision"],
                   '{"entropy":"os-1","display_name":"Work"}')
    assert rc == 0
    rec = json.loads(out)
    assert rec["domain"].startswith("xr:") and len(rec["domain"]) == 39
    assert "Work" not in rec["domain"]  # opaque: no name in the domain
    # replay is EXPLICIT and exhausts visibly (no silent entropy fallback)
    rc, out = _run([str(host), "provision"], '{"replay":true}')
    assert rc == 0 and json.loads(out)["domain"].endswith("000001")


def test_templates_and_ceremony_law(host: Path) -> None:
    rc, out = _run([str(host), "templates"], "{}")
    assert rc == 0
    t = json.loads(out)
    assert t["count"] == 7
    by_id = {x["id"]: x for x in t["templates"]}
    assert by_id["tor"]["route"] == "tor" and not by_id["tor"]["route_bound"]
    assert by_id["disposable"]["disposable"]
    # ceremony: every line the template applies is listed (single source)
    rc, out = _run([str(host), "ceremony"], '{"template_id":"banking"}')
    lines = json.loads(out)["lines"]
    applied = [l for l in lines if l.startswith("applied ")]
    assert any("shield.trust_level = strict" in l for l in applied)
    assert len(applied) == 8  # banking: 1 prefs + 5 policy + 2 visual rows
    # unknown template: typed rejection
    rc, out = _run([str(host), "ceremony"], '{"template_id":"ghost"}')
    assert rc == 0 and json.loads(out)["error"] == "kRejected"
    # Tor says it is NOT BOUND (inert-with-reason, the P12-T6 honesty law)
    rc, out = _run([str(host), "ceremony"], '{"template_id":"tor"}')
    assert any("NOT BOUND YET" in l for l in json.loads(out)["lines"])


def test_scheduler_cap_eviction_and_no_resurrection(host: Path) -> None:
    ops = [{"op": "provision", "entropy": f"e{i}"} for i in range(6)]
    ops += [{"op": "activate", "domain": f"xr:{i}", "tick": i}
            for i in range(6)]
    # NOTE: domains are opaque mints; discover them from the steps output.
    rc, out = _run([str(host), "scenario"],
                   json.dumps({"ops": ops[:6]}))
    assert rc == 0
    domains = [s["record"]["domain"] for s in json.loads(out)["steps"]]
    ops2 = [{"op": "provision", "entropy": f"e{i}"} for i in range(6)]
    ops2 += [{"op": "activate", "domain": d, "tick": i}
             for i, d in enumerate(domains)]
    rc, out = _run([str(host), "scenario"], json.dumps({"ops": ops2}))
    sc = json.loads(out)
    assert rc == 0
    assert len(sc["final"]["evictions"]) == 1  # cap 5: the 6th evicts LRU
    assert sc["final"]["evictions"][0]["reason"] == "cap"
    assert sc["final"]["evictions"][0]["domain"] == domains[0]
    # destroy + wake: NEVER resurrect (the disposable law) — use the
    # deterministic replay mint so the domain is known without a discovery
    # round-trip.
    replay_dom = "xr:00000000-0000-4000-8000-000000000001"
    ops3 = [{"op": "provision", "replay": True},
            {"op": "destroy", "domain": replay_dom},
            {"op": "wake", "domain": replay_dom, "tick": 9}]
    rc, out = _run([str(host), "scenario"], json.dumps({"ops": ops3}))
    sc = json.loads(out)
    assert sc["steps"][1]["zero_residual_verified"] is True
    assert sc["steps"][2]["ok"] is False
    assert "resurrect" in sc["steps"][2]["error"]
    assert sc["steps"][2]["error"].startswith("kUnknownIdentity")


def test_scenario_planted_residual_fails_destroy(host: Path) -> None:
    # the §1.4 negative, replayable: a purge that leaves bytes FAILS
    rc, out = _run([str(host), "scenario"],
                   '{"ops":[{"op":"provision","entropy":"p0"}]}')
    dom = json.loads(out)["steps"][0]["record"]["domain"]
    ops = [{"op": "provision", "entropy": "p0"},
           {"op": "plant-residual", "domain": dom, "kind": "cookies",
            "bytes": 512},
           {"op": "destroy", "domain": dom}]
    rc, out = _run([str(host), "scenario"], json.dumps({"ops": ops}))
    sc = json.loads(out)
    assert sc["steps"][2]["ok"] is False
    assert sc["steps"][2]["zero_residual_verified"] is False
    assert "residual" in sc["steps"][2]["error"]


def test_autoswitch_probe_is_refused(host: Path) -> None:
    rc, out = _run([str(host), "autoswitch-probe"],
                   '{"tab_id":1,"to":"xr:00000000-0000-4000-8000-000000000001"}')
    assert rc == 0
    assert json.loads(out)["error"] == "kRejected"
    assert "never auto-switch" in json.loads(out)["reason"]


def test_attribution_closes_and_refuses_contradictions(host: Path) -> None:
    args = {"samples": [{"pid": 1, "rss_kb": 1000,
                         "serves": ["xr:00000000-0000-4000-8000-000000000001"]},
                        {"pid": 2, "rss_kb": 800,
                         "serves": ["xr:00000000-0000-4000-8000-000000000001",
                                    "xr:00000000-0000-4000-8000-000000000002"]}],
            "total_kb": 3000}
    rc, out = _run([str(host), "attribute"], json.dumps(args))
    rows = json.loads(out)
    assert rc == 0
    assert rows["sum_kb"] == 3000  # closes EXACTLY against the total
    by = {r["domain"]: r["kb"] for r in rows["rows"]}
    assert by["xr:00000000-0000-4000-8000-000000000001"] == 1400  # 1000+400
    assert by["xr:00000000-0000-4000-8000-000000000002"] == 400
    # contradictory samples: NO table (never a plausible wrong one)
    args["total_kb"] = 100
    rc, out = _run([str(host), "attribute"], json.dumps(args))
    assert rc == 0 and json.loads(out)["error"] == "kRejected"


def test_resolve_pref_fails_safe(host: Path) -> None:
    # unknown identity: value null = NO overrides (closed), never a guess
    rc, out = _run([str(host), "resolve-pref"],
                   '{"domain":"xr:ghost","key":"shield.trust_level"}')
    assert rc == 0 and json.loads(out)["value"] is None


def test_living_subcommands_unknown_is_typed(host: Path) -> None:
    rc, out = _run([str(host), "no-such-cmd"], "{}")
    assert rc == 1 and json.loads(out)["error"] == "kUnknownMethod"


# ---------------------------------------------------------------------------
# 3. the derived-pair gates stay green with identity present
# ---------------------------------------------------------------------------

def test_host_protocol_check_green() -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "host_protocol_check.py"),
                        "--xr-core", str(XR_CORE)], capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout


def test_parity_completeness_green_with_identity() -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "parity_completeness.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "identity" in r.stdout
    man = json.loads((TOOLS / "parity" / "manifest.json").read_text("utf-8"))
    ids = {p["id"] for p in man["pairs"]}
    assert "identity" in ids  # the pair is DATA, never an omission
