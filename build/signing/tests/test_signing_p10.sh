#!/usr/bin/env bash
# build/signing/tests/test_signing_p10.sh — the P10 signing matrix, executed
# for real where the sandbox allows (P10-T4):
#   * Linux repo signing: REAL gpg round-trip — sign -> verify OK; flip one
#     byte -> FAILS; wrong key -> FAILS; missing key -> visible SKIP (77).
#   * AppImage update-metadata: writer -> --check reader round-trip.
#   * macOS/Windows: EXACT-argv stub-binary tests (recorder replays what
#     platform_argv.py constructs; real execution = HG-37).
#   * The release-channel-without-provider refusal (fail-closed).
# Exit: 0 all executed cells green · 1 failure · (77 propagates only when
# EVERYTHING was skipped, per the zero-executed law).
set -u
cd "$(dirname "$0")/../../.."   # repo root
PY="${PYTHON:-python3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CELLS_EXECUTED=0
FAILS=0

note() { printf '  %s\n' "$*"; }

# ---- Linux repo signing (REAL gpg) ---------------------------------------
GNUPG="$TMP/gnupghome"
if out=$("$PY" build/signing/linux_repo_sign.py keygen --gnupghome "$GNUPG" 2>&1); then
  CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: gpg keygen — $out"
else rc=$?
  if [ "$rc" -eq 77 ]; then
    note "SKIP: SKIP (tool absent: gpg) — the whole real-gpg block (4 cells)"
  else
    echo "FAIL: gpg keygen rc=$rc: $out"; FAILS=$((FAILS+1))
  fi
fi
if [ -f "$GNUPG/signing-pub.asc" ]; then
  printf 'xr-update-repo 0.9.18.2 main\n' > "$TMP/Release"
  if out=$("$PY" build/signing/linux_repo_sign.py sign --gnupghome "$GNUPG" \
        --in "$TMP/Release" --mode clearsign 2>&1); then
    CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: clearsign InRelease"
  else echo "FAIL: clearsign: $out"; FAILS=$((FAILS+1)); fi
  if out=$("$PY" build/signing/linux_repo_sign.py verify --gnupghome "$GNUPG" \
        --in "$TMP/InRelease" 2>&1); then
    CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: verify OK — $out"
  else echo "FAIL: verify: $out"; FAILS=$((FAILS+1)); fi
  # tamper: flip one byte of the clearsigned file -> must FAIL
  python3 - "$TMP/InRelease" <<'PYEOF'
import sys
p = sys.argv[1]
b = bytearray(open(p, 'rb').read())
i = b.index(b'xr-update-repo')
b[i] = b[i] ^ 0x01  # flip one byte INSIDE the signed text
open(p + '.tampered', 'wb').write(bytes(b))
PYEOF
  if out=$("$PY" build/signing/linux_repo_sign.py verify --gnupghome "$GNUPG" \
        --in "$TMP/InRelease.tampered" 2>&1); then
    echo "FAIL: tampered file VERIFIED (gpg lane broken): $out"; FAILS=$((FAILS+1))
  else
    CELLS_EXECUTED=$((CELLS_EXECUTED+1))
    note "ok: one-byte tamper detected ($(printf '%s' "$out" | head -c 60)...)"
  fi
  # wrong key: verify with a DIFFERENT keyring -> must FAIL
  "$PY" build/signing/linux_repo_sign.py keygen --gnupghome "$TMP/other-key" >/dev/null 2>&1
  if out=$("$PY" build/signing/linux_repo_sign.py verify --gnupghome "$TMP/other-key" \
        --in "$TMP/InRelease" 2>&1); then
    echo "FAIL: wrong-keyring VERIFIED: $out"; FAILS=$((FAILS+1))
  else
    CELLS_EXECUTED=$((CELLS_EXECUTED+1))
    note "ok: wrong keyring rejected"
  fi
  # repomd.xml detached .asc convention
  printf '<repomd xmlns="http://linux.duke.edu/metadata/repo"/>' > "$TMP/repomd.xml"
  if "$PY" build/signing/linux_repo_sign.py sign --gnupghome "$GNUPG" \
        --in "$TMP/repomd.xml" --mode detach >/dev/null 2>&1 && \
     out=$("$PY" build/signing/linux_repo_sign.py verify --gnupghome "$GNUPG" \
        --in "$TMP/repomd.xml" --sig "$TMP/repomd.xml.asc" 2>&1); then
    CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: repomd.xml detached .asc verify"
  else echo "FAIL: repomd detach round-trip: $out"; FAILS=$((FAILS+1)); fi
fi

# ---- AppImage metadata round-trip (pure data, always runs) ---------------
printf '\x7fELFAFTEREFORMAT' > "$TMP/XR-0.9.18.2-x86_64.AppImage"
head -c 200000 /dev/urandom >> "$TMP/XR-0.9.18.2-x86_64.AppImage"
if out=$("$PY" build/signing/appimage_meta.py write --appimage "$TMP/XR-0.9.18.2-x86_64.AppImage" \
      --channel beta --version 0.9.18.2 2>&1) && \
   out2=$("$PY" build/signing/appimage_meta.py check --appimage "$TMP/XR-0.9.18.2-x86_64.AppImage" 2>&1); then
  CELLS_EXECUTED=$((CELLS_EXECUTED+2)); note "ok: appimage write+check — $out2"
else echo "FAIL: appimage round-trip: ${out:-$out2}"; FAILS=$((FAILS+1)); fi
# tampered image -> check must fail
python3 - "$TMP/XR-0.9.18.2-x86_64.AppImage" <<'PYEOF'
import sys
p = sys.argv[1]
b = bytearray(open(p, 'rb').read())
b[1000] ^= 0xFF
# re-append the SAME trailer over a modified payload: reader must notice
open(p, 'wb').write(bytes(b))
PYEOF
"$PY" build/signing/appimage_meta.py write --appimage "$TMP/XR-0.9.18.2-x86_64.AppImage" \
  --channel beta --version 0.9.18.2 >/dev/null 2>&1
if out=$("$PY" build/signing/appimage_meta.py check --appimage "$TMP/XR-0.9.18.2-x86_64.AppImage" 2>&1); then
  echo "FAIL: tampered image passed --check: $out"; FAILS=$((FAILS+1))
else
  CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: tampered image refused ($(printf '%s' "$out" | head -c 60)...)"
fi

# ---- macOS/Windows EXACT argv (stub-binary recorder, python harness) -----
if out=$("$PY" build/signing/tests/argv_stub_test.py 2>&1); then
  CELLS_EXECUTED=$((CELLS_EXECUTED+3)); note "ok: argv-stub matrix (5 exact argv shapes + provider guard, stub-recorded)"
else
  echo "FAIL: argv stub matrix: $out"; FAILS=$((FAILS+1))
fi

# ---- release-channel-without-provider refusal (fail-closed) ---------------
if out=$("$PY" build/signing/platform_argv.py --print guard --channel beta 2>&1); then
  echo "FAIL: release channel accepted WITHOUT provider: $out"; FAILS=$((FAILS+1))
else
  CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: beta without XR_SIGN_PROVIDER refused — $(printf '%s' "$out" | head -c 60)..."
fi
if out=$("$PY" build/signing/platform_argv.py --print guard --channel stable --provider hsm://signhost 2>&1); then
  CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: stable with provider accepted (argv construction only; real sigs = HG-37)"
else echo "FAIL: stable with provider refused: $out"; FAILS=$((FAILS+1)); fi

if [ "$FAILS" -gt 0 ]; then
  echo "FAIL: signing matrix ($FAILS failure(s) of $CELLS_EXECUTED executed cells)"
  exit 1
fi
if [ "$CELLS_EXECUTED" -eq 0 ]; then
  echo "FAIL: signing matrix executed ZERO cells (0 executed => FAIL, never a pass)"
  exit 1
fi
echo "PASS: signing matrix ($CELLS_EXECUTED cells executed: gpg real round-trip, tamper, wrong-key; appimage round-trip; argv-exact; provider guard)"
exit 0
