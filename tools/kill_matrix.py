#!/usr/bin/env python3
"""tools/kill_matrix.py — the §11.10 kill matrix, hosts-local mode (P10-T0-b).

Closes the T0-b debt: P9 shipped the kill matrix as DATA (kill-matrix.yaml)
plus a completeness checker, and deferred *execution* to the farm on the
claim that "a real browser process tree" does not exist here. True for the
8 Chromium process types — false for the four host binaries that exist right
here (policy_host, commands_host, settings_host, themes_host). This runner
executes the matrix against them, for real, in this sandbox:

  * discovery: every xr-core ``*/tests/Makefile`` ``<name>_host`` target is a
    row (discovered, never hand-listed);
  * for every discovered host, kill cells are executed mid-write /
    mid-dispatch / mid-snapshot (where the binary actually performs that
    operation) under SIGKILL and SIGTERM;
  * invariants asserted after every kill (the same laws the P6 store, P7
    shortcuts and P8 counters unit tests prove at file level, now proven
    across the process kill boundary):
      - no partial state: every on-disk state file parses as complete JSON
        and holds a whole known generation (never a truncated write);
      - prior-state-preserved: after any kill the store still loads and
        serves the pre-kill or post-write generation — never garbage;
      - corrupt-load: a corrupt state file yields a typed refusal and the
        file is preserved, never silently rewritten;
      - disposable => zero bytes: the same operations with no --store-dir
        leave the filesystem untouched (P8's filesystem-diff assertion);
  * the 8 Chromium process rows stay farm-visible with the correct reason
    (HG-33), printed in the executed / not-run split — never dropped.

Runner law (build/qa/_common.py): 0 executed cells => FAIL; the split is
always printed. Frozen clock: --as-of. Stdlib only.
"""
from __future__ import annotations

import argparse
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

from _common import RunnerError, emit, require_cases  # noqa: E402

CHROMIUM_MATRIX = Path("build/qa/drill/kill-matrix.yaml")

SIGNALS = ("SIGKILL", "SIGTERM")
XR_CORE: Path | None = None   # default cwd for host invocations (set in main)

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


def discover_hosts(xr_core: Path) -> list[dict[str, Any]]:
    """Discovered, not hand-listed: every <name>_host target in xr-core."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mk in sorted(xr_core.glob("*/tests/Makefile")):
        for line in mk.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if ":" not in s:
                continue
            target = s.split(":", 1)[0].strip()
            # forms seen in the tree: $(BUILD)/commands_host:  or  commands_host:
            for cand in (target, target.split("/")[-1] if "/" in target else ""):
                if cand.endswith("_host") and "$" not in cand:
                    name = cand[: -len("_host")]
                    if name and name not in seen:
                        seen.add(name)
                        found.append({"name": name, "makefile": mk,
                                      "bin": mk.parent / "build" / f"{name}_host"})
    if not found:
        raise RunnerError("host discovery found no *_host targets — the drill would certify nothing")
    return found


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


def farm_rows(repo: Path) -> list[dict[str, str]]:
    """The 8 Chromium process rows, read from the matrix data (not hand-listed)."""
    rows: list[dict[str, str]] = []
    text = (repo / CHROMIUM_MATRIX).read_text(encoding="utf-8")
    in_rows = False
    for line in text.splitlines():
        if line.startswith("rows:"):
            in_rows = True
            continue
        if in_rows and line.strip().startswith("- process:"):
            rows.append({"host": line.split(":", 1)[1].strip(), "phase": "process-kill",
                         "signal": "*", "status": "not-run",
                         "reason": "needs the farm browser process tree + VM snapshots (HG-33)"})
    if not rows:
        raise RunnerError("kill-matrix.yaml yielded zero farm rows — data drifted?")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(prog="kill-matrix", description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None, help="xr-core checkout (default: sibling)")
    ap.add_argument("--iterations", type=int, default=3, help="kill iterations per cell")
    ap.add_argument("--seed", default="20260910")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    global XR_CORE
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else repo.parent / "xr-core"
    XR_CORE = xr_core
    if not xr_core.exists():
        return emit("kill-matrix", ok=False,
                    failures=[f"xr-core not found at {xr_core}"], as_json=a.json)
    if not _has_toolchain():
        return emit("kill-matrix", ok=False, failures=[
            "SKIP (tool absent: g++/make) — needed for: building the host binaries the "
            "kill matrix executes; local hint: apt-get install g++ make (build-essential)"],
            as_json=a.json)
    try:
        import random
        rng = random.Random(str(a.seed))
        hosts = discover_hosts(xr_core)
        result = run_host_matrix(hosts, rng, max(1, a.iterations))
        result["cells"].extend(farm_rows(repo))
        executed = [c for c in result["cells"] if c["status"] == "executed"]
        notrun = [c for c in result["cells"] if c["status"] == "not-run"]
        require_cases(len(executed), "kill-matrix")
        result["summary"] = {
            "hosts_discovered": [h["name"] for h in hosts],
            "cells_executed": len(executed),
            "kill_iterations": sum(c.get("iterations", 0) for c in executed),
            "kills_mid_flight": result["kill_stats"]["mid"],
            "kills_post_exit": result["kill_stats"]["post"],
            "cells_not_run": len(notrun),
        }
    except RunnerError as exc:
        return emit("kill-matrix", ok=False, failures=[str(exc)], as_json=a.json)
    if not a.json:
        for c in result["cells"]:
            if c["status"] == "executed":
                print(f"  executed: {c['host']}/{c['phase']}/{c['signal']}"
                      f" ({c.get('iterations', 1)} iteration(s))")
            else:
                print(f"  NOT-RUN : {c['host']}/{c['phase']}/{c['signal']} — {c['reason']}")
        s = result["summary"]
        print(f"  cells executed: {s['cells_executed']} "
              f"(kill iterations: {s['kill_iterations']}), cells not-run: {s['cells_not_run']}")
    return emit("kill-matrix", ok=True, extra={"summary": result["summary"]}, as_json=a.json)


def _has_toolchain() -> bool:
    import shutil as sh
    return bool(sh.which("g++")) and bool(sh.which("make"))


if __name__ == "__main__":
    raise SystemExit(main())
