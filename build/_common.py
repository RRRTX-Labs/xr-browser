"""Shared helpers for XR Browser build tooling (Phase P2).

Stdlib-first, same house style as tools/_common.py: every tool exposes --help,
supports --json, and exits 0 = pass, 1 = fail, 2 = usage error. MOCK MODE is
enforced here: when XR_ALLOW_MOCK=1 is set, every emitted line is prefixed
"MOCK MODE — not a build" (Plan P2: mock tests plumbing only, never evidence).

This module is deliberately small and does NOT import tools/_common.py: the
build tools are a separate, self-contained surface (Plan §7.1 `build/`).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

DEPS_FILE = "DEPS"  # repo root pin file (single source of truth)


class ToolError(Exception):
    """Fail-closed tool error; message is the reason, exit code 1."""


def repo_root(start: str | os.PathLike | None = None) -> Path:
    cur = Path(start or Path.cwd()).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / ".git").exists():
            return cand
    raise ToolError(f"no git repository found at or above {cur}")


def load_deps(root: Path) -> dict[str, Any]:
    """Load DEPS (YAML) fail-closed. Returns dict or raises ToolError."""
    try:
        import yaml  # pinned dev dependency (tools/requirements-dev.txt)
    except ImportError as exc:  # pragma: no cover
        raise ToolError(f"PyYAML not importable ({exc}); install pinned dev deps") from exc
    p = root / DEPS_FILE
    if not p.exists():
        raise ToolError(f"missing {DEPS_FILE} at {root}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"DEPS parse failure: {exc}") from exc
    if not isinstance(data, dict):
        raise ToolError("DEPS: top level must be a mapping")
    return data


def mock_enabled() -> bool:
    return os.environ.get("XR_ALLOW_MOCK") == "1"


def emit(as_json: bool, result: dict[str, Any], *, failures: list[str] | None = None) -> int:
    """Print result (mock-prefixed when in mock mode); return exit code."""
    ok = not (failures or [])
    if as_json:
        out = dict(result)
        out["status"] = "pass" if ok else "fail"
        if failures:
            out["failures"] = failures
        print(json.dumps(out, indent=2))
    else:
        prefix = "MOCK MODE — not a build: " if mock_enabled() else ""
        for line in failures or []:
            print(f"{prefix}FAIL: {line}")
        print(f"{prefix}{'PASS' if ok else 'FAIL'}: {result.get('tool', 'tool')}")
    return EXIT_PASS if ok else EXIT_FAIL


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command locally (no shell), streaming stdout; fail-loud on error."""
    if mock_enabled():
        print(f"MOCK MODE — not a build: would run: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    proc = subprocess.run(cmd, cwd=cwd, text=True)
    if check and proc.returncode != 0:
        raise ToolError(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit JSON output")


def main_with_guard(fn: Any) -> None:
    try:
        rc = fn()
    except ToolError as exc:
        prefix = "MOCK MODE — not a build: " if mock_enabled() else ""
        print(f"{prefix}error: {exc}", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    except SystemExit as exc:
        sys.exit(EXIT_USAGE if exc.code not in (0, EXIT_USAGE) else exc.code)
    sys.exit(rc if isinstance(rc, int) else EXIT_PASS)


# --- bare-name collision union (P10) -------------------------------------
# The build/*/ kits are all importable as the bare name `_common`; whichever
# copy binds first in a shared interpreter (pytest collection) must carry the
# UNION of the kit APIs, or the other kit's importers break (observed:
# branding's `from _common import ToolError` died on build/qa's copy). Load
# the SIBLING kit by explicit path and re-export the names this file lacks.
def _xr_union_sibling_kit() -> None:  # noqa: D401 - module-level side import
    import importlib.util as _ilu
    _sib = Path(__file__).resolve().parent.parent / "_common.py"
    if not _sib.exists() or _sib.resolve() == Path(__file__).resolve():
        return
    _spec = _ilu.spec_from_file_location("_xr_build_common_sibling", _sib)
    if _spec is None or _spec.loader is None:
        return
    _mod = _ilu.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_mod)
    except Exception:
        return  # a broken sibling must not break THIS kit's importers
    import builtins as _bi
    for _nm in dir(_mod):
        if _nm.startswith("_"):
            continue
        if _nm not in globals():
            globals()[_nm] = getattr(_mod, _nm)  # noqa: PLC0206 - union export
    del _bi


_xr_union_sibling_kit()
