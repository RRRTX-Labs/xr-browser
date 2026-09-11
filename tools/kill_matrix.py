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

P11-T0-e split: the cell ENGINE (build/probe/kill/disposable execution,
run_host_matrix) lives in tools/kill_matrix_cells.py — this file keeps
discovery, the farm rows and the CLI. The moves are verbatim.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_qa_dir = Path(__file__).resolve().parents[1] / "build" / "qa"   # <repo>/build/qa
if (_qa_dir / "_common.py").exists():
    sys.path.insert(0, str(_qa_dir))
else:  # pragma: no cover - layout drift is a setup error, not a skip
    raise SystemExit(f"kill-matrix: runner law module not found at {_qa_dir}/_common.py")

from _common import RunnerError  # noqa: E402  (emit/require_cases re-exported below)

CHROMIUM_MATRIX = Path("build/qa/drill/kill-matrix.yaml")

# the cell engine (P11-T0-e split). sys.path insert so the module also works
# when kill_matrix.py is loaded via importlib from a different cwd (canaries).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kill_matrix_cells import (  # noqa: E402
    HOST_DRILLS, SIGNALS, RunnerError, build_host, corrupt_load_cell,
    host_call, kill_cell, probe_runtime, run_host_matrix, set_xr_core,
    snapshot_dir,
)
# re-exported for the canaries (tools/tests/test_p10_kill_matrix.py) and any
# other consumer that reached through the module before the split:
from _common import emit, require_cases  # noqa: E402,F401


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
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else repo.parent / "xr-core"
    set_xr_core(xr_core)
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
