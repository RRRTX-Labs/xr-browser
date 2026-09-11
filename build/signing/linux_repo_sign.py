#!/usr/bin/env python3
"""build/signing/linux_repo_sign.py — the REAL Linux repo-signing lane
(P10-T4; gpg is present in the dev sandbox and this lane exercises it for
real, with a throwaway GNUPGHOME — using gpg, not inventing crypto).

Covers the two repo-metadata shapes:
  * apt:    `Release` clearsigned → `InRelease` (+ detached `Release.gpg`)
  * rpm:    `repomd.xml` detached signature → `repomd.xml.asc`
             (the `rpmsign`/`--add-sign` convention's exact bytes)

Subcommands:
  keygen   --gnupghome DIR            throwaway signing key (TEST ONLY —
                                      a release key is born in an HSM at
                                      the HG-36 ceremony, never here)
  sign     --in FILE [--out FILE]     clearsign (apt) or detach-sign (.asc)
  verify   --in FILE [--sig FILE]     verify against the keyring in HOME
Exit: 0 pass · 1 fail · 77 gpg absent (SKIP-visible) · 2 usage.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def gpg_present() -> bool:
    try:
        subprocess.run(["gpg", "--version"], capture_output=True, timeout=20)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def gpg_env(home: Path) -> dict:
    env = dict(os.environ)
    env["GNUPGHOME"] = str(home)
    return env


def run_gpg(home: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["gpg", "--homedir", str(home), "--batch",
                        "--yes", *args], capture_output=True, text=True,
                       env=gpg_env(home), timeout=120)
    if check and r.returncode != 0:
        raise SystemExit(f"FAIL: gpg {' '.join(args[:2])}: "
                         f"{(r.stderr or r.stdout).strip()[:300]}")
    return r


def cmd_keygen(a: argparse.Namespace) -> int:
    home = Path(a.gnupghome)
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    # ed25519 via gpg's own primitives (no crypto invented here)
    r = run_gpg(home, "--pinentry-mode", "loopback", "--passphrase", "",
                "--quick-gen-key", "XR Test Repo Signer "
                "<test@rrrtx.labs>", "default", "sign", "0",
                check=False)
    if r.returncode != 0:
        print(f"FAIL: keygen: {(r.stderr or r.stdout).strip()[:300]}")
        return 1
    r = run_gpg(home, "--armor", "--export", "test@rrrtx.labs",
                check=False)
    (home / "signing-pub.asc").write_text(r.stdout, encoding="utf-8")
    print(f"PASS: linux-repo test key generated in {home} "
          "(TEST ONLY — release keys are HSM-born, HG-36)")
    return 0


def cmd_sign(a: argparse.Namespace) -> int:
    home = Path(a.gnupghome)
    src = Path(a.infile)
    if not src.exists():
        print(f"FAIL: {src} not found")
        return 1
    if a.mode == "clearsign":  # apt InRelease convention
        out = Path(a.out) if a.out else src.with_name("InRelease")
        run_gpg(home, "--clearsign", "--local-user", "test@rrrtx.labs",
                "--output", str(out), str(src))
        print(f"PASS: clearsigned {src.name} -> {out.name}")
        return 0
    # detach-sign (Release.gpg / repomd.xml.asc convention)
    suffix = a.suffix if a.suffix else ".asc"
    out = Path(a.out) if a.out else src.with_name(src.name + suffix)
    run_gpg(home, "--detach-sign", "--armor", "--local-user",
            "test@rrrtx.labs", "--output", str(out), str(src))
    print(f"PASS: detached signature {src.name} -> {out.name}")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    home = Path(a.gnupghome)
    src = Path(a.infile)
    args = ["--verify"]
    if a.sig:
        args += [str(Path(a.sig))]
    args.append(str(src))
    r = run_gpg(home, *args, check=False)
    if r.returncode != 0:
        print(f"FAIL: verification FAILED ({src.name}): "
              f"{(r.stderr or r.stdout).strip()[:300]}")
        return 1
    print(f"PASS: signature verified ({src.name} against keyring {home})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="linux-repo-sign",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("keygen", "throwaway TEST key"),
                           ("sign", "clear/detach sign"),
                           ("verify", "verify")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--gnupghome", required=True)
        if name != "keygen":
            p.add_argument("--in", dest="infile", required=True)
        if name == "sign":
            p.add_argument("--mode", choices=["clearsign", "detach"],
                           default="clearsign")
            p.add_argument("--out", default=None)
            p.add_argument("--suffix", default=".asc",
                           help="detach suffix (e.g. .gpg for Release)")
        if name == "verify":
            p.add_argument("--sig", default=None,
                           help="detached sig (omit for clearsigned)")
        p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not gpg_present():
        print("SKIP: SKIP (tool absent: gpg) — needed for: the REAL Linux "
              "repo-signing lane (sign/verify/tamper/wrong-key); local "
              "hint: apt-get install gnupg")
        return 77
    return {"keygen": cmd_keygen, "sign": cmd_sign,
            "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
