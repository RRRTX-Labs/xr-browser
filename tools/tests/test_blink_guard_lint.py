"""blink_guard_lint.py: the P12 seam-guard lint (T1).

The interesting risk here is not that the lint fails to fire — it is that the
lint fires on nothing and prints PASS. A guard lint that counts zero hooks and
exits 0 is indistinguishable from a clean tree, so the value of this file is
almost entirely in the tests that pin the DETECTION rule against call shapes and
guard shapes that already exist in the tree.

Both halves of that rule were wrong once and neither was caught by running the
lint against the patch it was written for, because that patch happened to use
the shape the regexes accepted:

  * the guard regex was anchored at `^XR_`, which rejects `ENABLE_XR_SHIELD` —
    the guard the already-shipped P11 network seam (patch 0200) actually uses;
  * the call regex was anchored at the start of the line, which matches
    `blink::xr::OnDocumentStart(this);` but not
    `if (network::xr::XrShieldGate::ShouldBlock(*req)) {`.

Against patch 0200 the old lint reported `hooks: 0` and passed. `test_p11_patch_0200`
below is the test that would have caught it, and it runs against the real patch
file rather than a transcription of it.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
XR_CORE = TOOLS.parents[1] / "xr-core"
P11_PATCH = (XR_CORE / "patches/network-seams/0200-shield-network-seam"
             / "0200-shield-network-seam.patch")
P12_PATCH = (XR_CORE / "patches/blink-seams/0300-cosmetic-document-start"
             / "0300-cosmetic-document-start.patch")


def _lint():
    spec = importlib.util.spec_from_file_location(
        "blink_guard_lint", TOOLS / "blink_guard_lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patch(tmp_path: Path, added: list[str]) -> Path:
    """A one-hunk patch whose added lines are `added`."""
    f = tmp_path / "p.patch"
    lines = [
        "diff --git a/third_party/blink/renderer/core/dom/document.cc "
        "b/third_party/blink/renderer/core/dom/document.cc",
        "index 1111111..2222222 100644",
        "--- a/third_party/blink/renderer/core/dom/document.cc",
        "+++ b/third_party/blink/renderer/core/dom/document.cc",
        "@@ -100,4 +100,4 @@",
        " void Document::Foo() {",
    ]
    lines += [f"+{a}" for a in added]
    lines += ["   return;", " }"]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


# --- the rule, pinned against patches that already exist in the tree --------

def test_p11_patch_0200_detected(tmp_path: Path) -> None:
    """The shipped P11 seam must count as 2 guarded hooks.

    This is a regression test for both broken regexes at once: patch 0200 uses
    `ENABLE_XR_SHIELD` (rejected by the old guard rule) and calls through a
    static member inside an `if (` (invisible to the old call rule). With either
    half broken the count comes out 0 and the lint prints PASS.
    """
    if not P11_PATCH.is_file():
        pytest.skip(f"xr-core patch not checked out: {P11_PATCH}")
    res = _lint().scan_patch(P11_PATCH)
    assert res["hooks"] == 2, res
    assert res["guarded"] == 2, res
    assert res["violations"] == [], res["violations"]
    assert "ENABLE_XR_SHIELD" in res["guard_macros"], res["guard_macros"]
    assert "0200" in res["patch_ids"], res["patch_ids"]


def test_p12_patch_0300_detected(tmp_path: Path) -> None:
    """The P12 document-start seam: 1 hook, guarded, id cited at the call site."""
    if not P12_PATCH.is_file():
        pytest.skip(f"xr-core patch not checked out: {P12_PATCH}")
    res = _lint().scan_patch(P12_PATCH)
    assert res["hooks"] == 1, res
    assert res["guarded"] == 1, res
    assert res["violations"] == [], res["violations"]
    assert "ENABLE_XR_COSMETIC" in res["guard_macros"], res["guard_macros"]


@pytest.mark.parametrize("call", [
    "blink::xr::OnDocumentStart(this);",
    "network::xr::XrShieldGate::OnNetworkContextCreated(this);",
    "if (network::xr::XrShieldGate::ShouldBlock(*url_request_)) {",
    "  blink::xr::OnDocumentStart(doc);",
])
def test_call_shapes_recognised(tmp_path: Path, call: str) -> None:
    """Every call shape used in the tree is a hook, guarded or not."""
    res = _lint().scan_patch(_patch(tmp_path, [call]))
    assert res["hooks"] == 1, (call, res)


@pytest.mark.parametrize("line", [
    '#include "services/network/xr/xr_shield_gate.h"',
    '"xr/xr_shield_gate.cc",',
    "// see renderer/cosmetic/core/degrade.h",
])
def test_non_calls_not_counted(tmp_path: Path, line: str) -> None:
    """Includes, BUILD.gn source rows and comments name the seam without
    reaching it; counting them would inflate `hooks` and hide a missing one."""
    res = _lint().scan_patch(_patch(tmp_path, [line]))
    assert res["hooks"] == 0, (line, res)


@pytest.mark.parametrize("guard", [
    "#if defined(ENABLE_XR_COSMETIC)",
    "#if defined(ENABLE_XR_SHIELD)",
    "#if defined(XR_COSMETIC)",
    "#ifdef XR_COSMETIC",
])
def test_xr_guard_shapes_credited(tmp_path: Path, guard: str) -> None:
    """`ENABLE_XR_*` is Chromium's feature-gate shape and is XR-owned; a rule
    demanding a literal `XR_` prefix rejects the shipped P11 seam."""
    res = _lint().scan_patch(
        _patch(tmp_path, ["// P12 cosmetic seam (patch 0300)", guard,
                          "blink::xr::OnDocumentStart(this);",
                          "#endif  // ENABLE_XR_COSMETIC"]))
    assert res["hooks"] == 1 and res["guarded"] == 1, res
    assert res["violations"] == [], res["violations"]


# --- and the things the lint must reject -----------------------------------

def test_unguarded_call_fails(tmp_path: Path) -> None:
    res = _lint().scan_patch(
        _patch(tmp_path, ["// P12 cosmetic seam (patch 0300)",
                          "blink::xr::OnDocumentStart(this);"]))
    assert res["hooks"] == 1 and res["guarded"] == 0, res
    assert any("unguarded seam call" in v for v in res["violations"]), res


def test_upstream_builflag_is_not_a_guard(tmp_path: Path) -> None:
    """`#if BUILDFLAG(IS_FOO)` compiles the seam wherever upstream's flag is on,
    which has nothing to do with xr_shield_cosmetic_v1. Crediting it would let
    the seam into builds where the feature is off."""
    res = _lint().scan_patch(
        _patch(tmp_path, ["// P12 cosmetic seam (patch 0300)",
                          "#if BUILDFLAG(IS_FOO)",
                          "blink::xr::OnDocumentStart(this);", "#endif"]))
    assert res["guarded"] == 0, res
    assert any("upstream BUILDFLAG" in v for v in res["violations"]), res


def test_guard_in_other_hunk_is_not_credited(tmp_path: Path) -> None:
    """Guard depth is hunk-local. Crediting an `#if` from a different hunk would
    be a false PASS; instead the unbalanced guard is itself a finding."""
    f = tmp_path / "p.patch"
    f.write_text("\n".join([
        "diff --git a/a.cc b/a.cc",
        "index 1111111..2222222 100644",
        "--- a/a.cc", "+++ b/a.cc",
        "@@ -1,3 +1,4 @@",
        " void A() {",
        "+#if defined(ENABLE_XR_COSMETIC)",
        "+// P12 cosmetic seam (patch 0300)",
        " }",
        "@@ -50,3 +51,4 @@",
        " void B() {",
        "+blink::xr::OnDocumentStart(this);",
        "+#endif  // ENABLE_XR_COSMETIC",
        " }",
    ]) + "\n", encoding="utf-8")
    res = _lint().scan_patch(f)
    assert res["guarded"] == 0, res
    assert any("unguarded seam call" in v for v in res["violations"]), res
    assert any("hunk boundary" in v for v in res["violations"]), res


def test_missing_patch_id_comment_fails(tmp_path: Path) -> None:
    """A guarded call with no comment naming the patch id leaves the reader no
    way to reach the manifest row or the round-trip proof."""
    res = _lint().scan_patch(
        _patch(tmp_path, ["#if defined(ENABLE_XR_COSMETIC)",
                          "blink::xr::OnDocumentStart(this);",
                          "#endif  // ENABLE_XR_COSMETIC"]))
    assert res["hooks"] == 1 and res["guarded"] == 0, res
    assert any("no comment naming the patch id" in v
               for v in res["violations"]), res


# --- the zero case, and the end-to-end exit code ---------------------------

def test_no_blink_seams_patches_is_a_loud_note(tmp_path: Path) -> None:
    """Empty manifest is not a failure, but it must not print a bare PASS."""
    core = tmp_path / "xr-core"
    (core / "patches").mkdir(parents=True)
    (core / "patches/manifest.yaml").write_text("patches: []\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(TOOLS / "blink_guard_lint.py"),
         "--repo", str(tmp_path), "--xr-core", str(core)],
        capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
    assert "nothing to lint" in p.stdout, p.stdout
    assert "hooks: 0, guarded: 0" in p.stdout, p.stdout


def test_cli_pass_reports_nonzero_counts(tmp_path: Path) -> None:
    """PASS must carry the counts, so 'scanned nothing' and 'scanned N' differ."""
    if not P12_PATCH.is_file():
        pytest.skip(f"xr-core patch not checked out: {P12_PATCH}")
    p = subprocess.run(
        [sys.executable, str(TOOLS / "blink_guard_lint.py"),
         "--repo", str(TOOLS.parent), "--xr-core", str(XR_CORE)],
        capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
    assert "PASS: blink_guard_lint (hooks: 1, guarded: 1, unguarded: 0)" in p.stdout, p.stdout


def test_cli_fails_on_an_unguarded_manifest_row(tmp_path: Path) -> None:
    """End-to-end: a manifest row pointing at a patch with a bare call exits 1."""
    core = tmp_path / "xr-core"
    d = core / "patches/blink-seams/9999-bad"
    d.mkdir(parents=True)
    (core / "patches/manifest.yaml").write_text(
        'patches:\n  - id: "9999-bad"\n    category: blink_seams\n'
        '    dir: blink-seams/9999-bad\n', encoding="utf-8")
    (d / "9999-bad.patch").write_text("\n".join([
        "diff --git a/a.cc b/a.cc",
        "index 1111111..2222222 100644",
        "--- a/a.cc", "+++ b/a.cc",
        "@@ -1,3 +1,4 @@",
        " void A() {",
        "+// P12 cosmetic seam (patch 9999)",
        "+blink::xr::OnDocumentStart(this);",
        " }",
    ]) + "\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(TOOLS / "blink_guard_lint.py"),
         "--repo", str(tmp_path), "--xr-core", str(core)],
        capture_output=True, text=True)
    assert p.returncode == 1, p.stdout
    assert "unguarded: 1" in p.stdout, p.stdout
