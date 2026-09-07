"""build/skip_policy.py — optional external helper tools (P4-T0.1).

House law (L6): a test that cannot run is SKIPPED WITH A VISIBLE REASON,
never silently passed and never deleted. This module is the single place
that decides "can this run here?" for tools that are NOT vendored and NOT
a pip dependency (minisign, codesign, signtool, ... — all of which live on
a build/ops host but not on a bare machine or a GitHub-hosted runner).

Mirror of the assumptions-suite policy (build/upstream/assumptions.py):
SKIP is a first-class verdict with a reason string that must be printed in
the run summary, and a SKIP never counts as PASS.

Registered tools live in docs/dependencies/helper-tools.yaml (rationale +
install command per tool); this module reads the names, not the install
hints, so it stays importable with zero dependencies.

Exit/usage: pytest paths call pytest_skip_if_absent(); CLI paths call
require_tool() which raises ToolError (exit 1) with an install hint.
"""
from __future__ import annotations

import shutil
from typing import Any

# name -> (what it is used for here, install hint). Keep in sync with
# docs/dependencies/helper-tools.yaml (lint: tools/skip_policy_lint.py).
EXTERNAL_TOOLS: dict[str, dict[str, str]] = {
    "minisign": {
        "used_for": "TEST-ONLY artifact signature in the fast-lane drill (P3-T5)",
        "install": "apt-get install -y minisign (Ubuntu universe)",
    },
    "codesign": {
        "used_for": "macOS TEST signing passthrough (P2-T7)",
        "install": "Xcode command line tools (macOS runners only)",
    },
    "signtool": {
        "used_for": "Windows TEST signing passthrough (P2-T7)",
        "install": "Windows SDK (Windows runners only)",
    },
}

SKIP_PREFIX = "SKIP (tool absent: "


def tool_path(name: str) -> str | None:
    """Absolute path of an external tool, or None when it is not installed."""
    return shutil.which(name)


def tool_absent_reason(name: str) -> str | None:
    """Return the skip reason when `name` is absent, else None (present)."""
    if tool_path(name):
        return None
    meta = EXTERNAL_TOOLS.get(name, {})
    used = meta.get("used_for", "unregistered external tool")
    hint = meta.get("install", "see docs/dependencies/helper-tools.yaml")
    return (f"{SKIP_PREFIX}{name}) — needed for: {used}; "
            f"install hint: {hint}")


def skip_record(name: str) -> dict[str, Any] | None:
    """A machine-readable SKIP row (never a PASS row), or None if present."""
    reason = tool_absent_reason(name)
    if reason is None:
        return None
    return {"tool": name, "status": "SKIP", "reason": reason,
            "used_for": EXTERNAL_TOOLS.get(name, {}).get("used_for", ""),
            "install": EXTERNAL_TOOLS.get(name, {}).get("install", "")}


def require_tool(name: str) -> str:
    """CLI-side guard: raise ToolError (exit 1) with an install hint."""
    path = tool_path(name)
    if path is None:
        from _common import ToolError  # local import: keeps this module dep-free
        raise ToolError(
            f"external tool {name!r} is not installed; "
            f"{EXTERNAL_TOOLS.get(name, {}).get('install', 'see docs/dependencies/helper-tools.yaml')}")
    return path


def pytest_skip_if_absent(name: str) -> None:
    """Skip the running pytest test when `name` is absent (L6: visible)."""
    reason = tool_absent_reason(name)
    if reason is not None:
        import pytest
        pytest.skip(reason, allow_module_level=False)


def collect_skips() -> list[dict[str, Any]]:
    """SKIP rows for every registered tool missing on this host."""
    rows = [r for r in (skip_record(n) for n in EXTERNAL_TOOLS) if r]
    return rows


def summary_line(row: dict[str, Any]) -> str:
    return f"{row['status']}: {row['reason']}"
