"""P14-CLOSE C-4 — the security row, closed as tests (fast lane: governance
runs `./scripts/build test`, which runs this file on every push).

1. Cross-identity process assertion + a PLANTED red: a scratch copy of the
   identity core whose IdentityStore::Insert accepts a duplicate partition
   domain ("share a partition across identities") MUST redden
   identity/tests/test_derivation.cc. The assertion cites the seam's partition
   code (spike/identity_seam/xr_identity.h:36) and the core's prefix; the two
   are pinned together here so they cannot drift.
2. Policy row CONSULTED on the path (the ABPF lesson: present-but-inert is not
   enforcement): stubbing the resolver consult (vault_scope absent, or a
   disposable granted autofill) MUST turn the vault-scope cells FAIL.
3. Purge FS-diff (T6): the disposable-zero-residue cell measures a real
   fsdiff around each cycle; neutering the diff MUST turn the cell FAIL.

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
XR_CORE = REPO.parent / "xr-core"
sys.path.insert(0, str(TOOLS))
# isolation_matrix imports build/qa/_common (RunnerError, …); tools/ has its
# own _common. Import under build/qa's, then restore whatever the session had,
# so this module neither breaks nor is broken by its neighbours.
_saved = sys.modules.pop("_common", None)
sys.path.insert(0, str(REPO / "build" / "qa"))
try:
    import isolation_matrix  # noqa: E402
    import identity_iso_cells  # noqa: E402
finally:
    sys.path.remove(str(REPO / "build" / "qa"))
    if _saved is not None:
        sys.modules["_common"] = _saved
    else:
        sys.modules.pop("_common", None)

HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None
MATRIX = yaml.safe_load((XR_CORE / "test" / "isolation" / "matrix.yaml")
                        .read_text(encoding="utf-8"))
SEAM = XR_CORE / "spike" / "identity_seam" / "xr_identity.h"
MINT_H = XR_CORE / "identity" / "core" / "mint.h"
DERIVATION = XR_CORE / "identity" / "tests" / "test_derivation.cc"
SHARE_GUARD = "  if (records_.count(rec.domain)) {\n"


def _only(mech: str) -> dict:
    m = dict(MATRIX)
    m["mechanisms"] = [x for x in MATRIX["mechanisms"] if x["id"] == mech]
    assert m["mechanisms"], f"matrix lost the {mech} mechanism"
    return m


# -- 1. cross-identity process assertion ------------------------------------

def test_partition_citation_cannot_drift() -> None:
    seam = SEAM.read_text(encoding="utf-8").splitlines()
    assert "cross-identity correlation primitive" in seam[35], \
        "spike/identity_seam/xr_identity.h:36 moved — re-cite it in test_derivation.cc"
    seam_prefix = re.search(r'kPartitionDomainPrefix\[\] = "([^"]+)"', "\n".join(seam))
    core_prefix = re.search(r'kDomainPrefix = "([^"]+)"', MINT_H.read_text(encoding="utf-8"))
    assert seam_prefix and core_prefix
    assert seam_prefix.group(1) == core_prefix.group(1), \
        "seam partition prefix and core mint prefix drifted"
    src = DERIVATION.read_text(encoding="utf-8")
    assert "spike/identity_seam/xr_identity.h:36" in src
    assert "TestCrossIdentityNeverSharesAPartition();" in src


def test_planted_partition_share_reddens(tmp_path: Path) -> None:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — planted partition-share red skipped (skip-policy)")
    scratch = tmp_path / "xr-core"
    ignore = shutil.ignore_patterns("build", "__pycache__")
    for sub in ("identity", "common"):
        shutil.copytree(XR_CORE / sub, scratch / sub, ignore=ignore)
    core = scratch / "identity" / "core" / "identity.cc"
    text = core.read_text(encoding="utf-8")
    assert SHARE_GUARD in text, "plant anchor moved: IdentityStore::Insert duplicate guard"
    core.write_text(text.replace(SHARE_GUARD, "  if (false) {  // PLANTED SHARE\n"),
                    encoding="utf-8")
    build = tmp_path / "build"
    r = subprocess.run(["make", "-C", str(scratch / "identity" / "tests"),
                        f"BUILD={build}", str(build / "test_derivation")],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-400:]
    run = subprocess.run([str(build / "test_derivation")], capture_output=True,
                         text=True, timeout=120)
    assert run.returncode != 0, "the planted partition share did NOT redden test_derivation"
    assert "share one partition" in run.stdout + run.stderr


# -- 2. the no-vault-access row is CONSULTED ----------------------------------

def test_vault_consult_real_resolver_passes() -> None:
    mod = isolation_matrix.load_resolver(XR_CORE)
    cells = isolation_matrix.run_fake_cells(mod, _only("vault-scope"))
    assert cells and all(c["verdict"] == "PASS" for c in cells), cells


def test_vault_consult_stubbed_absent_fails(monkeypatch) -> None:
    mod = isolation_matrix.load_resolver(XR_CORE)
    real = isolation_matrix.resolve

    def stub(m, vid, trust):  # the consult "happens" but returns nothing
        p = dict(real(m, vid, trust))
        p.pop("vault_scope", None)
        return p
    monkeypatch.setattr(isolation_matrix, "resolve", stub)
    cells = isolation_matrix.run_fake_cells(mod, _only("vault-scope"))
    assert cells and all(c["verdict"] == "FAIL" for c in cells)
    assert "not consulted" in cells[0]["detail"]


def test_vault_consult_stubbed_grant_fails_for_disposable(monkeypatch) -> None:
    mod = isolation_matrix.load_resolver(XR_CORE)
    real = isolation_matrix.resolve

    def stub(m, vid, trust):  # a consult that grants vault access
        p = dict(real(m, vid, trust))
        p["vault_scope"] = {"autofill_allowed": True, "export_allowed": False}
        return p
    monkeypatch.setattr(isolation_matrix, "resolve", stub)
    cells = isolation_matrix.run_fake_cells(mod, _only("vault-scope"))
    eph = [c for c in cells if "ephemeral" in c["pair"]]
    assert eph and all(c["verdict"] == "FAIL" for c in eph), \
        "a disposable granted autofill did not redden — the row is inert"


# -- 3. purge FS-diff (T6) ----------------------------------------------------

def test_fs_diff_cell_passes_and_is_consulted(monkeypatch) -> None:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — identity host cells skipped (skip-policy)")
    mx = _only("disposable-zero-residue")
    cells = identity_iso_cells.run_identity_cells(XR_CORE, mx)
    assert cells and all(c["verdict"] == "PASS" for c in cells), cells
    assert all("planted leftover caught=True" in c["detail"] for c in cells)
    # Neuter the measurement: a diff that sees nothing must turn the cell red
    # (the planted leftover goes uncaught), never pass quietly.
    monkeypatch.setattr(identity_iso_cells.fsdiff, "diff",
                        lambda before, after: {"added": [], "removed": [], "changed": []})
    red = identity_iso_cells.run_identity_cells(XR_CORE, mx)
    assert red and all(c["verdict"] == "FAIL" for c in red)
