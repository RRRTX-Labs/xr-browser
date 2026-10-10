"""tools/identity_iso_cells.py — the P14 identity-core isolation cells.

Split out of tools/isolation_matrix.py by the touched-file size law (the
P13 precedent: split by responsibility, never compress comments). These
cells drive the xr-core identity HOST + session-chaos SUITE rather than the
P6 resolver fake:

  * disposable-zero-residue (T6): a clean close verifies zero bytes AND the
    planted cookie jar (the §1.4 negative) FAILS the destroy;
  * identity-derivation-probe (security req 2): the brute-force corpus —
    try to derive an identity from a partition name / URL / title / log
    line / a real vid; every attempt must fail to embed the source and
    produce the opaque shape;
  * session-restore-no-bleed (T8, census C-14): the seeded chaos suite is
    the assertion (restore re-binds to the recorded identity, never
    another, never the default; disposables never restored).

g++/make absent => the cells record a VISIBLE skip with the reason (the
resolver cells keep the run non-empty; the empty-run law is about a runner
that quietly ran nothing, not a toolchain that honestly said skip).

Stdlib only. No wall clock in any verdict.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import RunnerError  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "spike"))
import fsdiff  # noqa: E402  (P4-T5's real FS-diff; T6 wires it into this cell)

# ---------------------------------------------------------------------------
# P14 identity-core cells (the identity host + suite; security req 2, T6, T8)
# ---------------------------------------------------------------------------

IDENTITY_MECHS = ("disposable-zero-residue", "identity-derivation-probe",
                  "session-restore-no-bleed")
DOMAIN_SHAPE = re.compile(
    r"^xr:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _identity_bin(xr_core: Path) -> tuple[Path | None, str]:
    """Build the identity lane; (host path, reason). None + reason on no
    toolchain.

    The build is OUT-OF-TREE (BUILD override into this repo's work/scratch):
    building in-place would leave identity/tests/build/ in the sibling, and
    every pin-faithful gate would then rightly call the sibling DIRTY — the
    files it reads must be the pinned files, build residue included.
    """
    if shutil.which("g++") is None or shutil.which("make") is None:
        return None, "g++/make absent — identity cells skipped (skip-policy)"
    tests = xr_core / "identity" / "tests"
    build = (Path(__file__).resolve().parents[1] / "work" / "scratch"
             / "iso-identity-build")
    r = subprocess.run(["make", "-C", str(tests), "build",
                        f"BUILD={build}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RunnerError(f"identity make failed: {r.stderr[-300:]}")
    return build / "identity_host", ""


def _host_json(host: Path, sub: str, args: dict[str, Any]) -> dict[str, Any]:
    p = subprocess.run([str(host), sub, json.dumps(args, sort_keys=True)],
                       capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout)


def _scenario(host: Path, ops: list[dict[str, Any]],
              cwd: Path | None = None) -> dict[str, Any]:
    p = subprocess.run([str(host), "scenario",
                        json.dumps({"ops": ops}, sort_keys=True)],
                       capture_output=True, text=True, timeout=60,
                       cwd=str(cwd) if cwd else None)
    return json.loads(p.stdout)


def _fs_cycle(host: Path, ops: list[dict[str, Any]]
              ) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Run one scenario with a FRESH scratch dir as the host's cwd and return
    (scenario result, fsdiff of that dir before/after). The diff is measured
    (sha256 per path, build/spike/fsdiff.py), never assumed."""
    with tempfile.TemporaryDirectory(prefix="xr-t6-fsdiff.") as td:
        root = Path(td)
        before = fsdiff.snapshot(root)
        res = _scenario(host, ops, cwd=root)
        return res, fsdiff.diff(before, fsdiff.snapshot(root))


def run_identity_cells(xr_core: Path, matrix: dict[str, Any]
                       ) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    idents = {i["id"]: i for i in matrix["identities"]}
    mechs = [m for m in matrix["mechanisms"] if m["id"] in IDENTITY_MECHS]
    if not mechs:
        return cells
    host, reason = _identity_bin(xr_core)
    for mech in mechs:
        for a, b in matrix["identity_pairs"]:
            if host is None:
                cells.append({"mechanism": mech["id"], "pair": [a, b],
                              "mode": "skip", "verdict": "SKIP",
                              "detail": reason})
                continue
            if mech["id"] == "disposable-zero-residue":
                # T6: clean close verifies zero bytes AND the planted cookie
                # jar (the §1.4 negative) FAILS the destroy.
                # domain discovery: provision first, then destroy by name
                prov = _scenario(host, [
                    {"op": "provision", "entropy": f"iso-{a}-{b}-clean",
                     "in_memory": True}])
                dom = prov["steps"][0]["record"]["domain"]
                # T6 FS-diff: each cycle runs with a fresh scratch dir as
                # the host cwd; the clean close must leave ZERO paths, and the
                # planted leftover (plant-fs-leftover) MUST show up.
                clean, fs_clean = _fs_cycle(host, [
                    {"op": "provision", "entropy": f"iso-{a}-{b}-clean",
                     "in_memory": True},
                    {"op": "destroy", "domain": dom}])
                prov2 = _scenario(host, [
                    {"op": "provision", "entropy": f"iso-{a}-{b}-dirty",
                     "in_memory": True}])
                dom2 = prov2["steps"][0]["record"]["domain"]
                dirty, fs_dirty = _fs_cycle(host, [
                    {"op": "provision", "entropy": f"iso-{a}-{b}-dirty",
                     "in_memory": True},
                    {"op": "plant-residual", "domain": dom2,
                     "kind": "cookies", "bytes": 512},
                    {"op": "destroy", "domain": dom2},
                    {"op": "plant-fs-leftover", "path": "leftover.bin",
                     "bytes": 64}])
                okfs = (fsdiff.is_empty(fs_clean) and
                        fs_dirty["added"] == ["leftover.bin"])
                okc = (clean["steps"][1]["ok"] is True and
                       clean["steps"][1]["zero_residual_verified"] is True)
                okd = (dirty["steps"][2]["ok"] is False and
                       "residual" in dirty["steps"][2]["error"])
                cells.append({
                    "mechanism": "disposable-zero-residue", "pair": [a, b],
                    "mode": "fake",
                    "verdict": "PASS" if okc and okd and okfs else "FAIL",
                    "detail": (f"clean close verified={okc}; planted cookie "
                               f"jar fails destroy={okd}; fs-diff clean close "
                               f"0 paths + planted leftover caught={okfs}")})
            elif mech["id"] == "identity-derivation-probe":
                # Security req 2: the brute-force probe corpus — try to
                # derive an identity from a partition name / URL / title /
                # log line; every attempt must fail to embed the source.
                probes = [f"partition:{a}", f"https://{a}.example/x",
                          f"{a} — tab title", f"log-line identity={a}",
                          idents[a]["vid"], f"{b}-identity"]
                ok = True
                for i, probe in enumerate(probes):
                    rec = _host_json(host, "provision",
                                     {"entropy": probe,
                                      "display_name": probe[:20]})
                    dom = rec.get("domain", "")
                    shape_ok = bool(DOMAIN_SHAPE.match(dom))
                    embed_ok = probe.lower() not in dom.lower()
                    if not (shape_ok and embed_ok):
                        ok = False
                cells.append({
                    "mechanism": "identity-derivation-probe",
                    "pair": [a, b], "mode": "fake",
                    "verdict": "PASS" if ok else "FAIL",
                    "detail": (f"{len(probes)} derivation probes "
                               f"(name/URL/title/log/vid): no embed, "
                               "opaque shape")})
            else:  # session-restore-no-bleed (C-14, T8)
                # The suite is the assertion: the seeded chaos test proves
                # restore-never-bleeds + disposables-never-restored.
                binp = host.parent / "test_session_chaos"
                r = subprocess.run([str(binp)], capture_output=True,
                                   text=True, timeout=120)
                line = (r.stdout.strip().splitlines() or [""])[-1]
                cells.append({
                    "mechanism": "session-restore-no-bleed",
                    "pair": [a, b], "mode": "fake",
                    "verdict": "PASS" if r.returncode == 0 else "FAIL",
                    "detail": f"identity/session+chaos: {line}"})
    return cells


