#!/usr/bin/env python3
"""tools/date_ambient_probe.py — the ambient-clock half of the date-invariance
law, split out of tools/date_invariance_check.py by the touched-file size law
(P12-CLOSE T0-U1).

The half lives here so the probe's helper-tool discovery, its skip-policy
phrasing, and its displaced-lane runner do not push the checker body over
the 380-line ceiling. Nothing else in the tree imports this module; the
checker calls ``run_ambient_tier(..., want_strict=...)``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# `faketime` is an OPTIONAL EXTERNAL HELPER TOOL (apt install faketime) — a
# gate lane must never hard-require an optional tool (ADR-0047). Absence is a
# visible degradation, never a red gate and never a silent pass (the checker
# owns the two-tier verdict; this module only supplies the probe-and-lanes).
FAKETIME_LIB_CANDIDATES = (
    "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1",
    "/usr/lib/faketime/libfaketime.so.1",
    "/usr/lib/aarch64-linux-gnu/faketime/libfaketime.so.1",
    "/usr/local/lib/faketime/libfaketime.so.1",
)
SHIFTS = ("2019-03-04", "2031-11-23")


def have_faketime() -> bool:
    """The apt package's guaranteed surface: the launcher binary on PATH.
    XR_TEST_FAKETIME_ABSENT is a DEV/TEST seam (the negative fixture's
    deterministic 'tool absent' on a host that HAS the package)."""
    if os.environ.get("XR_TEST_FAKETIME_ABSENT"):
        return False
    import shutil
    if shutil.which("faketime"):
        return True
    return faketime_lib() is not None


def faketime_lib() -> str | None:
    """The preload shared object, if this machine has the apt package."""
    import glob
    for c in FAKETIME_LIB_CANDIDATES:
        if os.path.exists(c):
            return c
    for pat in ("/usr/lib/*/faketime/libfaketime.so.1",
                "/usr/lib*/faketime/libfaketime.so.1",
                "/usr/local/lib/faketime/libfaketime.so.1"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


def skip_policy_absent_reason(repo: Path) -> str | None:
    """The helper-tool absence phrasing, formatted by build/skip_policy.py
    (the single home of optional-tool SKIP text). None when unloadable."""
    sp = repo / "build" / "skip_policy.py"
    if not sp.exists():
        return None
    try:
        sys.path.insert(0, str(sp.parent))
        import importlib
        return importlib.import_module("skip_policy").tool_absent_reason(
            "faketime")
    except Exception:
        return None


def probe_self_check() -> str:
    """Prove the preload can displace a child clock, else return an error
    string. A preload that fails to bind would displace nothing, and every
    moved lane would equal its pinned baseline — reading exactly like 'the
    law holds' (the false-negative class a planted-defect fixture would
    catch). Returns '' on success."""
    check_env = {"LD_PRELOAD": faketime_lib(),
                 "FAKETIME": f"{SHIFTS[0]} 12:00:00",
                 "FAKETIME_NO_CACHE": "1"}
    r = subprocess.run(["date", "-u", "+%Y"], capture_output=True,
                       text=True, env={**os.environ, **check_env})
    year = SHIFTS[0].split("-")[0]
    if r.returncode == 0 and r.stdout.strip() == year:
        return ""
    return (f"LD_PRELOAD probe failed to displace a child clock "
            f"(date -u +%Y => {r.stdout.strip()!r}, rc={r.returncode}) — "
            f"the displacement is unproven, never claimed")


def run_ambient_tier(repo: Path, pinned_as_of: str, td: Path,
                     base: dict, env_date_runner) -> tuple[dict, str]:
    """Displace the wall clock at the gate's own pinned --as-of and re-run
    every lane, keyed `ambient:<lane>@<shift>`. Returns (extra_results,
    probe_error_string). The runner callable is the checker's `_run` so this
    module stays free of the lane definitions."""
    extra: dict[str, dict] = {}
    err = probe_self_check()
    if err:
        return extra, err
    for shift in SHIFTS:
        moved = env_date_runner(repo, pinned_as_of, td, env_date=shift)
        for lane in sorted(base):
            extra[f"ambient:{lane}@{shift}"] = moved[lane]
            extra.setdefault(f"ambient:{lane}@pinned", base[lane])
    return extra, ""
