#!/usr/bin/env python3
"""build/signing/tests/argv_stub_test.py — the macOS/Windows arg-construction
tests (P10-T4): platform_argv.py must construct the EXACT argv we will run
on the signing hosts, and a stub-binary recorder must observe exactly that
argv. Real execution + real certs = HG-37; here we pin the CONTRACT.

Also pins the release-channel-without-provider refusal (fail-closed).
Stdlib only. Exit: 0 pass · 1 fail.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARGV_TOOL = HERE.parent / "platform_argv.py"


def make_stub_dir(tmp: Path) -> Path:
    bindir = tmp / "stubbin"
    bindir.mkdir()
    stub = tmp / "record_argv.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "with open(os.environ['RECORDED_ARGV'], 'a') as fh:\n"
        "    fh.write(os.path.basename(sys.argv[0]) + '\\0')\n"
        "    for a in sys.argv[1:]:\n"
        "        fh.write(a + '\\0')\n"
        "    fh.write('\\x00\\n')\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    for name in ("codesign", "xcrun", "signtool", "osslsigncode"):
        (bindir / name).symlink_to(stub)
    return bindir


def observed(bindir: Path, env: dict, spec_cmd: str) -> list[list[str]]:
    env = dict(env)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    subprocess.run(spec_cmd, shell=True, env=env, check=True,
                   capture_output=True, timeout=60)
    raw = Path(env["RECORDED_ARGV"]).read_text()
    return [[a for a in blk.split("\0") if a]
            for blk in raw.split("\0\n") if blk.strip("\0")]


def main() -> int:
    cases = [
        ("mac-codesign", ["--app", "XR.app"],
         ["codesign", "--force", "--options", "runtime", "--timestamp",
          "--entitlements", "build/signing/xr.entitlements", "--sign",
          "Developer ID Application: RRRTX Labs (TEAMID)", "XR.app"]),
        ("mac-notary", [],
         ["xcrun", "notarytool", "submit", "XR.zip", "--keychain-profile",
          "xr-notary", "--wait"]),
        ("mac-staple", [],
         ["xcrun", "stapler", "staple", "XR.app"]),
        ("win-sign", [],
         ["signtool", "sign", "/fd", "SHA256", "/tr",
          "http://timestamp.digicert.com", "/td", "SHA256", "/sha1",
          "0" * 40, "/f", "build/signing/xr-release-cert.pem",
          "XR-Setup.exe"]),
        ("win-verify", [],
         ["osslsigncode", "verify", "XR-Setup.exe"]),
    ]
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        stubbin = make_stub_dir(tmp)
        env = dict(os.environ)
        env["RECORDED_ARGV"] = str(tmp / "argv.log")
        Path(env["RECORDED_ARGV"]).write_text("")
        for which, extra, want in cases:
            spec = subprocess.run(
                [sys.executable, str(ARGV_TOOL), "--print", which, *extra],
                capture_output=True, text=True, check=True).stdout.strip()
            try:
                got = observed(stubbin, env, spec)
            except subprocess.CalledProcessError as exc:
                print(f"FAIL: {which}: stub run failed: {exc}")
                fails += 1
                continue
            if want in got:
                print(f"ok: argv exact ({which}): {' '.join(want)[:70]}")
            else:
                print(f"FAIL: {which}: observed {got} != want {want}")
                fails += 1
        # provider guard: release channel WITHOUT provider refused
        r = subprocess.run([sys.executable, str(ARGV_TOOL), "--print",
                            "guard", "--channel", "beta"],
                           capture_output=True, text=True)
        if r.returncode != 0 and "XR_SIGN_PROVIDER" in r.stdout:
            print("ok: beta without XR_SIGN_PROVIDER refused (fail-closed)")
        else:
            print("FAIL: beta without provider was NOT refused")
            fails += 1
        r = subprocess.run([sys.executable, str(ARGV_TOOL), "--print",
                            "guard", "--channel", "stable",
                            "--provider", "hsm://signhost"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("ok: stable with provider accepted (argv construction "
                  "only; real signatures = HG-37)")
        else:
            print("FAIL: stable with provider refused")
            fails += 1
    if fails:
        print(f"FAIL: platform argv tests ({fails})")
        return 1
    print("PASS: platform argv (5 exact argv shapes observed through the "
          "stub recorder; release-channel guard fail-closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
