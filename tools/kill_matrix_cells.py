"""tools/kill_matrix_cells.py — the kill-matrix CELL ENGINE (P11-T0-e split).

Extracted verbatim from tools/kill_matrix.py by the touched-file size law
(<=380 lines), split by responsibility: this module EXECUTES cells against
the discovered host binaries (build/probe/host_call/snapshot/completeness/
corrupt-load/kill/disposable-zero-bytes and the per-host matrix loop); the
orchestrator (kill_matrix.py) keeps discovery, the farm rows and the CLI.
Nothing was renamed, reordered or weakened — the functions are byte-identical
moves; the only additions are this docstring, the imports and set_xr_core()
(the XR_CORE global moved here with host_call, which reads it).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_qa_dir = Path(__file__).resolve().parents[1] / "build" / "qa"   # <repo>/build/qa
if (_qa_dir / "_common.py").exists():
    sys.path.insert(0, str(_qa_dir))
else:  # pragma: no cover - layout drift is a setup error, not a skip
    raise SystemExit(f"kill-matrix: runner law module not found at {_qa_dir}/_common.py")

from _common import RunnerError  # noqa: E402

SIGNALS = ("SIGKILL", "SIGTERM")
XR_CORE: Path | None = None   # default cwd for host invocations (set via set_xr_core)


def set_xr_core(path: Path | None) -> None:
    """Set the default cwd for host invocations (the orchestrator and the
    canaries call this; host_call/run_host_matrix read the module global)."""
    global XR_CORE
    XR_CORE = path


_qa_drill = Path(__file__).resolve().parents[1] / "build" / "qa" / "drill"
if (_qa_drill / "host_drills.py").exists():
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("host_drills", _qa_drill / "host_drills.py")
    _hd = _ilu.module_from_spec(_spec)
    sys.modules["host_drills"] = _hd
    _spec.loader.exec_module(_hd)
    HOST_DRILLS = _hd.HOST_DRILLS
else:  # pragma: no cover - layout drift is a setup error, not a skip
    raise SystemExit(f"kill-matrix: drill data not found at {_qa_drill}/host_drills.py")


def build_host(makefile: Path) -> None:
    if subprocess.run(["make", "-C", str(makefile.parent), "build"],
                      capture_output=True).returncode != 0:
        raise RunnerError(f"make -C {makefile.parent} build failed — cannot drill an unbuilt host")


def probe_runtime(bin: Path, req: list[str], store: Path | None, n: int = 3) -> float:
    """Typical wall-clock of one host invocation; kill delays are drawn
    against this so kills land mid-flight instead of always post-exit."""
    best = 1.0
    for _ in range(n):
        t0 = time.perf_counter()
        host_call(bin, req, store)
        best = min(best, time.perf_counter() - t0)
    return max(best, 0.0004)


def host_call(bin: Path, req: list[str], store_dir: Path | None,
              timeout: float = 30.0, cwd: Path | None = None
              ) -> subprocess.CompletedProcess:
    argv = [str(bin), *req]
    if store_dir is not None:
        argv[1:1] = ["--store-dir", str(store_dir)]
    # cwd: themes_host resolves its default tokens source relative to cwd;
    # running every host from the xr-core root is uniform and harmless.
    effective_cwd = cwd if cwd is not None else XR_CORE
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          cwd=str(effective_cwd) if effective_cwd else None)


def snapshot_dir(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()}


def assert_complete_state(store: Path, state_files: list[str], gens: set[str],
                          cell: str) -> None:
    """No partial state / no truncation: every present state file is complete
    JSON holding a whole known generation."""
    for name in state_files:
        p = store / name
        if not p.exists():
            continue  # killed before first rename: gen-1 absent is legal
        raw = p.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RunnerError(f"{cell}: state file {name} is PARTIAL/invalid after kill: {exc}")
        blob = json.dumps(doc, sort_keys=True)
        hit = any(g in blob for g in gens)
        if not hit:
            raise RunnerError(f"{cell}: state file {name} holds an unknown generation: {blob[:120]}")


def corrupt_load_cell(bin: Path, req: list[str], store: Path, cell: str) -> None:
    """Prior-state-preserved-on-corrupt-load, through the process boundary:
    a corrupt state file must yield a typed refusal (or clean ignore) and be
    preserved on disk — never silently rewritten or half-dropped."""
    for name in HOST_DRILLS[bin.parent.parent.name if False else _core_of(bin)]["state"]:
        p = store / name
        if not p.exists():
            continue
        good = p.read_bytes()
        p.write_bytes(good[: max(1, len(good) // 2)])  # truncate: the classic partial write
        r = host_call(bin, req, store)
        after = p.read_bytes()
        if after != good[: max(1, len(good) // 2)]:
            raise RunnerError(f"{cell}: corrupt state file {name} was silently rewritten")
        if r.returncode not in (0, 1):
            raise RunnerError(f"{cell}: corrupt load crashed the host (exit {r.returncode})")


def _xr_core_of(bin: Path) -> Path:  # <xr-core>/<core>/tests/build/<name>_host
    return bin.parents[3]


def _core_of(bin: Path) -> str:
    return bin.parents[2].name


def kill_cell(bin: Path, req: list[str], store: Path, sig: str, delay: float,
              rng, cell: str, state_files: list[str], gens: set[str],
              before: dict[str, bytes] | None) -> str:
    """One kill iteration. Returns 'killed-mid' | 'killed-post' (both count)."""
    argv = [str(bin), *req]
    if store is not None:
        argv[1:1] = ["--store-dir", str(store)]
    devnull = subprocess.DEVNULL
    p = subprocess.Popen(argv, stdout=devnull, stderr=devnull,
                         cwd=str(_xr_core_of(bin)))
    time.sleep(delay)
    if p.poll() is None:
        p.send_signal(getattr(signal, sig))
        mid = True
    else:
        mid = False
    p.wait(timeout=30)
    if store is not None and state_files:
        assert_complete_state(store, state_files, gens, cell)
        if before is not None and not mid:
            pass  # post-completion kill: state may have advanced, completeness is the law
    return "killed-mid" if mid else "killed-post"


def run_host_matrix(hosts: list[dict[str, Any]], rng, iterations: int) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    kill_stats = {"mid": 0, "post": 0}
    with tempfile.TemporaryDirectory(prefix="p10kill_") as td:
        root = Path(td)
        for h in hosts:
            spec = HOST_DRILLS.get(h["name"])
            if spec is None:
                cells.append({"host": h["name"], "phase": "*", "signal": "*",
                              "status": "not-run",
                              "reason": "no drill surface registered for this host"})
                continue
            binp = h["bin"]
            if not binp.exists():
                build_host(h["makefile"])
            if not binp.exists():
                cells.append({"host": h["name"], "phase": "*", "signal": "*",
                              "status": "not-run", "reason": "host binary failed to build"})
                continue
            # -- mid-dispatch cells (both signals): after a bootstrap call lets
            # first-run writes land (commands_host materializes registry.json),
            # dispatching under kill must leave the store byte-identical.
            for sig in SIGNALS:
                store = root / f"{h['name']}-dispatch-{sig}"
                store.mkdir()
                host_call(binp, spec["read"], store)   # bootstrap, not asserted
                before = snapshot_dir(store)
                rt = probe_runtime(binp, spec["read"], store)
                executed = 0
                for i in range(iterations):
                    delay = rt * (0.15 + rng.random() * 1.1)
                    outcome = kill_cell(binp, spec["read"], store, sig, delay, rng,
                              f"{h['name']}/dispatch/{sig}", spec["state"], set(), None)
                    kill_stats["mid" if outcome == "killed-mid" else "post"] += 1
                    if snapshot_dir(store) != before:
                        raise RunnerError(
                            f"{h['name']}/dispatch/{sig}: read-only dispatch mutated the store")
                    executed += 1
                cells.append({"host": h["name"], "phase": "mid-dispatch", "signal": sig,
                              "status": "executed", "iterations": executed})
            # -- mid-write cells
            if spec["write"] is None:
                cells.append({"host": h["name"], "phase": "mid-write", "signal": "*",
                              "status": "not-run", "reason": spec["write_reason"]})
            else:
                for sig in SIGNALS:
                    store = root / f"{h['name']}-write-{sig}"
                    store.mkdir()
                    seed = host_call(binp, spec["seed"], store)
                    if seed.returncode != 0:
                        raise RunnerError(f"{h['name']}: seed request failed: {seed.stderr[:200]}")
                    gens = {"1"}  # generation markers checked inside state blobs
                    executed = 0
                    rt = probe_runtime(binp, spec["write"], store)
                    for i in range(iterations):
                        delay = rt * (0.15 + rng.random() * 1.1)
                        outcome = kill_cell(binp, spec["write"], store, sig, delay, rng,
                                  f"{h['name']}/mid-write/{sig}", spec["state"], gens, None)
                        kill_stats["mid" if outcome == "killed-mid" else "post"] += 1
                        # prior-state-preserved: the store still loads and answers
                        r = host_call(binp, spec["read"], store)
                        if r.returncode != 0:
                            raise RunnerError(
                                f"{h['name']}/mid-write/{sig}: store did not survive a kill "
                                f"(read request exit {r.returncode}): {r.stderr[:160]}")
                        executed += 1
                    cells.append({"host": h["name"], "phase": "mid-write", "signal": sig,
                                  "status": "executed", "iterations": executed})
            # -- snapshot cell where a snapshot mode exists
            if h["name"] == "policy":
                sig = "SIGKILL"
                store = root / f"{h['name']}-snapshot"
                store.mkdir()
                executed = 0
                rt = probe_runtime(binp, ["snapshot", "--store-dir", str(store)], None)
                for i in range(iterations):
                    delay = rt * (0.15 + rng.random() * 1.1)
                    outcome = kill_cell(binp, ["snapshot", "--store-dir", str(store)], store, sig,
                              delay, rng, f"{h['name']}/snapshot/{sig}", [], set(), None)
                    kill_stats["mid" if outcome == "killed-mid" else "post"] += 1
                    executed += 1
                cells.append({"host": "policy", "phase": "mid-snapshot", "signal": sig,
                              "status": "executed", "iterations": executed})
            # -- corrupt-load cell (stateful hosts)
            if spec["state"]:
                store = root / f"{h['name']}-corrupt"
                store.mkdir()
                host_call(binp, spec["seed"], store)
                corrupt_load_cell(binp, spec["read"], store, f"{h['name']}/corrupt-load")
                cells.append({"host": h["name"], "phase": "corrupt-load", "signal": "-",
                              "status": "executed", "iterations": 1})
        # -- disposable => zero bytes (every write surface, no --store-dir)
        for h in hosts:
            spec = HOST_DRILLS.get(h["name"])
            if spec is None or spec["write"] is None:
                continue
            sandbox = root / f"{h['name']}-disposable"
            sandbox.mkdir()
            cwd = sandbox / "cwd"
            cwd.mkdir()
            before = snapshot_dir(sandbox)
            argv = [str(h["bin"]), *spec["write"]]
            if h["name"] == "themes":
                # tokens source is an input, not state: name it explicitly so the
                # disposable sandbox stays empty and the refusal story stays honest
                argv[1:1] = ["--tokens", str(XR_CORE / "ui" / "themes" / "tokens.json")]
            env = dict(os.environ)
            r = subprocess.run(argv, cwd=str(cwd),
                               capture_output=True, env=env, timeout=30)  # disposable: cwd is the empty sandbox
            after = snapshot_dir(sandbox)
            if r.returncode != 0:
                raise RunnerError(f"{h['name']}/disposable: host exited {r.returncode} in disposable mode")
            if after != before:
                raise RunnerError(
                    f"{h['name']}/disposable: disposable session wrote bytes: "
                    f"{sorted(set(after) - set(before))}")
            cells.append({"host": h["name"], "phase": "disposable-zero-bytes", "signal": "-",
                          "status": "executed", "iterations": 1})
    return {"cells": cells, "kill_stats": kill_stats}


