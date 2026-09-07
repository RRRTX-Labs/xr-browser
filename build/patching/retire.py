"""build/patching/retire.py — `xr-patch retire` (P3-T7, §12.5).

The ONLY sanctioned patch-removal path: appends the seam-retirement ledger
row (build/upstream/retirements.json, meta repo) AND surgically removes the
patch from the manifest + tree (xr-core), rolling the manifest back if the
ledger append fails. Removal without a ledger entry fails retirement-lint
(CI). Extracted from apply.py to keep files under the 400-LOC law.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _common import ToolError, emit, repo_root  # noqa: E402


def cmd_retire(args: argparse.Namespace) -> int:
    """xr-patch retire — the only sanctioned patch-removal path (P3-T7)."""
    import importlib.util
    import shutil
    from apply import _load_yaml, load_deps  # sibling module (runtime import)
    root = repo_root()
    spec = importlib.util.spec_from_file_location(
        "xr_retirements", root / "build" / "upstream" / "retirements.py")
    retirements = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retirements)  # type: ignore[union-attr]

    manifest_path, _ = _resolve_manifest(args)
    manifest = _load_yaml(manifest_path)
    entry = next((p for p in manifest.get("patches", []) if p.get("id") == args.id), None)
    if entry is None:
        raise ToolError(f"--id {args.id!r} not found in {manifest_path}")

    rev_retired_at = args.rev_retired_at
    if not rev_retired_at:
        rev_retired_at = str(load_deps(root).get("chromium_rev", "<unknown>"))

    import subprocess
    who = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True)
    retired_by = who.stdout.strip() or "unknown@rrrtx.example"

    # surgery first (rollback-able); ledger append validates its own args
    original_manifest = manifest_path.read_text(encoding="utf-8")
    pdir = manifest_path.parent / entry.get("dir", "")
    pdir_existed = pdir.exists()
    import tempfile as _tf, shutil as _sh
    pdir_backup = None
    if pdir_existed:
        pdir_backup = Path(_tf.mkdtemp(prefix="xr-retire-")) / pdir.name
        _sh.copytree(pdir, pdir_backup)
    try:
        retirements.remove_patch_from_manifest(manifest_path, args.id)
        if pdir_existed:
            shutil.rmtree(pdir)
        row = retirements.append_retirement(
            root, patch_id=args.id, mechanism=args.mechanism,
            evidence=args.evidence, note=args.note,
            rev_retired_at=rev_retired_at, retired_by=retired_by)
    except Exception:
        manifest_path.write_text(original_manifest, encoding="utf-8")
        if pdir_backup is not None and pdir.exists() is False and pdir_backup.exists():
            _sh.copytree(pdir_backup, pdir)
        raise

    print(f"retired {args.id} ({args.mechanism}) — ledger row written, patch removed")
    print(f"  ledger: {retirements.LEDGER_PATH} (meta repo — commit it)")
    print(f"  xr-core: manifest + {entry.get('dir')} removed — commit the sibling repo")
    print("  both commits together close the retirement (retirement-lint enforces linkage)")
    return emit(args.json, {"tool": "xr-patch", "cmd": "retire", "retired": row})


def _resolve_manifest(args: argparse.Namespace) -> tuple[Path, Path]:
    checkout = Path(args.checkout).resolve() if args.checkout else Path.cwd() / "chromium"
    if args.manifest:
        return Path(args.manifest).resolve(), checkout
    return checkout / "src" / "xr" / "patches" / "manifest.yaml", checkout


