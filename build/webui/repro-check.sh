#!/usr/bin/env bash
# build/webui/repro-check.sh — R1 reproducibility rung (P7).
#
# Builds the WebUI bundle TWICE from the same tree and asserts the outputs are
# BYTE-IDENTICAL (this is the "stable" rung that gates later tracks' WebUI
# builds — P8/P13). A divergence is a FAIL (non-repro build = not shippable).
#
# Failure conditions (P7 #5): node/npm absent OR registry unreachable → SKIP
# VISIBLE (exit 77) with sources+config shipped. Non-repro output → FAIL (1).
# Exit: 0 pass · 1 fail · 77 skip-visible · 2 usage.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"   # .../xr-browser/build/webui
REPO="$(cd "$HERE/../.." && pwd)"       # .../xr-browser
UI_CORE="${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}"   # .../xr-core
TOOLCHAIN="$UI_CORE/ui/toolchain"

command -v node >/dev/null 2>&1 || { echo "repro-check: SKIP (node not installed)"; exit 77; }
command -v npm  >/dev/null 2>&1 || { echo "repro-check: SKIP (npm not installed)"; exit 77; }
[ -d "$TOOLCHAIN" ] || { echo "repro-check: FAIL — no $TOOLCHAIN"; exit 1; }

cd "$TOOLCHAIN"
npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 || {
  echo "repro-check: SKIP — npm ci failed (registry unreachable or lock drift) — sources+config shipped"; exit 77; }

build() {
  rm -rf dist "$1"
  node build.mjs >/dev/null 2>&1 || { echo "repro-check: FAIL — build failed"; exit 1; }
  mkdir -p "$1" && cp -r dist/. "$1"/
}

build "$TOOLCHAIN/.repro_a"
build "$TOOLCHAIN/.repro_b"

A=$(cat "$TOOLCHAIN"/.repro_a/{bundle.js,index.html,tokens.css} | sha256sum | cut -d' ' -f1)
B=$(cat "$TOOLCHAIN"/.repro_b/{bundle.js,index.html,tokens.css} | sha256sum | cut -d' ' -f1)
BA=$(sha256sum "$TOOLCHAIN"/.repro_a/bundle.js | cut -d' ' -f1)
BB=$(sha256sum "$TOOLCHAIN"/.repro_b/bundle.js | cut -d' ' -f1)

rm -rf "$TOOLCHAIN/.repro_a" "$TOOLCHAIN/.repro_b"

echo "repro-check: bundle build_a=$BA"
echo "repro-check: bundle build_b=$BB"
echo "repro-check: all    build_a=$A"
echo "repro-check: all    build_b=$B"
if [ "$A" = "$B" ]; then
  echo "repro-check: PASS — two independent builds are byte-identical (R1 repro rung)"
  exit 0
else
  echo "repro-check: FAIL — non-reproducible build (two builds diverged)"
  exit 1
fi
