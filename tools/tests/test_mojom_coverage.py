"""tools/tests/test_mojom_coverage.py — P12-T2: every xr.mojom interface must
be reachable by the fuzz generator (contract-driven coverage law).

Root-cause class this closes (P10-T0-a / P11-T0-a): a contract surface that
is never fed to the fuzzer is invisible-by-omission — the gate printed "0
failures" because nobody counted the new surface at all. P12-T2 adds
`xr-core/mojom/cosmetic.mojom` as the 9th interface, and this test makes it
structurally impossible for ANY interface (present or future) to be absent
from tools/mojom_fuzz_gen.py's inputs:

  * discover every `interface X {` declared under ../xr-core/mojom/;
  * run the generator and parse its `covers:` count line (names + counts);
  * assert the discovered interface-set is a SUBSET of the covered set — a
    new interface with no generator seed source FAILS here, naming it.

The generator's own zero-case law (a covered host with no committed seeds
raises, exit 1) proves the reverse direction: a listed-but-unseeded host
cannot pass. The negative path below proves THIS test can fire (a covers
line with an interface removed must be flagged), so a silent-pass is not a
failure mode of the harness.

Stdlib only (pytest is in the dev set). No wall-clock, no network.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
XRCORE = REPO.parent / "xr-core"

INTF_RE = re.compile(r"^interface\s+([A-Za-z_][A-Za-z0-9_]*)")


def _run_gen(*args: str) -> dict:
    r = subprocess.run(
        [sys.executable, str(TOOLS / "mojom_fuzz_gen.py"),
         "--repo", str(REPO), *args],
        capture_output=True, text=True)
    return {"rc": r.returncode, "out": r.stdout, "err": r.stderr}


def discover_mojom_interfaces() -> dict[str, str]:
    """interface name -> file it was declared in, over ../xr-core/mojom/."""
    if not (XRCORE / "mojom").is_dir():
        pytest.skip("no ../xr-core/mojom sibling checkout")
    found: dict[str, str] = {}
    for f in sorted((XRCORE / "mojom").glob("*.mojom")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = INTF_RE.match(line.strip())
            if m:
                found[m.group(1)] = f.name
    return found


def parse_covers(covers: str) -> dict[str, str]:
    """covers: 'Name:host:count Name:host:count ...' -> {interface: host}."""
    out: dict[str, str] = {}
    for tok in covers.split():
        name, host, count = tok.split(":")
        assert int(count) > 0, f"{tok}: zero cases (empty-run law)"
        out[name] = host
    return out


def missing_from_covers(interfaces: dict[str, str],
                        covered: dict[str, str]) -> list[str]:
    return [name for name in interfaces if name not in covered]


# --- positive: every discovered interface is covered -----------------------

def test_every_mojom_interface_is_covered() -> None:
    interfaces = discover_mojom_interfaces()
    assert interfaces, "no interfaces discovered under ../xr-core/mojom (zero-case law)"
    r = _run_gen("--count", "25", "--seed", "20260919", "--json")
    assert r["rc"] == 0, r["err"]
    doc = json.loads(r["out"][r["out"].index("{"):])
    covered = parse_covers(doc["covers"])
    missing = missing_from_covers(interfaces, covered)
    # The count line must NAMES each covered host (a host with no name is a
    # host the test cannot verify — that is itself the failure this exists for).
    assert doc["per_host"] and all(v == 25 for v in doc["per_host"].values()), \
        "a covered host ran fewer cases than --count (short-run law)"
    assert not missing, (
        "interface(s) absent from the fuzz generator's inputs: "
        f"{missing} — add a seed source in tools/mojom_fuzz_gen.py "
        "(COVERED_HOSTS / CORPORA / SEED_FILES) so no contract surface is "
        "invisible to the fuzzer")


def test_cosmetic_interface_is_covered() -> None:
    # The P12-T2 deliverable, pinned explicitly: cosmetic.mojom must be in
    # the generator, mapped to its stdio host renderer/cosmetic, with the
    # committed parity corpus as seeds.
    interfaces = discover_mojom_interfaces()
    assert interfaces.get("Cosmetic") == "cosmetic.mojom", \
        "cosmetic.mojom must declare interface Cosmetic"
    r = _run_gen("--count", "11", "--seed", "7", "--json")
    doc = json.loads(r["out"][r["out"].index("{"):])
    covered = parse_covers(doc["covers"])
    assert covered.get("Cosmetic") == "renderer/cosmetic", \
        "Cosmetic must map to the renderer/cosmetic stdio host"
    assert doc["per_host"]["renderer/cosmetic"] == 11


# --- negative: this test can fire (never a silent pass) --------------------

def test_missing_interface_is_flagged() -> None:
    interfaces = discover_mojom_interfaces()
    if not interfaces:
        pytest.skip("no xr-core interfaces to prove the negative against")
    covered = parse_covers(" ".join(
        f"{name}:{name}:10" for name in interfaces))
    victim = sorted(interfaces)[0]
    del covered[victim]
    missing = missing_from_covers(interfaces, covered)
    assert victim in missing, "the coverage check failed to flag a dropped interface"
