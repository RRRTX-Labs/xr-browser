"""patch_manifest_check.py: declared `files:` vs the patch's real diff.

The contract calls `files:` "metadata; the .patch is truth", and nothing else in
the tree compared the two — the first P12 row declared 4 files while its patch
touched 5, and `xr-patch lint` passed it correctly because that list is not its
input. `test_apply_lint_does_not_see_files_drift` pins that gap, so if
`build/patching/apply.py` ever grows the check this tool becomes redundant and
that test tells whoever did it to delete this file instead of maintaining two.

Every plant is applied to a COPY of the real manifest under a temp xr-core, and
the clean control is asserted first so a plant that silently fails to apply
cannot read as a pass.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
XR_CORE = TOOLS.parents[1] / "xr-core"
APPLY = REPO / "build" / "patching" / "apply.py"
P12_ID = "0300-cosmetic-document-start"
P12_DIR = "patches/blink-seams/0300-cosmetic-document-start"
OMITTED = "third_party/blink/renderer/core/xr/BUILD.gn"


def _core(tmp_path: Path) -> Path:
    src = XR_CORE / "patches"
    if not src.is_dir():
        pytest.skip(f"xr-core patches not checked out: {src}")
    dst = tmp_path / "xr-core"
    dst.mkdir()
    shutil.copytree(src, dst / "patches")
    return dst


def _run(core: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "patch_manifest_check.py"),
         "--xr-core", str(core)], capture_output=True, text=True)


def _apply_lint(core: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(APPLY), "lint",
         "--manifest", str(core / "patches/manifest.yaml"),
         "--xr-core", str(core)], capture_output=True, text=True)


def _manifest(core: Path) -> Path:
    return core / "patches" / "manifest.yaml"


def _write(core: Path, man: dict) -> None:
    _manifest(core).write_text(yaml.safe_dump(man, sort_keys=False),
                               encoding="utf-8")


def _omit(core: Path) -> None:
    """Declare one fewer file than the patch touches."""
    man = yaml.safe_load(_manifest(core).read_text())
    row = next(r for r in man["patches"] if r.get("id") == P12_ID)
    assert OMITTED in row["files"], "fixture assumption broken"
    row["files"] = [f for f in row["files"] if f != OMITTED]
    _write(core, man)


def test_real_tree_is_clean() -> None:
    """The control, against the actual checkout rather than a copy."""
    if not (XR_CORE / "patches/manifest.yaml").is_file():
        pytest.skip("xr-core not checked out")
    p = _run(XR_CORE)
    assert p.returncode == 0, p.stdout
    # Counts, not just PASS: the zero-case law.
    assert "patches: 4" in p.stdout and "files: 21" in p.stdout, p.stdout
    assert "drifted: 0" in p.stdout, p.stdout


def test_under_report(tmp_path: Path) -> None:
    """The direction that hides a file from budget_meter's registered_files()."""
    core = _core(tmp_path)
    _omit(core)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not declare" in p.stdout, p.stdout
    assert OMITTED in p.stdout, p.stdout


def test_over_report(tmp_path: Path) -> None:
    """The other direction: a declared file the patch never touches."""
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    next(r for r in man["patches"] if r.get("id") == P12_ID)["files"].append(
        "third_party/blink/renderer/core/xr/NOT_IN_PATCH.cc")
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not touch" in p.stdout, p.stdout


def test_both_directions_at_once(tmp_path: Path) -> None:
    core = _core(tmp_path)
    _omit(core)
    man = yaml.safe_load(_manifest(core).read_text())
    next(r for r in man["patches"] if r.get("id") == P12_ID)["files"].append(
        "third_party/blink/renderer/core/xr/NOT_IN_PATCH.cc")
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not declare" in p.stdout and "does not touch" in p.stdout
    assert "drifted: 2" in p.stdout, p.stdout


def test_empty_ledger_is_a_loud_note(tmp_path: Path) -> None:
    """No patches is legitimate, but must not print a bare PASS."""
    core = _core(tmp_path)
    _write(core, {"total_cap": 150, "allowed_roots": ["chrome/app/"],
                  "categories": {}, "patches": []})
    p = _run(core)
    assert p.returncode == 0, p.stdout
    assert "nothing to check" in p.stdout, p.stdout
    assert "patches: 0, files: 0" in p.stdout, p.stdout


def test_missing_manifest_fails(tmp_path: Path) -> None:
    p = _run(tmp_path / "absent")
    assert p.returncode == 1, p.stdout
    assert "not found" in p.stdout, p.stdout


def test_apply_lint_does_not_see_files_drift(tmp_path: Path) -> None:
    """The division of labour, pinned.

    `apply.py lint` owns caps, allowed_roots, patchinfo fields and duplicate ids
    — this tool must not re-implement them, and it does not. What it uniquely
    owns is the `files:`-vs-diff comparison. If this test starts failing, the
    check moved into apply.py and THIS FILE should be deleted rather than kept
    as a second opinion that can drift from the first.
    """
    if not APPLY.is_file():
        pytest.skip(f"apply.py not present: {APPLY}")
    core = _core(tmp_path)
    assert _apply_lint(core).returncode == 0, "control: real tree must lint"
    _omit(core)
    assert _apply_lint(core).returncode == 0, (
        "apply.py lint now sees files drift — delete patch_manifest_check.py "
        "instead of maintaining two implementations")
    assert _run(core).returncode == 1, "and this tool must still see it"
