from pathlib import Path

from preflight import check_disk, probe


def test_probe_shape():
    info = probe()
    assert "nproc" in info and "disk" in info
    assert info["disk"]["free_gb"] >= 0


def test_check_disk_refuses_huge_estimate():
    ok, msg = check_disk(Path("/tmp"), estimate_gb=1_000_000)
    assert not ok
    assert "REFUSED" in msg


def test_check_disk_accepts_tiny_estimate():
    ok, msg = check_disk(Path("/tmp"), estimate_gb=0.0001)
    assert ok
