#!/usr/bin/env bash
# make_test_signing_material.sh — TEST-ONLY signing scaffold (P2-T8).
#
# Generates: a local CA + codesigning TEST certs (mac/win emulation) via
# openssl, and a minisign keypair (if minisign is installed). REAL certs are
# HSM-backed and land in P10 — none exist here, by design (ADR-0004).
#
# LOUDLY TEST-ONLY: filenames, cert subjects, and this header all say TEST.
# REFUSES to run if XR_PROD_SIGN=1 is present (there is no production key
# material in this repo, and this script must never be confused with it).
set -euo pipefail

if [[ "${XR_PROD_SIGN:-}" == "1" ]]; then
  echo "REFUSING: XR_PROD_SIGN=1 is set. This script is TEST-ONLY (P2 scaffold)." >&2
  echo "Real certs land in P10 (HSM) — no production signing material lives here." >&2
  exit 1
fi

command -v openssl >/dev/null 2>&1 || { echo "error: openssl required" >&2; exit 1; }

OUT="${1:-$(dirname "$0")/out}"
mkdir -p "$OUT"

# --- local TEST CA ---
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -subj "/CN=XR TEST ROOT CA (TEST-ONLY)/O=RRRTX Labs TEST/OU=not-for-production" \
  -keyout "$OUT/test-root-ca.key" -out "$OUT/test-root-ca.crt" 2>/dev/null

# --- mac codesigning TEST identity (self-signed leaf) ---
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -subj "/CN=XR TEST Mac Codesigning (TEST-ONLY)/O=RRRTX Labs TEST/OU=not-for-production" \
  -keyout "$OUT/test-mac-codesign.key" -out "$OUT/test-mac-codesign.crt" 2>/dev/null

# --- windows TEST code-signing cert (PKCS#12 for signtool emulation) ---
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -subj "/CN=XR TEST Win Codesigning (TEST-ONLY)/O=RRRTX Labs TEST/OU=not-for-production" \
  -keyout "$OUT/test-win-codesign.key" -out "$OUT/test-win-codesign.crt" 2>/dev/null
openssl pkcs12 -export -out "$OUT/test-win-codesign.pfx" -inkey "$OUT/test-win-codesign.key" \
  -in "$OUT/test-win-codesign.crt" -passout pass:test-only 2>/dev/null

# --- minisign keypair (test) ---
if command -v minisign >/dev/null 2>&1; then
  minisign -G -s "$OUT/test-minisign.key" -p "$OUT/test-minisign.pub" \
    -c "XR TEST minisign (TEST-ONLY) — not for release signatures" >/dev/null 2>&1
  echo "minisign keypair generated (TEST-ONLY)"
else
  echo "note: minisign not installed — skipped keypair generation (install minisign to generate)"
fi

echo "TEST signing material written to $OUT (TEST-ONLY — never ship, never sign releases)."
