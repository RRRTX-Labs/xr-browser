#!/usr/bin/env bash
# build/webui/identity-chrome-tests.sh — the identity chrome's pure-core lane
# (P14-T4, P14-CLOSE C-1).
#
# 1. esbuild-bundles xr-core/ui/identity-chrome/chrome-core.ts into a SCRATCH
#    directory outside both repos, using the pinned, allowlisted toolchain
#    (ui/toolchain). Tests never write into the tree.
# 2. Runs ui/identity-chrome/tests/identity-chrome.test.mjs under node:test
#    against that bundle, with the REAL states.json, ui/themes/tokens.json and
#    the committed per-layout x per-theme snapshots pointed in. The last test
#    requires the core to reproduce every snapshot that
#    tools/identity_chrome_check.py generated, so the two cannot drift.
#
# --plant-drift (the negative): copies chrome-core.ts to scratch and breaks the
# rail layout's first-letter rule, so the dot is labelled with the full name.
# It bundles THAT and REQUIRES the suite to fail. Exit 0 only when the drift
# is caught.
#
# The lit elements (identity-chrome.ts) are type-checked by the toolchain
# lane (`tsc --strict`; ui/tsconfig.json includes identity-chrome/*.ts).
# Pixels are NOT-RUN (docs/qa/browser-harness.md#identity-chrome-visual).
#
# Exit: 0 pass · 1 fail · 2 layout · 77 skip-visible (node/npm/registry absent).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
UI_CORE="${XR_CORE:-}"
if [ -z "$UI_CORE" ]; then
  UI_CORE="$("$PY" "$REPO/tools/xr_sibling.py" --repo "$REPO" --print-path)" || {
    echo "identity-chrome-tests: FAIL — the sibling checkout is not at the DEPS pin (above)"; exit 2; }
fi
TOOLCHAIN="$UI_CORE/ui/toolchain"
IDC="$UI_CORE/ui/identity-chrome"
MODE="${1:-}"

command -v node >/dev/null 2>&1 || { echo "identity-chrome-tests: SKIP (node not installed) — sources shipped"; exit 77; }
[ -f "$IDC/chrome-core.ts" ] || { echo "identity-chrome-tests: FAIL — no $IDC/chrome-core.ts"; exit 1; }
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/xr-idc-tests.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

if [ ! -d "$TOOLCHAIN/node_modules/esbuild" ]; then
  command -v npm >/dev/null 2>&1 || { echo "identity-chrome-tests: SKIP (npm not installed) — sources shipped"; exit 77; }
  ( cd "$TOOLCHAIN" && npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 ) \
    || { echo "identity-chrome-tests: SKIP — npm ci failed (registry unreachable or lock drift)"; exit 77; }
fi

cp "$IDC/chrome-core.ts" "$SCRATCH/chrome-core.ts"
if [ "$MODE" = "--plant-drift" ]; then
  "$PY" - "$SCRATCH/chrome-core.ts" <<'PYEOF' || { echo "identity-chrome-tests: FAIL — could not plant the drift"; exit 1; }
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
anchor = "identity.name.slice(0, 1).toUpperCase()"
assert anchor in t, "plant anchor missing (has chrome-core.ts changed shape?)"
p.write_text(t.replace(anchor, "identity.name", 1), encoding="utf-8")
PYEOF
  echo "identity-chrome-tests: --plant-drift: rail initial rule removed in a scratch copy"
fi

( cd "$TOOLCHAIN" && node_modules/.bin/esbuild "$SCRATCH/chrome-core.ts" --bundle --format=esm \
    --platform=neutral --target=es2022 --outfile="$SCRATCH/chrome-core.mjs" --log-level=warning ) \
  || { echo "identity-chrome-tests: FAIL — esbuild could not bundle chrome-core.ts"; exit 1; }

echo "identity-chrome-tests: node --test ui/identity-chrome/tests/identity-chrome.test.mjs"
TAP="$SCRATCH/tap.txt"
XR_IDC_CORE_BUNDLE="$SCRATCH/chrome-core.mjs" \
XR_IDC_STATES="$IDC/states.json" \
XR_IDC_TOKENS="$UI_CORE/ui/themes/tokens.json" \
XR_IDC_SNAPSHOTS="$IDC/snapshots" \
  node --test "$IDC/tests/identity-chrome.test.mjs" >"$TAP" 2>&1 && SUITE=0 || SUITE=1

if [ "$MODE" = "--plant-drift" ]; then
  # Verdict only (the planted run's frames carry node:test's anonymous-callback
  # label, which the vocabulary lane scans in every captured transcript).
  grep -E 'not ok [0-9]+|^# (tests|pass|fail)' "$TAP" | sed 's/^/  /'
  if [ "$SUITE" -eq 0 ]; then
    echo "identity-chrome-tests: FAIL — the planted drift did NOT redden the suite"
    exit 1
  fi
  echo "identity-chrome-tests: PASS — the planted core drift reddens the snapshot law"
  exit 0
fi
sed 's/^/  /' "$TAP"
if [ "$SUITE" -ne 0 ]; then
  echo "identity-chrome-tests: FAIL — identity chrome core suite failed"
  exit 1
fi
echo "identity-chrome-tests: PASS (every state + layout case, color never alone, contrast edge, typed refusals, SR resolution, core == every committed snapshot)"
