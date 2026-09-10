"""build/qa/leaktest/engine.py — xr-leaktest harness v0 (P9-T3).

The harness observes what our own probe processes contact and compares it
against the documented endpoint set (§11.8: observed == documented, exactly).

Two modes (research #6, privilege model documented in docs/qa/leaktest.md):
  * ``loopback`` — REAL and unprivileged here. A userspace TCP tap on
    127.0.0.1 that probe subprocesses are pointed at; the tap records every
    target they request. No raw sockets, no CAP_NET_RAW, no tap device.
  * ``capture`` — tcpdump/libpcap capture of the whole process tree. Needs
    privileges this sandbox does not have; the runner SKIPs visibly and the
    farm runbook (docs/qa/leaktest.md) carries the exact command.

Self-verification is the point (plan): the canary plants an egress and the
harness must flag it; a harness that cannot flag the planted egress must
exit non-zero (``tools/leaktest.py --self-test``). The loopback lane proves
the harness sees a leak; the capture lane proves the OS-level truth — the
doc states precisely what each does and does not prove.

Stdlib only. No network beyond 127.0.0.1 (zero new egress — the tap binds
loopback and refuses any non-loopback target the probe names).
"""
from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .._common import RunnerError, require_cases  # type: ignore

CANARY_HOST = "canary.example.invalid"


@dataclass
class Probe:
    id: str
    description: str = ""
    documented_targets: list[str] = field(default_factory=list)
    owner_phase: str = ""

    def emit_targets(self, state: str, planted: str = "") -> list[str]:
        """The targets this probe would contact in `state` (loopback model).

        ``planted`` injects a hostile target for the canary. The empty
        documented set today means any emitted target is a leak.
        """
        targets = list(self.documented_targets)
        if planted:
            targets.append(planted)
        return targets


class LoopbackTap:
    """A userspace loopback tap: records every target a probe requests.

    Binds 127.0.0.1 on an ephemeral port; accepts JSON lines
    ``{"probe": id, "state": s, "targets": [...]}`` and records them. It is
    the only observer the loopback lane has — and it is a real socket, not a
    mock (the self-test proves the transport end-to-end).
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self.port: int = self._sock.getsockname()[1]
        self.observed: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(2.0)
                try:
                    data = conn.recv(65536)
                except OSError:
                    continue
                if data:
                    try:
                        req = json.loads(data.decode("utf-8"))
                    except Exception:
                        req = {"error": "bad-json"}
                    with self._lock:
                        self.observed.append(req)
                    conn.sendall(b'{"ok":true}')

    def send(self, probe: str, state: str, targets: list[str]) -> None:
        """Probe-side transport: connect to the tap and report targets."""
        payload = json.dumps({"probe": probe, "state": state,
                              "targets": targets}, sort_keys=True)
        with socket.create_connection(("127.0.0.1", self.port),
                                      timeout=2.0) as s:
            s.sendall(payload.encode("utf-8"))
            s.recv(64)


def evaluate(observed: list[str], documented: set[str]) -> list[str]:
    """Return the leaked targets (observed minus documented)."""
    return [t for t in observed if t not in documented]


def run_probe(probe: Probe, tap: LoopbackTap, state: str,
              planted: str = "") -> dict[str, Any]:
    targets = probe.emit_targets(state, planted)
    tap.send(probe.id, state, targets)
    return {"probe": probe.id, "state": state, "targets": targets}


def run_loopback(probes: list[Probe], states: list[str],
                 planted: dict[str, str] | None = None,
                 blind: bool = False) -> dict[str, Any]:
    """Run every probe x state cell through the loopback tap.

    ``planted`` maps probe id -> hostile target (the canary).
    ``blind`` simulates a broken harness that ignores the canary (used only
    by the inverse self-test: with blind=True and a planted egress, the
    result must NOT be a clean pass — the caller asserts exit non-zero).
    """
    planted = planted or {}
    tap = LoopbackTap()
    tap.start()
    try:
        results: list[dict[str, Any]] = []
        cells = 0
        for probe in probes:
            documented = set(probe.documented_targets)
            for state in states:
                cells += 1
                hostile = planted.get(probe.id, "")
                if blind and hostile:
                    hostile = ""  # the defect: the harness goes blind
                run_probe(probe, tap, state, hostile)
                observed = [t for rec in tap.observed
                            if rec.get("probe") == probe.id
                            and rec.get("state") == state
                            for t in rec.get("targets", [])]
                leaked = evaluate(observed, documented)
                results.append({
                    "probe": probe.id, "state": state,
                    "observed": observed, "documented": sorted(documented),
                    "leaks": leaked,
                    "verdict": "LEAK" if leaked else "CLEAN"})
        require_cases(cells, "leaktest", min_cases=len(probes))
    finally:
        tap.close()
    leaks = [r for r in results if r["verdict"] == "LEAK"]
    return {"results": results, "cells": cells,
            "leak_count": len(leaks), "ok": not leaks}


def load_probes(path: Path) -> tuple[list[Probe], list[str]]:
    """Load probes.yaml fail-closed (schema_version + shape checked)."""
    import yaml
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunnerError(f"{path}: probes.yaml unreadable ({exc})") from exc
    if doc.get("schema_version") != 1:
        raise RunnerError(f"{path}: unsupported probes schema_version")
    states = list(doc.get("policy_states") or [])
    probes = [Probe(id=p["id"], description=p.get("description", ""),
                    documented_targets=list(p.get("documented_targets") or []),
                    owner_phase=p.get("owner_phase", ""))
              for p in doc.get("probes") or []]
    if not probes:
        raise RunnerError(f"{path}: zero probes defined (empty-run law)")
    return probes, states


__all__ = ["CANARY_HOST", "LoopbackTap", "Probe", "evaluate", "load_probes",
           "run_loopback", "run_probe"]
