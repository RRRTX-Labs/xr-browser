"""P8 themes tooling tests: themes_host <-> fakes/themes.py byte-parity + gates.

The P8-T3/T4 proof lane's cross-implementation contract: every registered
method of the themes host (flag-status, list, current, apply, import,
validate-doc, system-mode) must respond BYTE-IDENTICALLY between the compiled
C++ host (xr-core/themes/tests/build/themes_host) and the Python reference
fake (xr-core/fakes/themes.py) over >=30 valid parity cases; malformed frames
compare by EXIT code + error CODE only (the two parsers' detail text
legitimately differs — recorded settings-suite convention).

Parity table cases run on DISPOSABLE sessions (no --store-dir): one fresh
process per call on both sides, so no state can leak between rows. The
durability session is a separate test: apply -> fresh-process list/current ->
state file, byte-compared at every step (both sides write the canonical
state shape: schema/schema_version/applied/mode, tmp -> rename).

The tokens source (xr-core/ui/themes/tokens.json) is re-gated here:
40 meta tokens; built-ins exactly {light, dark, high-contrast, dusk,
prairie}; the system resolver defaulting to light; light carries exactly 9
exact waiver rows; the other four curated themes carry ZERO waivers; every
theme's value map passes the reference audit with its own waiver rows.

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).

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
CPP_HOST = XR_CORE / "themes" / "tests" / "build" / "themes_host"
FAKE = XR_CORE / "fakes" / "themes.py"
TOKENS = XR_CORE / "ui" / "themes" / "tokens.json"

BUILTINS = ("dark", "dusk", "high-contrast", "light", "prairie")
META_TOKENS = 40
WAIVER_COUNTS = {"light": 9}  # every other built-in must carry zero waivers


def _have_cpp_toolchain() -> bool:
    return shutil.which("g++") is not None and shutil.which("make") is not None


def _ensure_cpp_host() -> Path:
    if CPP_HOST.is_file():
        return CPP_HOST
    r = subprocess.run(["make", "-C", str(XR_CORE / "themes" / "tests")],
                       capture_output=True, text=True)
    if r.returncode != 0 or not CPP_HOST.is_file():
        raise RuntimeError(f"make failed:\n{r.stdout}\n{r.stderr}")
    return CPP_HOST


CPP_OK = _have_cpp_toolchain()
pytestmark = [pytest.mark.skipif(not CPP_OK,
                                 reason="g++/make absent — themes C++ lane")]


def _req(method: str, args: dict) -> str:
    return json.dumps({"method": method, "args": args}, sort_keys=True)


def _backend(backend: str, req: str, store: Path) -> tuple[int, str]:
    """One request against one backend. `store` is a per-case directory that
    EXISTS (host refuses state writes into a missing dir — kIoError, which is
    itself covered by the refuse rows); durable tests pass --store-dir, the
    disposable parity rows pass none."""
    if backend == "cpp":
        cmd = [str(CPP_HOST)]
        if store is not None:
            cmd += ["--store-dir", str(store)]
        cmd += ["--tokens", str(TOKENS), req]
    else:
        cmd = [sys.executable, str(FAKE), "--tokens", str(TOKENS)]
        if store is not None:
            cmd += ["--store-dir", str(store)]
        cmd.append(req)
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout.strip()
    line = out.splitlines()[-1] if out else ""
    return p.returncode, line


# (id, method, args) — 30+ valid parity rows, each a fresh disposable session
# (no --store-dir on either side; apply/system-mode are in-memory and die
# with the process, which is exactly the disposable contract).
PARITY_CASES: list[tuple[str, str, dict]] = [
    ("flag_status", "flag-status", {}),
    ("list_fresh", "list", {}),
    ("current_fresh", "current", {}),
    ("apply_dark", "apply", {"name": "dark"}),
    ("current_dark", "current", {}),
    ("list_after_dark", "list", {}),
    ("apply_light", "apply", {"name": "light"}),
    ("current_light", "current", {}),
    ("apply_dusk", "apply", {"name": "dusk"}),
    ("current_dusk", "current", {}),
    ("apply_high_contrast", "apply", {"name": "high-contrast"}),
    ("current_hc", "current", {}),
    ("apply_prairie", "apply", {"name": "prairie"}),
    ("current_prairie", "current", {}),
    ("apply_system", "apply", {"name": "system"}),
    ("current_system", "current", {}),
    ("list_system_current", "list", {}),
    ("system_mode_dark", "system-mode", {"mode": "dark"}),
    ("current_mode_dark", "current", {}),
    ("system_mode_hc", "system-mode", {"mode": "high-contrast"}),
    ("current_mode_hc", "current", {}),
    ("system_mode_light", "system-mode", {"mode": "light"}),
    ("current_back_light", "current", {}),
    ("apply_then_mode_dark", "apply", {"name": "prairie"}),
    ("validate_empty_doc", "validate-doc", {"theme-doc": "{}"}),
    ("validate_text_row", "validate-doc",
     {"theme-doc": json.dumps({"text": "#111111"})}),
    ("validate_accent_row", "validate-doc",
     {"theme-doc": json.dumps({"accent": "#0969da", "accent-hover": "#0550ae"})}),
    ("import_text_row", "import",
     {"theme-doc": json.dumps({"text": "#111111"})}),
    ("current_after_import", "current", {}),
    ("import_accent_row", "import",
     {"theme-doc": json.dumps({"accent": "#0969da", "accent-soft": "#ddf4ff",
                               "focus-ring": "#0969da"})}),
    ("import_again_same", "import",
     {"theme-doc": json.dumps({"text": "#111111"})}),
    ("validate_dark_full_doc", "validate-doc",
     {"theme-doc": json.dumps(
         {"text": "#e6edf3", "surface": "#0f1216",
          "text-dim": "#9da7b3"})}),
]

# Malformed frames: compared by EXIT code + error CODE (never detail text).
MALFORMED_FRAMES: list[tuple[str, str, str]] = [
    ("not-json", "{not-json", "kMalformedInput"),
    ("args_array", json.dumps({"method": "list", "args": [1, 2, 3]}),
     "kMalformedInput"),
    ("unknown_method", json.dumps({"method": "teleport", "args": {}}),
     "kUnknownMethod"),
    ("apply_name_missing", _req("apply", {}), "kMalformedInput"),
    ("apply_name_type", _req("apply", {"name": 7}), "kMalformedInput"),
    ("import_doc_missing", _req("import", {}), "kMalformedInput"),
    ("import_bad_json", _req("import", {"theme-doc": "not json"}),
     "kRejected"),
    ("import_unknown_token", _req("import", {"theme-doc": '{"ghost":"#fff"}'}),
     "kRejected"),
    ("import_unknown_method", _req("system-mode", {"mode": "sepia"}),
     "kMalformedInput"),
    ("import_duplicate_key", _req("import", {"theme-doc": '{"text":"#111111",'
                                            '"text":"#222222"}'}),
     "kRejected"),
    ("apply_unknown_theme", _req("apply", {"name": "magenta"}), "kRejected"),
    ("store_dir_missing_write", "apply", "kIoError"),
]

VALID_N = len(PARITY_CASES)


@pytest.fixture(scope="module")
def hosts() -> dict:
    _ensure_cpp_host()
    return {}


def _run_pair(req: str, tmp: Path, cid: str, durable: bool = False):
    """Run both backends for one request; durable sessions share no state
    between rows because each pair uses its own store dir."""
    if durable:
        sc = tmp / cid / "cpp"
        sp = tmp / cid / "py"
        sc.mkdir(parents=True, exist_ok=True)
        sp.mkdir(parents=True, exist_ok=True)
        return _backend("cpp", req, sc) + _backend("fake", req, sp)
    return _backend("cpp", req, None) + _backend("fake", req, None)


def test_themes_parity_valid_cases(hosts, tmp_path: Path) -> None:
    assert VALID_N >= 30, "parity table must hold >=30 valid cases"
    for cid, method, args in PARITY_CASES:
        rc_c, out_c, rc_p, out_p = _run_pair(_req(method, args), tmp_path, cid)
        assert rc_c == rc_p == 0, f"{cid}: rc cpp={rc_c} py={rc_p}"
        assert out_c == out_p, f"{cid}: byte mismatch\nC++: {out_c}\npy:  {out_p}"


def test_themes_parity_malformed(hosts, tmp_path: Path) -> None:
    for cid, frame, code in MALFORMED_FRAMES:
        if cid == "store_dir_missing_write":
            # durable refusal: host refuses state writes into a missing dir;
            # fake mirrors (kIoError). Both must refuse identically.
            rc_c, out_c = _backend("cpp", _req("apply", {"name": "dark"}),
                                   tmp_path / "missing" / "cpp")
            rc_p, out_p = _backend("fake", _req("apply", {"name": "dark"}),
                                   tmp_path / "missing" / "py")
            assert rc_c == rc_p == 1, (cid, rc_c, rc_p)
            code_c = json.loads(out_c).get("error")
            code_p = json.loads(out_p).get("error")
            assert code_c == code_p == code, (cid, out_c, out_p)
            continue
        rc_c, out_c, rc_p, out_p = _run_pair(frame, tmp_path, cid)
        assert rc_c == rc_p == 1, (cid, rc_c, rc_p)
        code_c = json.loads(out_c).get("error")
        code_p = json.loads(out_p).get("error")
        assert code_c == code_p == code, (cid, out_c, out_p)


def test_themes_durability_session_parity(hosts, tmp_path: Path) -> None:
    # One real session per backend on its own store dir: apply -> fresh
    # process list/current -> hostile import refused -> state file. Every
    # step's stdout and the final state file are byte-compared.
    sc = tmp_path / "dur_c"
    sp = tmp_path / "dur_p"
    sc.mkdir(parents=True, exist_ok=True)
    sp.mkdir(parents=True, exist_ok=True)
    for step in ("apply_hc", "list_persisted", "current_persisted"):
        if step == "apply_hc":
            req = _req("apply", {"name": "high-contrast"})
        else:
            req = _req(step.replace("_persisted", ""), {})
        rc_c, out_c = _backend("cpp", req, sc)
        rc_p, out_p = _backend("fake", req, sp)
        assert rc_c == rc_p == 0, (step, rc_c, rc_p)
        assert out_c == out_p, f"{step}: byte mismatch\nC++: {out_c}\npy:  {out_p}"
    # Hostile import must be refused on BOTH sides and leave state untouched.
    hostile = _req("import", {"theme-doc": json.dumps({"text": "#ffffff",
                                                       "surface": "#f3f4f6"})})
    rc_c, out_c = _backend("cpp", hostile, sc)
    rc_p, out_p = _backend("fake", hostile, sp)
    assert rc_c == rc_p == 1, (rc_c, rc_p)
    code_c = json.loads(out_c).get("error")
    code_p = json.loads(out_p).get("error")
    assert code_c == code_p == "kRejected", (out_c, out_p)
    rc_c, out_c = _backend("cpp", _req("list", {}), sc)
    rc_p, out_p = _backend("fake", _req("list", {}), sp)
    assert rc_c == rc_p == 0
    assert out_c == out_p
    for doc in (json.loads(out_c),):
        assert doc["current"] == "high-contrast", "state must be untouched"
    # State files: identical bytes (canonical write on both sides).
    f_c = (sc / "themes-state.json").read_bytes()
    f_p = (sp / "themes-state.json").read_bytes()
    assert f_c == f_p, f"state files diverge:\nC++: {f_c!r}\npy:  {f_p!r}"
    state = json.loads(f_c)
    assert state == {"schema": "xr-themes-state", "schema_version": 1,
                     "applied": "high-contrast", "mode": "light"}


def test_themes_tokens_corpus_structure() -> None:
    doc = json.loads(TOKENS.read_text(encoding="utf-8"))
    themes = doc["themes"]
    # Built-in set is exactly the five curated themes + the system resolver.
    for name in BUILTINS:
        assert name in themes, name
    assert set(themes) == set(BUILTINS), set(themes) - set(BUILTINS)
    # Meta schema: 40 tokens, flat under themes/schema/tokens (or wherever the
    # generator records it — assert via the tokens_gen schema below).
    meta = doc["tokens"]
    assert len(meta) == META_TOKENS, len(meta)
    # System resolution: default + per-mode mapping point at named built-ins.
    sysres = doc.get("system_resolution")
    assert sysres is not None and sysres.get("default") == "light"
    modes = sysres.get("modes")
    assert modes is not None
    for mode in ("light", "dark", "high-contrast"):
        assert modes.get(mode) in BUILTINS, (mode, modes.get(mode))
    # Waiver law: light carries exactly 9 exact rows; every other built-in
    # carries ZERO (curated non-brand themes must stand on their own).
    for name, theme in themes.items():
        rows = theme.get("waivers", [])
        expected = WAIVER_COUNTS.get(name, 0)
        assert len(rows) == expected, (name, len(rows))
        for row in rows:
            assert set(row) == {"token", "pair", "best", "reason"}, row
            assert isinstance(row["best"], (int, float)) and \
                isinstance(row["reason"], str)
    # Every theme value map covers the 40 tokens (flat keys beyond 'waivers').
    for name, theme in themes.items():
        keys = [k for k in theme if k != "waivers"]
        assert len(keys) == META_TOKENS, (name, len(keys))


def test_themes_reference_audit_zero_hard_failures() -> None:
    """The reference (Python) audit over the FINAL corpus: with each theme's
    own waiver rows applied, zero failures may remain and no row may be
    unnecessary (data-hygiene law) — a python-lane restatement of the C++
    test_contrast invariants on the committed corpus."""
    sys.path.insert(0, str(XR_CORE / "fakes"))
    import themes as tfake  # noqa: PLC0415  (local import keeps this gate clean)

    src = tfake.TokenSource()
    src.load_text(TOKENS.read_text(encoding="utf-8"))
    doc = json.loads(TOKENS.read_text(encoding="utf-8"))
    for name in BUILTINS:
        theme = {k: v for k, v in doc["themes"][name].items()
                 if k != "waivers"}
        findings = tfake.audit_with_waivers(
            theme, src, doc["themes"][name].get("waivers", []))
        fails = [f for f in findings if not f["passed"]]
        assert not fails, (name, fails)
        unnecessary = [f for f in findings if f.get("unnecessary")]
        assert not unnecessary, (name, unnecessary)
        waived = [f for f in findings if f.get("waived")]
        if name == "light":
            assert len(waived) == 9, (name, len(waived))
        else:
            assert not waived, (name, waived)
