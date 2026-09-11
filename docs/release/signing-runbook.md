# docs/release/signing-runbook.md — per-OS signing, operator commands

Status: **human-gated**. Linux repo signing is REAL and testable in the
dev sandbox (`build/signing/tests/test_signing_p10.sh`, transcript
`evidence/P10/logs/t4-signing-matrix.txt`). macOS/Windows execution and
every credential below are **HG-37** (certificates, Apple Developer
account, notary, SmartScreen) and **HG-36** (HSM key ceremony). Who may
run: release-eng only, never CI with interactive credentials; CI
constructs argv and verifies, it does not hold keys.

## Linux (apt / rpm / AppImage) — REAL TODAY

```bash
# throwaway TEST keyring (never a release key — release keys are HSM-born, HG-36)
export GNUPGHOME=$(mktemp -d); chmod 700 "$GNUPGHOME"
python3 build/signing/linux_repo_sign.py keygen --gnupghome "$GNUPGHOME"

# apt: clearsign Release -> InRelease
python3 build/signing/linux_repo_sign.py sign --gnupghome "$GNUPGHOME" \
  --in dist/Release --mode clearsign
python3 build/signing/linux_repo_sign.py verify --gnupghome "$GNUPGHOME" \
  --in dist/InRelease

# rpm: detached repomd.xml.asc (the rpmsign convention's exact shape)
python3 build/signing/linux_repo_sign.py sign --gnupghome "$GNUPGHOME" \
  --in dist/repomd.xml --mode detach
python3 build/signing/linux_repo_sign.py verify --gnupghome "$GNUPGHOME" \
  --in dist/repomd.xml --sig dist/repomd.xml.asc

# AppImage update metadata (embed + verify round-trip)
python3 build/signing/appimage_meta.py write --appimage XR.AppImage \
  --channel beta --version 0.9.18.2
python3 build/signing/appimage_meta.py check --appimage XR.AppImage
```

Credential: none for TEST; production = `xr-signing-linux-repo`
(HG-36 class). The full matrix harness:
`bash build/signing/tests/test_signing_p10.sh` — sign→verify OK,
one-byte tamper→FAIL, wrong key→FAIL, missing gpg→visible SKIP (77).

## macOS — HG-37 (the argv is pinned; execution is human)

```bash
# the EXACT argv we will run (contract: build/signing/tests/argv_stub_test.py)
codesign --force --options runtime --timestamp \
  --entitlements build/signing/xr.entitlements \
  --sign 'Developer ID Application: RRRTX Labs (TEAMID)' XR.app
xcrun notarytool submit XR.zip --keychain-profile xr-notary --wait
xcrun stapler staple XR.app
codesign --verify --deep --strict --verbose=2 XR.app
```

Credential: Apple Developer ID Application cert (+ Hardened Runtime);
notary App Store Connect API key in the `xr-notary` keychain profile.
Entitlements: the minimum for a multi-process browser (JIT in the
renderer, network in the browser process); reviewed per release.

## Windows — HG-37

```bash
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 \
  /sha1 <cert-sha1> /f <cert.pem> XR-Setup.exe
osslsigncode verify XR-Setup.exe
```

Credential: EV code-signing certificate on an HSM/token (CA/B 2023–2026
rules — hardware-key-only; lead times + SmartScreen reputation program
recorded in `docs/state/research-log-P10.md` item 4).

## What the guard refuses (fail-closed)

Any release channel (`beta`/`stable`) without `XR_SIGN_PROVIDER` is a
refusal at argv-construction time (`platform_argv.py guard`) and at
artifact time (`build/signing/sign_artifact.py` refuses release channels
outright until real HSM certs land). "We'll self-sign just this once" is
a P10 failure condition, not a workaround.
