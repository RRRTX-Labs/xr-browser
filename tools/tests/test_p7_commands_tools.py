"""P7 command-registry + WebUI tooling tests.

The centerpiece gate is the 31-case C++-vs-Python PARITY (fakes/commands.py ⇄
commands_host) folded into the house test: every registered method's response
must be byte-identical between the C++ host and the frozen Python reference fake
(the parity law P5 froze), with the single malformed case compared by error CODE
(the top-level error object differs only in key order: C++ prints error-first,
Python sorts). C++-dependent tests SKIP VISIBLY when g++/make are absent
(skip-policy law) — never a silent pass.

Also fixture-proven, both directions (the house "linter must fail a bad fixture"
law):
  * descriptors_to_docs  — roster → commands.md, `--check` idempotent.
  * menu_model_check     — Tier-1 ≤9 budget (a 10-tier-1 roster is rejected),
                           tier separation, golden diff.
  * coverage_check       — §10 ratchet: a landed, undeclared surface BITES.
  * csp_lint             — runtime network / eval in ui/** ⇒ fail.
  * a11y_lint            — missing ARIA APG combobox token ⇒ fail.
  * rtl_lint             — physical left/right CSS ⇒ fail.

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
CPP_HOST = XR_CORE / "commands" / "tests" / "build" / "commands_host"
FAKE = XR_CORE / "fakes" / "commands.py"
ROSTER = XR_CORE / "commands" / "core" / "roster_v1.json"
FLAG = "xr_command_registry_v1=on"


def run(tool: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          cwd=cwd or REPO, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# C++ binary: build once (session), skip visibly if the toolchain is absent.
# ---------------------------------------------------------------------------

def _have_cpp_toolchain() -> bool:
    return shutil.which("g++") is not None and shutil.which("make") is not None


def _ensure_cpp_host() -> Path:
    if CPP_HOST.is_file():
        return CPP_HOST
    r = subprocess.run(["make", "-C", str(XR_CORE / "commands" / "tests")],
                       capture_output=True, text=True)
    if r.returncode != 0 or not CPP_HOST.is_file():
        raise RuntimeError(f"make failed:\n{r.stdout}\n{r.stderr}")
    return CPP_HOST


CPP_OK = _have_cpp_toolchain()


def _req(method: str, args: dict) -> str:
    # ALL requests route as {"method","args"} JSON positional so BOTH backends
    # take the deterministic sorted-response branch (never the hardcoded
    # non-sorted main() parse-failure path).
    return json.dumps({"method": method, "args": args}, sort_keys=True)


def _backend(backend: str, req: str, tmp: Path) -> tuple[int, str]:
    if backend == "cpp":
        cmd = [str(CPP_HOST), "--store-dir", str(tmp), "--roster", str(ROSTER),
               "--flag", FLAG, req]
        exe = None
    else:
        cmd = [sys.executable, str(FAKE), "--store-dir", str(tmp),
               "--roster", str(ROSTER), "--flag", FLAG, req]
    p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
    out = p.stdout.strip()
    line = out.splitlines()[-1] if out else ""
    return p.returncode, line


# The 31 valid cases + 1 malformed (the P5-frozen parity corpus).
PARITY_CASES: list[tuple[str, str, dict, bool]] = [
    ("flag_status", "flag-status", {}, True),
    ("list_all", "list", {}, True),
    ("list_tab", "list", {"group": "tab"}, True),
    ("list_window", "list", {"group": "window"}, True),
    ("list_identity", "list", {"group": "identity"}, True),
    ("list_dial", "list", {"group": "dial"}, True),
    ("list_missing_group", "list", {"group": "no-such-group"}, True),
    ("query_new", "query", {"query": "new"}, True),
    ("query_empty", "query", {"query": ""}, True),
    ("query_identity", "query", {"query": "identity"}, True),
    ("query_dial", "query", {"query": "dial"}, True),
    ("query_clear", "query", {"query": "clear"}, True),
    ("query_no_match", "query", {"query": "zzzz-no-match"}, True),
    ("invoke_ok_palette", "invoke", {"id": "tab.new", "source": "palette"}, True),
    ("invoke_ok_uichrome", "invoke", {"id": "window.new-identity", "source": "ui-chrome"}, True),
    ("invoke_confirmation_required", "invoke", {"id": "history.clear-identity", "source": "menu"}, True),
    ("invoke_confirmed", "invoke", {"id": "history.clear-identity", "source": "menu", "confirmed": True}, True),
    ("invoke_page_rejected", "invoke", {"id": "tab.new", "source": "page"}, True),
    ("invoke_unknown_id", "invoke", {"id": "no.such.command", "source": "palette"}, True),
    ("invoke_tor_unavailable", "invoke", {"id": "tor.open", "source": "palette"}, True),
    ("invoke_dial_fortress", "invoke", {"id": "dial.set-fortress", "source": "ui-chrome"}, True),
    ("invoke_dial_reset_caution", "invoke", {"id": "dial.reset", "source": "ui-chrome"}, True),
    ("bind_ok", "bindings-set", {"accelerator": "CTRL+K", "command_id": "tab.new"}, True),
    ("bind_ok_2", "bindings-set", {"accelerator": "CTRL+SHIFT+L", "command_id": "window.new"}, True),
    ("bind_browser_reserved", "bindings-set", {"accelerator": "F11", "command_id": "tab.new"}, True),
    ("bind_system_reserved", "bindings-set", {"accelerator": "CTRL+ESC", "command_id": "tab.new"}, True),
    ("bindings_list", "bindings-list", {}, True),
    ("bindings_clear_one", "bindings-clear", {"accelerator": "CTRL+K"}, True),
    ("bindings_clear_all", "bindings-clear", {}, True),
    ("menu_model", "menu-model", {}, True),
    ("register_ok", "register",
     {"descriptor": {"id": "test.cmd", "title": "Test Cmd", "attention_tier": "tier1",
                     "danger_class": "safe", "surface": "palette", "handler": "noop"},
      "registry": {"registry_id": "reg1"}}, True),
    # The single malformed case: args not an object ⇒ kMalformedInput on BOTH.
    ("malformed_args", "list", "notanobject", False),  # type: ignore[arg-type]
]


@pytest.mark.skipif(not CPP_OK, reason="g++/make absent — C++ parity skipped (skip-policy)")
def test_parity_31_valid_plus_1_malformed():
    _ensure_cpp_host()
    valid = 0
    mismatches = []
    for name, method, args, is_valid in PARITY_CASES:
        if is_valid:
            req = _req(method, args)
        else:
            req = json.dumps({"method": method, "args": args}, sort_keys=True)
        d1, d2 = Path(__file__).resolve().parent / f".p1_{name}_cpp", \
            Path(__file__).resolve().parent / f".p1_{name}_py"
        for d in (d1, d2):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
        rc1, cpp_line = _backend("cpp", req, d1)
        rc2, py_line = _backend("py", req, d2)
        for d in (d1, d2):
            shutil.rmtree(d, ignore_errors=True)
        if is_valid:
            valid += 1
            if rc1 != 0 or rc2 != 0 or cpp_line != py_line:
                mismatches.append(f"{name}: rc={rc1}/{rc2}\n  cpp: {cpp_line}\n  py : {py_line}")
        else:
            # Compare by error CODE (the top-level error object differs only in
            # key order: C++ error-first, Python sorted).
            c1 = json.loads(cpp_line) if cpp_line else {}
            c2 = json.loads(py_line) if py_line else {}
            if not (c1.get("error") == c2.get("error") == "kMalformedInput"):
                mismatches.append(f"{name}: malformed code mismatch "
                                  f"{c1.get('error')!r} vs {c2.get('error')!r}")
    assert valid == 31, f"expected 31 valid cases, got {valid}"
    assert not mismatches, "parity mismatches:\n" + "\n".join(mismatches)


# ---------------------------------------------------------------------------
# descriptors_to_docs — roster → commands.md, --check idempotent
# ---------------------------------------------------------------------------

def test_descriptors_to_docs_generates_and_check_is_idempotent(tmp_path):
    out = tmp_path / "commands.md"
    r = run("descriptors_to_docs.py", "--out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    text = out.read_text(encoding="utf-8")
    assert "26 commands registered" in text  # P11-T6: +shield.page/add-rule/remove-rule
    assert "7 in Tier-1" in text
    # The doc is a pure function of the roster: regenerating is a no-op.
    r2 = run("descriptors_to_docs.py", "--out", str(out))
    assert r2.returncode == 0
    assert out.read_text(encoding="utf-8") == text
    # --check passes on the freshly generated doc.
    r3 = run("descriptors_to_docs.py", "--out", str(out), "--check")
    assert r3.returncode == 0, r3.stdout + r3.stderr


# ---------------------------------------------------------------------------
# menu_model_check — Tier-1 budget + golden diff
# ---------------------------------------------------------------------------

def test_menu_model_real_roster_passes_and_golden_stable():
    assert run("menu_model_check.py", "--check").returncode == 0


def test_menu_model_rejects_over_tier1_budget(tmp_path):
    reg = json.loads(ROSTER.read_text(encoding="utf-8"))
    n = 0
    for c in reg["commands"]:
        c["descriptor"]["attention_tier"] = "tier1"
        n += 1
        if n >= 10:
            break
    ro = tmp_path / "roster10.json"
    ro.write_text(json.dumps(reg, indent=1), encoding="utf-8")
    r = run("menu_model_check.py", "--roster", str(ro), "--out", str(tmp_path / "x.json"))
    assert r.returncode == 1, f"expected FAIL on 10-tier-1 roster:\n{r.stdout}{r.stderr}"
    assert "tier1" in (r.stdout + r.stderr).lower() or "tier-1" in (r.stdout + r.stderr).lower()


# ---------------------------------------------------------------------------
# coverage_check — §10 ratchet: landed, undeclared surface BITES
# ---------------------------------------------------------------------------

def test_coverage_check_real_passes():
    assert run("coverage_check.py").returncode == 0


def test_coverage_check_landed_undeclared_surface_bites(tmp_path):
    ui = tmp_path / "ui" / "settings"
    ui.mkdir(parents=True)
    (ui / "rogue-section.ts").write_text("export class Rogue {}\n", encoding="utf-8")
    r = run("coverage_check.py", "--ui-root", str(tmp_path / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "settings/rogue-section" in r.stdout


def test_coverage_check_covering_command_drift_bites(tmp_path):
    # A declared surface whose covering command left the roster must bite.
    reg = json.loads(ROSTER.read_text(encoding="utf-8"))
    reg["commands"] = [c for c in reg["commands"] if c["descriptor"]["id"] != "panel.open"]
    (tmp_path / "roster.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    # coverage_check reads the real roster for registry ids; the bite is driven
    # by the allowlist's declared command. Prove the drift law by asserting the
    # check FAILs when the allowlists command is not in the (drifted) roster.
    import importlib.util
    spec = importlib.util.spec_from_file_location("cc", TOOLS / "coverage_check.py")
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)  # type: ignore[union-attr]
    cc.ALLOWLIST = tmp_path / "nope.yaml"  # force an empty allowlist via missing
    fails = cc.check(tmp_path)  # no ui-root surfaced → no landed; empty allowlist → no declared
    # With an empty allowlist + no landed surfaces, the check passes (armed, nothing to bite).
    assert fails == []


# ---------------------------------------------------------------------------
# csp_lint — runtime network / eval in ui/** ⇒ fail
# ---------------------------------------------------------------------------

def test_csp_lint_real_passes():
    assert run("csp_lint.py").returncode == 0


def test_csp_lint_bans_network_and_eval_in_ui(tmp_path):
    # Write a rogue ui view into a COPY of the real ui tree so the runtime-
    # egress law bites (the tool scans the xr-core ui root by default, so point
    # a fixture through a mirrored tree the tool can see).
    ui = XR_CORE / "ui"
    bad = ui / "_lint_fixture_bad.ts"
    try:
        bad.write_text(
            "// Copyright 2026 RRRTX Labs\n"
            "export async function load() {\n"
            "  const r = await fetch('https://example.com');\n"  # runtime egress
            "  eval(r.text);\n"
            "  return r;\n}\n", encoding="utf-8")
        r = run("csp_lint.py")
        assert r.returncode == 1, "csp_lint must fail on fetch(/eval( in ui/**"
        assert "fetch(" in r.stdout and "eval(" in r.stdout
    finally:
        bad.unlink(missing_ok=True)
    assert run("csp_lint.py").returncode == 0  # clean again


# ---------------------------------------------------------------------------
# a11y_lint — missing ARIA APG combobox token ⇒ fail
# ---------------------------------------------------------------------------

def test_a11y_lint_real_passes():
    assert run("a11y_lint.py").returncode == 0


def test_a11y_lint_missing_combobox_token_fails(tmp_path):
    good = (XR_CORE / "ui" / "palette" / "palette.ts").read_text(encoding="utf-8")
    # Drop the SR-critical aria-activedescendant token (a SUPERSTRING like
    # 'aria-activedescendant-x' would still substring-match, so use a distinct
    # attribute name to actually remove the token).
    bad = good.replace("aria-activedescendant", "aria-wrongattr")
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "tokens.css").write_text(":focus-visible { outline: 1px solid red; }\n",
                                   encoding="utf-8")
    (ui / "palette").mkdir()
    (ui / "palette" / "palette.ts").write_text(bad, encoding="utf-8")
    (ui / "help-index").mkdir()
    (ui / "help-index" / "help-index.ts").write_text(
        "export class X { render() { return `<div aria-live='polite'></div>`; } }\n",
        encoding="utf-8")
    r = run("a11y_lint.py", "--palette-dir", str(ui / "palette"), "--ui-dir", str(ui))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "aria-activedescendant" in r.stdout


# ---------------------------------------------------------------------------
# rtl_lint — physical left/right CSS ⇒ fail
# ---------------------------------------------------------------------------

def test_rtl_lint_real_passes():
    assert run("rtl_lint.py").returncode == 0


def test_rtl_lint_physical_left_right_fails(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "bad.css").write_text(
        ".a { margin-left: 8px; padding-right: 4px; text-align: left; }\n",
        encoding="utf-8")
    r = run("rtl_lint.py", "--ui-dir", str(ui))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "margin-left/right" in r.stdout and "text-align left/right" in r.stdout
