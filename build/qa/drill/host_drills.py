#!/usr/bin/env python3
"""build/qa/drill/host_drills.py — the hosts-local drill surface, as DATA.

The kill matrix's per-host drill rows (P10-T0-b), split out of
tools/kill_matrix.py so the runner stays under the 400-LOC law and the
data sits beside kill-matrix.yaml where the farm rows live. A host without
a binary write mode keeps its write cells NOT-RUN with the honest reason —
never silently dropped, never faked.
"""
from __future__ import annotations

from pathlib import Path

CHROMIUM_MATRIX = Path("build/qa/drill/kill-matrix.yaml")
SIGNALS = ("SIGKILL", "SIGTERM")
XR_CORE: Path | None = None   # default cwd for host invocations (set in main)

# Per-host drill surface. `write` is the state-mutating request (phase
# mid-write); `read` is a pure dispatch (phase mid-dispatch); `state` lists
# the on-disk files the write touches; `snapshot` marks hosts with a snapshot
# mode. A host without a binary write mode keeps its write cells NOT-RUN with
# the honest reason — never silently dropped, never faked.
HOST_DRILLS: dict[str, dict[str, Any]] = {
    "policy": {
        "core": "policy",
        "read": ["snapshot", "--diff"],
        "write": None,  # no binary write mode: store Save is library-level
        "write_reason": ("policy_host has no binary write mode (PolicyStore::Save "
                         "is library-level; the host write path lands with P11+ IPC) "
                         "— file-level law proven by policy/tests/test_store.cc"),
        "state": [],
        "seed": None,
    },
    "commands": {
        "core": "commands",
        "read": ["list"],
        "write": ["bindings-set", '{"command_id":"action.dial.fortress","accelerator":"Ctrl+Shift+9"}'],
        "seed": ["bindings-set", '{"command_id":"action.dial.standard","accelerator":"Ctrl+Shift+1"}'],
        "state": ["shortcuts.json", "policy-state.json"],
    },
    "settings": {
        "core": "settings",
        "read": ["sections"],
        "write": ["search", '{"query":"tracker blocking"}'],
        "seed": ["search", '{"query":"seed query"}'],
        "state": ["settings-counters.json"],
    },
    "themes": {
        "core": "themes",
        "read": ["list"],
        "write": ["apply", '{"name":"dark"}'],
        "seed": ["apply", '{"name":"light"}'],
        "state": ["xr-themes-state.json"],
    },
}


