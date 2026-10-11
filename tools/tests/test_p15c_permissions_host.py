"""P15-CLOSE C2 — the clock-owning permissions host, its protocol and its fake.

1. tools/permission_host_parity.py: every corpus + fixture case and a store-dir
   sequence (with a rolled-back clock) are byte-identical host vs fake.
2. host_protocol_check / parity_completeness count the permissions host.
3. The clock-free row: the real core is clean, a planted clock read in
   permissions/core reddens, and a clock read in permissions/host does not.
4. The kill matrix registers a drill surface for the permissions host, and the
   suite Makefile builds the real kill -9 test against the built host.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
XR_CORE = REPO.parent / "xr-core"
HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None


def _py(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          cwd=str(REPO), timeout=600)


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent — C++ host skipped (skip-policy)")
def test_host_fake_byte_parity() -> None:
    r = _py(str(TOOLS / "permission_host_parity.py"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS: permission-host-parity" in r.stdout
    assert "DIVERGE" not in r.stdout


def test_protocol_and_completeness_count_permissions() -> None:
    r = _py(str(TOOLS / "host_protocol_check.py"))
    assert r.returncode == 0, r.stdout
    assert "discovered host: permissions (8 method(s)" in r.stdout
    r = _py(str(TOOLS / "parity_completeness.py"), "--repo", str(REPO))
    assert r.returncode == 0, r.stdout
    assert "permissions: methods covered by parity corpus" in r.stdout


def test_core_is_clock_free_and_host_owns_the_clock() -> None:
    r = _py(str(TOOLS / "permission_write_path_check.py"))
    assert r.returncode == 0, r.stdout
    assert "permissions/core/ clock-free" in r.stdout
    host = (XR_CORE / "permissions" / "host" / "permissions_host.cc").read_text("utf-8")
    assert "system_clock::now()" in host and "EffectiveNow(" in host


def test_planted_core_clock_reddens(tmp_path: Path) -> None:
    core = tmp_path / "xr-core" / "permissions" / "core"
    host = tmp_path / "xr-core" / "permissions" / "host"
    core.mkdir(parents=True)
    host.mkdir(parents=True)
    (core / "ops.cc").write_text("// owner\n", "utf-8")
    (host / "permissions_host.cc").write_text(
        "#include <chrono>\nauto t = std::chrono::system_clock::now();\n", "utf-8")
    r = _py(str(TOOLS / "permission_write_path_check.py"), "--root", str(tmp_path))
    assert r.returncode == 0, "a clock read in the HOST is legal: " + r.stdout
    (core / "sweep.cc").write_text("long n() { return time(nullptr); }\n", "utf-8")
    r = _py(str(TOOLS / "permission_write_path_check.py"), "--root", str(tmp_path))
    assert r.returncode == 1, r.stdout
    assert "permissions/core/sweep.cc:1 clock read inside core" in r.stdout


def test_kill_drill_wiring() -> None:
    sys.path.insert(0, str(REPO / "build" / "qa" / "drill"))
    try:
        import host_drills  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    spec = host_drills.HOST_DRILLS["permissions"]
    assert spec["state"] == ["permissions-store.json", "permissions-clock.json"]
    assert spec["write"][0] == "grant" and spec["read"] == ["view"]
    mk = (XR_CORE / "permissions" / "tests" / "Makefile").read_text("utf-8")
    assert "test_kill9" in mk and "$(BUILD)/permissions_host:" in mk
    kill9 = (XR_CORE / "permissions" / "tests" / "test_kill9.cc").read_text("utf-8")
    assert "SIGKILL" in kill9 and "fork()" in kill9 and "XR_PERMISSIONS_HOST_PATH" in kill9
