"""build/qa/_common.py — the P9 runner law, shared by construction.

P9's central hazard is self-referential green: a proof machine that
certifies nothing. The two structural bugs that cause it are (a) "0 cases
run => PASS" and (b) "a runner that can never turn red". This module is the
single place both are enforced, and every P9 runner imports it — shared by
construction, not by convention (the plan's law, restated for this phase).

Conventions (house style, tools/_common.py + build/_common.py):
  * --help, --json, --check where applicable;
  * exit 0 pass · 1 fail · 2 usage · 77 skip-when-applicable;
  * frozen-clock law: every report that names a time takes it from
    ``--as-of`` (never wall-clock), so two runs with the same --as-of are
    byte-identical (determinism is a reproducibility rung, and P9's own
    reports must hit it).

Stdlib only (no new dependencies — DEPENDENCY RULES).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_SKIP = 77


class RunnerError(Exception):
    """Fail-closed runner error; the message is the reason, exit code 1."""


def require_cases(n: int, tool: str, *,
                  min_cases: int = 1) -> None:
    """The "no runner may PASS on zero cases" law.

    Every runner that reports a verdict must have executed at least
    ``min_cases`` cases. ``n`` is the runtime-derived count of cases the
    runner actually executed (never a hard-coded total). Raises RunnerError
    when the law is violated.
    """
    if n < min_cases:
        raise RunnerError(
            f"{tool}: executed {n} case(s) < required minimum {min_cases} "
            f"— a runner that passes on zero cases certifies nothing")


def as_of_arg(parser: argparse.ArgumentParser,
              default: str = "2026-09-10") -> None:
    """Register the frozen-clock ``--as-of`` argument (determinism law)."""
    parser.add_argument(
        "--as-of", default=default,
        help="frozen clock for report timestamps (default: %(default)s); "
             "two runs with the same --as-of must be byte-identical")


def iso(as_of: str) -> str:
    """Normalize an --as-of value to an ISO date (rejects junk)."""
    try:
        return datetime.strptime(as_of, "%Y-%m-%d").replace(
            tzinfo=timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    except ValueError as exc:
        raise RunnerError(f"--as-of {as_of!r} is not a YYYY-MM-DD date") from exc


def stable_json(obj: Any) -> str:
    """Canonical JSON (sorted keys, ASCII, no trailing newline)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed_rng(seed: int | str) -> "random.Random":
    """A deterministic Random from an int/str seed (no hash-order drift)."""
    import random
    return random.Random(str(seed))


def emit(tool: str, *, ok: bool, failures: list[str] | None = None,
         extra: dict[str, Any] | None = None, as_json: bool = False,
         status_note: str = "") -> int:
    """Print a house-style verdict line; return the exit code."""
    fails = failures or []
    payload = {"tool": tool, "status": "pass" if (ok and not fails) else "fail"}
    if extra:
        payload.update(extra)
    if status_note:
        payload["note"] = status_note
    if as_json:
        if fails:
            payload["failures"] = fails
        print(json.dumps(payload, sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        verdict = "PASS" if (ok and not fails) else "FAIL"
        if status_note:
            verdict += f" ({status_note})"
        print(f"{verdict}: {tool}")
    return EXIT_PASS if (ok and not fails) else EXIT_FAIL


def skip_visible(tool: str, reason: str, *, as_json: bool = False) -> int:
    """Print a visible SKIP (never a silent pass) and return EXIT_SKIP."""
    line = f"SKIP: {tool} skipped — {reason}"
    if as_json:
        print(json.dumps({"tool": tool, "status": "skip", "reason": reason},
                         sort_keys=True, indent=2))
    else:
        print(line)
    return EXIT_SKIP


def read_json(path: Path) -> Any:
    """Fail-closed JSON read (a malformed input is a failure, not None)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunnerError(f"{path}: not valid JSON ({exc})") from exc


def write_stable(path: Path, obj: Any, *, as_of: str) -> None:
    """Write canonical JSON with a recorded as-of (determinism law)."""
    if isinstance(obj, dict):
        obj = dict(obj)
        obj.setdefault("as_of", iso(as_of))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(obj) + "\n", encoding="utf-8")


def xr_core_root() -> Path:
    """Sibling xr-core checkout (the product tree). Fail-closed when absent."""
    here = Path(__file__).resolve().parents[2]      # build/qa/_common.py -> repo
    cand = (here.parent / "xr-core").resolve()
    if not (cand / ".git").exists() and not (cand / "README.md").exists():
        raise RunnerError(f"no xr-core sibling checkout at {cand}")
    return cand


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
