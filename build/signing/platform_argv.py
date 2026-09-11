#!/usr/bin/env python3
"""build/signing/platform_argv.py — the EXACT argv the signing hosts will
run for macOS/Windows (P10-T4). Pure argv CONSTRUCTION (no crypto, no
subprocess): the arg-construction tests pin these strings, the stub-binary
harness (build/signing/tests/test_platform_argv.sh) replays them against
a recorder so "what we will run on the signing host" is a tested fact,
not a docstring claim. Real execution + real certs = HG-37.

Also the XR_SIGN_PROVIDER guard: a RELEASE channel without a real
provider configured is a refusal (fail-closed), never a dry-run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RELEASE_CHANNELS = ("beta", "stable")


def mac_codesign_argv(app: str, identity: str,
                      entitlements: str) -> list[str]:
    return [
        "codesign", "--force", "--options", "runtime",
        "--timestamp", "--entitlements", entitlements,
        "--sign", identity, app,
    ]


def mac_notarytool_argv(zipfile: str, keychain_profile: str) -> list[str]:
    return ["xcrun", "notarytool", "submit", zipfile,
            "--keychain-profile", keychain_profile, "--wait"]


def mac_stapler_argv(app: str) -> list[str]:
    return ["xcrun", "stapler", "staple", app]


def mac_verify_argv(app: str) -> list[str]:
    return ["codesign", "--verify", "--deep", "--strict",
            "--verbose=2", app]


def win_signtool_argv(file: str, cert_sha1: str, pem: str) -> list[str]:
    return [
        "signtool", "sign", "/fd", "SHA256", "/tr",
        "http://timestamp.digicert.com", "/td", "SHA256",
        "/sha1", cert_sha1, "/f", pem, file,
    ]


def win_verify_argv(file: str) -> list[str]:
    return ["osslsigncode", "verify", file]


def guard(channel: str, provider: str | None) -> tuple[bool, str]:
    """The fail-closed release-channel guard."""
    if channel in RELEASE_CHANNELS and not provider:
        return False, (
            f"channel {channel!r} requires XR_SIGN_PROVIDER (a real "
            "signing host); refusing to construct a release signature "
            "without one — HG-37")
    if channel in RELEASE_CHANNELS:
        return True, f"provider {provider!r} accepted for {channel}"
    return True, f"channel {channel!r} needs no provider (test lane)"


def main() -> int:
    ap = argparse.ArgumentParser(prog="platform-argv",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--print", dest="which", required=True,
                    choices=["mac-codesign", "mac-notary", "mac-staple",
                             "mac-verify", "win-sign", "win-verify",
                             "guard"])
    ap.add_argument("--app", default="XR.app")
    ap.add_argument("--file", default="XR-Setup.exe")
    ap.add_argument("--zip", default="XR.zip")
    ap.add_argument("--identity", default="Developer ID Application: "
                    "RRRTX Labs (TEAMID)")
    ap.add_argument("--entitlements", default="build/signing/xr.entitlements")
    ap.add_argument("--keychain-profile", default="xr-notary")
    ap.add_argument("--cert-sha1", default="0000000000000000000000000000"
                    "000000000000")
    ap.add_argument("--pem", default="build/signing/xr-release-cert.pem")
    ap.add_argument("--channel", default="dev")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    table = {
        "mac-codesign": lambda: mac_codesign_argv(a.app, a.identity,
                                                  a.entitlements),
        "mac-notary": lambda: mac_notarytool_argv(a.zip,
                                                  a.keychain_profile),
        "mac-staple": lambda: mac_stapler_argv(a.app),
        "mac-verify": lambda: mac_verify_argv(a.app),
        "win-sign": lambda: win_signtool_argv(a.file, a.cert_sha1, a.pem),
        "win-verify": lambda: win_verify_argv(a.file),
    }
    if a.which == "guard":
        ok, reason = guard(a.channel, a.provider)
        print(("PASS: " if ok else "REFUSED: ") + reason)
        return 0 if ok else 1
    argv = table[a.which]()
    import shlex
    print(shlex.join(argv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
