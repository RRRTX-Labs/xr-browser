import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIGN = HERE.parent / "sign_artifact.py"


def test_release_channel_refused(tmp_path):
    artifact = tmp_path / "x.bin"
    artifact.write_bytes(b"\x00" * 16)
    r = subprocess.run([sys.executable, str(SIGN), "--artifact", str(artifact),
                        "--channel", "stable", "--os", "linux", "--key", "/tmp/k"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "refused" in r.stderr
    assert "P10" in r.stderr


def test_dev_channel_accepted_path(tmp_path):
    # only the channel gate is exercised here (mock env keeps it from shelling out)
    import os
    artifact = tmp_path / "x.bin"
    artifact.write_bytes(b"\x00" * 16)
    env = dict(os.environ, XR_ALLOW_MOCK="1")
    r = subprocess.run([sys.executable, str(SIGN), "--artifact", str(artifact),
                        "--channel", "dev", "--os", "linux", "--key", "/tmp/k", "--json"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0
