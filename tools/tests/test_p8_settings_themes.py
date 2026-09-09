"""P8 settings(+themes) tooling tests: hosts ⇄ fakes byte-parity + corpus gates.

The centerpiece is the C++-vs-Python PARITY gate (P6/P7 pattern): every
registered method of the settings host must respond byte-identically between
the compiled C++ host (xr-core/settings/tests/build/settings_host) and the
frozen Python reference fake (xr-core/fakes/settings.py) over a table of >=30
valid cases + >=2 malformed frames (compared by error CODE: the two parsers'
detail texts differ) + the six orchestrator-style NOVEL queries below (they
are recorded here and in evidence/P8/logs so a reviewer can re-run them).

The settings recall corpus (200 phrases, generated from the schema aliases —
never hand-edited) is re-checked structurally here: count == 200 and the
expect keys all exist in the schema; the >=95% top-3 BAR is measured by the
C++ suite test_recall_corpus (xr-core), which prints the percentage.

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).

Novel queries (recorded for the reviewer):
  N1 "block advertising trackers"          -> network.tracker-block
  N2 "private window letterboxing"         -> privacy.letterbox
  N3 "make this identity disposable"       -> identity.storage (in_memory alias)
  N4 "upgrade every page to https"         -> network.https-upgrade
  N5 "ask before notifications"            -> privacy.notifications
  N6 "route everything through a proxy"    -> network.route

Stdlib + pytest; runs on a clean clone (real repo + ../xr-core).
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
CPP_HOST = XR_CORE / "settings" / "tests" / "build" / "settings_host"
FAKE = XR_CORE / "fakes" / "settings.py"
SCHEMA = XR_CORE / "settings" / "core" / "settings_schema_v1.json"
CORPUS = XR_CORE / "settings" / "tests" / "recall_corpus.json"
FLAG_NAME = "xr_settings_v0"

STATE_ACTIVE = {
    "schema": "xr-settings-state",
    "schema_version": 1,
    "context": {"identity_id": "xr:0000-0001", "origin": None},
    "values": {"network.adblock": {"value": False, "source": "enterprise",
                                   "managed": True}},
}
STATE_BASIC = {
    "schema": "xr-settings-state",
    "schema_version": 1,
    "context": {"identity_id": None, "origin": None},
    "values": {},
}


def _have_cpp_toolchain() -> bool:
    return shutil.which("g++") is not None and shutil.which("make") is not None


def _ensure_cpp_host() -> Path:
    if CPP_HOST.is_file():
        return CPP_HOST
    r = subprocess.run(["make", "-C", str(XR_CORE / "settings" / "tests")],
                       capture_output=True, text=True)
    if r.returncode != 0 or not CPP_HOST.is_file():
        raise RuntimeError(f"make failed:\n{r.stdout}\n{r.stderr}")
    return CPP_HOST


CPP_OK = _have_cpp_toolchain()
pytestmark = [pytest.mark.skipif(not CPP_OK,
                                 reason="g++/make absent — settings C++ lane")]


def _req(method: str, args: dict) -> str:
    return json.dumps({"method": method, "args": args}, sort_keys=True)


def _backend(backend: str, req: str, store: Path, state: Path | None,
             flag: str, cwd: Path | None = None) -> tuple[int, str]:
    if backend == "cpp":
        cmd = [str(CPP_HOST), "--store-dir", str(store), "--schema", str(SCHEMA)]
        if state is not None:
            cmd += ["--state", str(state)]
        cmd += ["--flag", f"{FLAG_NAME}={flag}", req]
    else:
        cmd = [sys.executable, str(FAKE), "--store-dir", str(store),
               "--schema", str(SCHEMA)]
        if state is not None:
            cmd += ["--state", str(state)]
        cmd += ["--flag", f"{FLAG_NAME}={flag}", req]
    p = subprocess.run(cmd, cwd=cwd or store, capture_output=True, text=True)
    out = p.stdout.strip()
    line = out.splitlines()[-1] if out else ""
    return p.returncode, line


def _state_path(tmp: Path, which: str) -> Path | None:
    if which == "active":
        p = tmp / "state-active.json"
        p.write_text(json.dumps(STATE_ACTIVE, sort_keys=True), encoding="utf-8")
        return p
    if which == "basic":
        p = tmp / "state-basic.json"
        p.write_text(json.dumps(STATE_BASIC, sort_keys=True), encoding="utf-8")
        return p
    return None


# (id, method, args, state: active|basic|none, flag) — 30+ valid parity cases.
PARITY_CASES: list[tuple[str, str, dict, str, str]] = [
    ("flag_status", "flag-status", {}, "none", "on"),
    ("flag_status_off", "flag-status", {}, "none", "off"),
    ("sections_active_identity", "sections", {}, "active", "on"),
    ("sections_no_identity", "sections", {}, "basic", "on"),
    ("sections_off", "sections", {}, "basic", "off"),
    ("search_container", "search", {"query": "container"}, "active", "on"),
    ("search_containers", "search", {"query": "containers"}, "active", "on"),
    ("search_ads", "search", {"query": "ads"}, "active", "on"),
    ("search_empty", "search", {"query": ""}, "active", "on"),
    ("search_garbage", "search", {"query": "zzzz-no-match-zzzz"}, "active", "on"),
    ("search_off", "search", {"query": "ads"}, "basic", "off"),
    ("get_default", "get", {"key": "privacy.letterbox"}, "active", "on"),
    ("get_preempted", "get", {"key": "network.adblock"}, "active", "on"),
    ("get_unknown", "get", {"key": "ghost.key"}, "active", "on"),
    ("get_off", "get", {"key": "network.adblock"}, "basic", "off"),
    ("get_missing_key_arg", "get", {}, "active", "on"),
    ("set_policy_row_rejected", "set", {"key": "network.adblock",
                                        "value": True}, "active", "on"),
    ("set_unknown_key", "set", {"key": "ghost.key", "value": True},
     "active", "on"),
    ("set_type_mismatch", "set", {"key": "network.adblock", "value": "yes"},
     "active", "on"),
    ("set_off", "set", {"key": "network.adblock", "value": False},
     "basic", "off"),
    ("router_home", "router-resolve", {"anchor": ""}, "active", "on"),
    ("router_root", "router-resolve", {"anchor": "xr://settings"}, "active", "on"),
    ("router_section", "router-resolve", {"anchor": "xr://settings/privacy"},
     "active", "on"),
    ("router_setting", "router-resolve",
     {"anchor": "xr://settings/network/adblock"}, "active", "on"),
    ("router_dotted_key", "router-resolve",
     {"anchor": "xr://settings/network/network.adblock"}, "active", "on"),
    ("router_unknown_setting", "router-resolve",
     {"anchor": "xr://settings/network/nope"}, "active", "on"),
    ("router_unknown_section", "router-resolve",
     {"anchor": "xr://settings/net"}, "active", "on"),
    ("router_too_deep", "router-resolve",
     {"anchor": "xr://settings/a/b/c"}, "active", "on"),
    ("router_off", "router-resolve",
     {"anchor": "xr://settings/network/adblock"}, "basic", "off"),
    ("counters_dump_fresh", "counters-dump", {}, "active", "on"),
    ("counters_dump_off", "counters-dump", {}, "basic", "off"),
    ("schema_dump", "schema-dump", {}, "active", "on"),
    ("unknown_method", "teleport", {}, "active", "on"),
]

# The six orchestrator-style NOVEL queries (recorded in evidence).
NOVEL_QUERIES: list[tuple[str, str]] = [
    ("N1", "block advertising trackers"),
    ("N2", "private window letterboxing"),
    ("N3", "make this identity disposable"),
    ("N4", "upgrade every page to https"),
    ("N5", "ask before notifications"),
    ("N6", "route everything through a proxy"),
]

MALFORMED_FRAMES: list[str] = [
    "{not-json",
    "{\"method\":\"search\",\"args\":[1,2,3]}",   # args not an object
]

VALID_N = len(PARITY_CASES) + len(NOVEL_QUERIES)


@pytest.fixture(scope="module")
def hosts():
    _ensure_cpp_host()
    return {}


def _run_case(hosts, req: str, state: str, flag: str, store: Path,
              state_root: Path) -> tuple[int, str, int, str]:
    st = _state_path(state_root, state)
    store.mkdir(parents=True, exist_ok=True)
    rc_c, out_c = _backend("cpp", req, store / "cpp", st, flag, cwd=store)
    rc_p, out_p = _backend("fake", req, store / "py", st, flag, cwd=store)
    return rc_c, out_c, rc_p, out_p


def test_settings_parity_valid_cases(hosts, tmp_path: Path) -> None:
    assert VALID_N >= 30, "parity table must hold >=30 valid cases"
    n = 0
    for cid, method, args, state, flag in PARITY_CASES:
        rc_c, out_c, rc_p, out_p = _run_case(
            hosts, _req(method, args), state, flag, tmp_path / cid, tmp_path)
        assert rc_c == rc_p == 0, f"{cid}: rc cpp={rc_c} py={rc_p}"
        assert out_c == out_p, f"{cid}: byte mismatch\nC++: {out_c}\npy:  {out_p}"
        n += 1
    # The six novel queries (each a `search` on the active-identity state).
    for nid, q in NOVEL_QUERIES:
        req = _req("search", {"query": q})
        rc_c, out_c, rc_p, out_p = _run_case(hosts, req, "active", "on",
                                             tmp_path / nid, tmp_path)
        assert rc_c == rc_p == 0, f"{nid}: rc mismatch"
        assert out_c == out_p, f"{nid}: byte mismatch\nC++: {out_c}\npy:  {out_p}"
        n += 1
    assert n >= 30


def test_settings_parity_malformed(hosts, tmp_path: Path) -> None:
    # Malformed frames compare by EXIT CODE + error CODE only (the two
    # parsers' detail text legitimately differs).
    for i, frame in enumerate(MALFORMED_FRAMES):
        store = tmp_path / f"mal{i}"
        store.mkdir(parents=True, exist_ok=True)
        rc_c, out_c = _backend("cpp", frame, store / "cpp", None, "on",
                               cwd=store)
        rc_p, out_p = _backend("fake", frame, store / "py", None, "on",
                               cwd=store)
        assert rc_c == 1 and rc_p == 1, (i, rc_c, rc_p)
        code_c = json.loads(out_c).get("error")
        code_p = json.loads(out_p).get("error")
        assert code_c == code_p == "kMalformedInput", (i, out_c, out_p)


def test_settings_session_counters_parity(hosts, tmp_path: Path) -> None:
    # A mini-session on ONE store dir per backend: search hits + a router
    # open must produce byte-identical day-granular counters dumps.
    st = _state_path(tmp_path, "active")
    store_c, store_p = tmp_path / "sess_c", tmp_path / "sess_p"
    store_c.mkdir(parents=True, exist_ok=True)
    store_p.mkdir(parents=True, exist_ok=True)
    for backend, store in (("cpp", store_c), ("fake", store_p)):
        for q in ("ads", "container", "trackers"):
            rc, out = _backend(backend, _req("search", {"query": q}),
                               store, st, "on", cwd=store)
            assert rc == 0
        rc, out = _backend(backend, _req(
            "router-resolve", {"anchor": "xr://settings/privacy"}), store, st, "on",
            cwd=store)
        assert rc == 0
    rc_c, dump_c = _backend("cpp", _req("counters-dump", {}), store_c, st, "on",
                            cwd=store_c)
    rc_p, dump_p = _backend("fake", _req("counters-dump", {}), store_p, st, "on",
                            cwd=store_p)
    assert rc_c == rc_p == 0
    assert dump_c == dump_p, f"session counters diverge\nC++: {dump_c}\npy:  {dump_p}"
    doc = json.loads(dump_c)
    assert doc["schema"] == "xr-settings-counters"
    assert doc["in_memory"] is False
    # Query-choice note: "ads" matches 1 setting, "container" matches 3
    # (identity.kind + storage + default_grade), "trackers" matches 1.
    total = sum(int(d.get("queries", 0)) for d in doc["days"].values())
    assert total == 5


def test_settings_recall_corpus_structure() -> None:
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert doc["count"] == 200
    queries = doc["queries"]
    assert len(queries) == 200
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    known = {s["key"] for s in schema["settings"]}
    for row in queries:
        assert row["expect"] in known, row
        assert isinstance(row["query"], str) and row["query"]
    # The corpus is DERIVED data: regenerating must be diff-clean.
    r = subprocess.run(
        [sys.executable, str(XR_CORE / "settings/tests/gen_recall_corpus.py"),
         "--check"],
        cwd=XR_CORE, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
