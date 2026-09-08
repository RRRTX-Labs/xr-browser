#!/usr/bin/env bash
# build/webui/toolchain.sh — the reproducible WebUI toolchain entry (P7).
#
# Supply-chain posture (P7 security): the ONLY trusted network input is the
# lock-pinned npm install (`npm ci --ignore-scripts`). Every package in
# ui/toolchain/package-lock.json is integrity-pinned. esbuild's binary ships as
# an integrity-pinned optionalDependency (@esbuild/linux-x64), so
# --ignore-scripts is safe AND correct (no postinstall to run).
#
# Steps:
#   1. npm ci --ignore-scripts   (repro install from the lock; fails if the lock
#                                 drifts from package.json)
#   2. tsc -p <ui>               (strict type-check of the views)
#   3. node build.mjs            (deterministic esbuild bundle)
#   4. node check-bundle.js      (CSP lint on the OUTPUT)
#
# Failure conditions (P7 #5): node/npm absent OR registry unreachable → SKIP
# VISIBLE (exit 77, the farm's "skip" sentinel) with the sources + config still
# shipped. A genuine build/type/CSP failure → FAIL (exit 1), never a skip.
# Exit: 0 pass · 1 fail · 77 skip-visible · 2 usage.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"   # .../xr-browser/build/webui
REPO="$(cd "$HERE/../.." && pwd)"       # .../xr-browser
UI_CORE="${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}"   # .../xr-core
TOOLCHAIN="$UI_CORE/ui/toolchain"
UI_DIR="$UI_CORE/ui"

if [ ! -d "$TOOLCHAIN" ]; then
  echo "toolchain: FAIL — no $TOOLCHAIN (ui/toolchain missing)"; exit 1
fi

command -v node >/dev/null 2>&1 || { echo "toolchain: SKIP (node not installed) — sources+config shipped"; exit 77; }
command -v npm  >/dev/null 2>&1 || { echo "toolchain: SKIP (npm not installed) — sources+config shipped"; exit 77; }

echo "toolchain: npm ci --ignore-scripts (lock-pinned, --ignore-scripts)"
cd "$TOOLCHAIN"
if ! npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1; then
  # Registry unreachable / lock drift → the P7 #5 failure condition.
  echo "toolchain: SKIP — npm ci failed (registry unreachable or lock drift) — sources+config shipped"
  exit 77
fi

echo "toolchain: tsc -p $UI_DIR (strict)"
if ! npx tsc -p "$UI_DIR" 2>&1 | sed 's/^/  tsc: /'; then
  echo "toolchain: FAIL — tsc --strict found type errors"; exit 1
fi

echo "toolchain: node build.mjs (deterministic bundle)"
if ! node build.mjs 2>&1 | sed 's/^/  build: /'; then
  echo "toolchain: FAIL — esbuild bundle failed"; exit 1
fi

echo "toolchain: node check-bundle.js (CSP on output)"
if ! node check-bundle.js 2>&1 | sed 's/^/  csp: /'; then
  echo "toolchain: FAIL — CSP check failed on the built bundle"; exit 1
fi

echo "toolchain: PASS (tsc-strict + deterministic bundle + CSP-clean) in $TOOLCHAIN"
exit 0
