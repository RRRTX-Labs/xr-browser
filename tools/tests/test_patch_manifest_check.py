"""patch_manifest_check.py: the patch budget ledger (P12).

Until P12 nothing compared patches/manifest.yaml to the patches it describes, so
the category caps were prose: a row could declare fewer files than its patch
touched and the cap would never notice. The first P12 row did exactly that — 4
declared, 5 touched — which is the case `test_ledger_under_report` pins.

Every plant below is applied to a COPY of the real manifest under a temp
xr-core, never to the tree, and the clean control is asserted first so a plant
that silently fails to apply cannot read as a pass (a string-replace against a
differently-formatted YAML line is a no-op, and `blink_seams: { cap: 25 }` is
inline flow style here — that exact mistake was made once while writing this
file, and `test_cap_breach` now asserts its own mutation landed).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1]
XR_CORE = TOOLS.parents[1] / "xr-core"
P12_ID = "0300-cosmetic-document-start"
P12_DIR = "patches/blink-seams/0300-cosmetic-document-start"


def _core(tmp_path: Path) -> Path:
    """A temp xr-core holding only the real patches dir."""
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


def _manifest(core: Path) -> Path:
    return core / "patches" / "manifest.yaml"


def _rows(core: Path) -> list[dict]:
    return yaml.safe_load(_manifest(core).read_text())["patches"]


def _find(rows: list[dict], pid: str) -> dict:
    return next(r for r in rows if r.get("id") == pid)


def _write(core: Path, man: dict) -> None:
    _manifest(core).write_text(yaml.safe_dump(man, sort_keys=False),
                               encoding="utf-8")


def test_real_tree_is_clean() -> None:
    """The control. Run against the actual checkout, not a copy."""
    if not (XR_CORE / "patches/manifest.yaml").is_file():
        pytest.skip("xr-core not checked out")
    p = _run(XR_CORE)
    assert p.returncode == 0, p.stdout
    assert "PASS: patch_manifest_check" in p.stdout, p.stdout
    # Counts, not just PASS: the zero-case law.
    assert "patches: 4" in p.stdout and "files: 21" in p.stdout, p.stdout


def test_ledger_under_report(tmp_path: Path) -> None:
    """The direction that hides a cap breach: patch touches an undeclared file."""
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    row = _find(man["patches"], P12_ID)
    row["files"] = [f for f in row["files"]
                    if not f.endswith("core/xr/BUILD.gn")]
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not declare" in p.stdout, p.stdout
    assert "core/xr/BUILD.gn" in p.stdout, p.stdout


def test_ledger_over_report(tmp_path: Path) -> None:
    """The other direction: a declared file the patch never touches."""
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    _find(man["patches"], P12_ID)["files"].append(
        "third_party/blink/renderer/core/xr/NOT_IN_PATCH.cc")
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not touch" in p.stdout, p.stdout


def test_cap_breach(tmp_path: Path) -> None:
    """blink_seams declares 5 files; a cap of 4 must fail.

    Asserts the mutation landed, because the categories block is inline flow
    (`blink_seams: { cap: 25 }`) and a text replace aimed at block style is a
    silent no-op that would make this test vacuously pass.
    """
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    assert man["categories"]["blink_seams"]["cap"] == 25
    man["categories"]["blink_seams"]["cap"] = 4
    _write(core, man)
    assert yaml.safe_load(_manifest(core).read_text())[
        "categories"]["blink_seams"]["cap"] == 4, "mutation did not land"
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "5 declared file(s) > cap 4" in p.stdout, p.stdout


def test_total_cap_breach(tmp_path: Path) -> None:
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    man["total_cap"] = 3
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "4 patches > total_cap 3" in p.stdout, p.stdout


def test_unknown_category_is_uncapped_by_typo(tmp_path: Path) -> None:
    """An unknown category matches no cap, so it is unlimited by default."""
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    _find(man["patches"], P12_ID)["category"] = "blink_seam"
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "uncapped by default" in p.stdout, p.stdout


def test_duplicate_patch_id(tmp_path: Path) -> None:
    core = _core(tmp_path)
    man = yaml.safe_load(_manifest(core).read_text())
    man["patches"].append(dict(_find(man["patches"], P12_ID)))
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "duplicate patch id" in p.stdout, p.stdout


def test_path_outside_every_allowed_root(tmp_path: Path) -> None:
    """blink/** is on the §12.7 never-list; only core/** is an allowed root."""
    core = _core(tmp_path)
    patch = core / P12_DIR / f"{P12_ID}.patch"
    patch.write_text(patch.read_text() + "\n".join([
        "diff --git a/third_party/blink/renderer/platform/x.cc "
        "b/third_party/blink/renderer/platform/x.cc",
        "--- /dev/null",
        "+++ b/third_party/blink/renderer/platform/x.cc",
        "@@ -0,0 +1,1 @@",
        "+// outside the ledger", ""]), encoding="utf-8")
    man = yaml.safe_load(_manifest(core).read_text())
    _find(man["patches"], P12_ID)["files"].append(
        "third_party/blink/renderer/platform/x.cc")
    _write(core, man)
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "outside every allowed_root" in p.stdout, p.stdout


def test_missing_patchinfo(tmp_path: Path) -> None:
    core = _core(tmp_path)
    (core / P12_DIR / "patchinfo.md").unlink()
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "patchinfo.md is missing" in p.stdout, p.stdout


def test_missing_patch_file(tmp_path: Path) -> None:
    core = _core(tmp_path)
    (core / P12_DIR / f"{P12_ID}.patch").unlink()
    p = _run(core)
    assert p.returncode == 1, p.stdout
    assert "does not exist" in p.stdout, p.stdout


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
