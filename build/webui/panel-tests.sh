#!/usr/bin/env bash
# build/webui/panel-tests.sh — the panel's focus-containment lane (P13-T1).
#
# What runs:
#   1. esbuild-bundles xr-core/ui/panel/focus-trap.ts into a SCRATCH directory
#      outside both repos (tests never write into the tree), using the pinned,
#      allowlisted toolchain (ui/toolchain: lit/axe-core/esbuild/typescript);
#   2. runs xr-core/ui/panel/tests/focus-trap.test.mjs under node:test against
#      that bundle.
#
# Why a bundle and not the .ts directly: this sandbox has no browser and the
# toolchain is dependency-frozen (no jsdom/happy-dom, no node TS loader), so the
# containment core is proved through a hand-rolled focus world. The DOM-facing
# half is type-checked by the toolchain lane (`tsc --strict`, which
# ui/tsconfig.json now includes ui/panel/*.ts in) and exercised on the farm —
# the browser halves are NOT-RUN with methods in docs/qa/browser-harness.md.
#
# --plant-leak (the negative this lane exists to make possible): copies the
# panel sources to scratch, plants the leak the phase brief names — containment
# deleted, i.e. `containedTarget` always answers null — bundles THAT, and
# requires node:test to FAIL. Exit 0 only when the leak is caught: a lane that
# cannot fail proves nothing, and a trap is exactly the kind of code whose test
# can pass while containing nothing.
#
# Exit: 0 pass · 1 fail · 77 skip-visible (node/npm/registry unavailable).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
UI_CORE="${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}"
TOOLCHAIN="$UI_CORE/ui/toolchain"
PANEL="$UI_CORE/ui/panel"
SCRATCH="${TMPDIR:-/tmp}/xr-panel-tests.$$"
MODE="${1:-}"

command -v node >/dev/null 2>&1 || { echo "panel-tests: SKIP (node not installed) — sources shipped"; exit 77; }
[ -d "$PANEL" ] || { echo "panel-tests: FAIL — no $PANEL"; exit 1; }

mkdir -p "$SCRATCH/src"
trap 'rm -rf "$SCRATCH"' EXIT

# The pinned toolchain's node_modules (installed by build/webui/toolchain.sh).
# Absent -> install from the lock; registry unreachable -> SKIP visible.
if [ ! -d "$TOOLCHAIN/node_modules/esbuild" ]; then
  command -v npm >/dev/null 2>&1 || { echo "panel-tests: SKIP (npm not installed) — sources shipped"; exit 77; }
  ( cd "$TOOLCHAIN" && npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 ) \
    || { echo "panel-tests: SKIP — npm ci failed (registry unreachable or lock drift)"; exit 77; }
fi

PLANTED=0
if [ "$MODE" = "--plant-leak" ]; then
  PLANTED=1
  cp "$PANEL/focus-trap.ts" "$SCRATCH/src/focus-trap.ts"
  # The leak: containment removed. `containedTarget` returns null for every
  # call, so the frame never intercepts an escaping Tab — exactly the defect
  # the positive tests assert cannot happen.
  python3 - "$SCRATCH/src/focus-trap.ts" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
anchor = "  const inside = focusables(world, root);\n"
assert anchor in t, "planted-leak anchor missing (has focus-trap.ts changed shape?)"
t = t.replace(anchor, "  if (true) return null;  // PLANTED LEAK (panel-tests.sh)\n" + anchor, 1)
p.write_text(t, encoding="utf-8")
PY
  [ $? -eq 0 ] || { echo "panel-tests: FAIL — could not plant the leak"; exit 1; }
  echo "panel-tests: --plant-leak: containment removed in a scratch copy ($SCRATCH)"
else
  cp "$PANEL/focus-trap.ts" "$SCRATCH/src/focus-trap.ts"
fi

SRC="$SCRATCH/src/focus-trap.ts"
BUNDLE="$SCRATCH/focus-trap.mjs"
( cd "$TOOLCHAIN" && node_modules/.bin/esbuild "$SRC" --bundle --format=esm \
    --platform=neutral --target=es2022 --outfile="$BUNDLE" --log-level=warning ) \
  || { echo "panel-tests: FAIL — esbuild could not bundle focus-trap.ts"; exit 1; }

echo "panel-tests: node --test ui/panel/tests/focus-trap.test.mjs"
if XR_PANEL_TRAP_BUNDLE="$BUNDLE" node --test "$PANEL/tests/focus-trap.test.mjs" 2>&1 \
    | sed "s/^/  /"; then
  SUITE=0
else
  SUITE=1
fi

if [ "$PLANTED" = "1" ]; then
  if [ "$SUITE" -eq 0 ]; then
    echo "panel-tests: FAIL — the planted leak did NOT redden the suite (the trap's test has no teeth)"
    exit 1
  fi
  echo "panel-tests: PASS — the planted leak reddens the suite (containment is really tested)"
  exit 0
fi
if [ "$SUITE" -ne 0 ]; then
  echo "panel-tests: FAIL — focus-containment suite failed"
  exit 1
fi
echo "panel-tests: PASS (focus containment: wrap, intercept, re-open race, restore, planted-leak control)"
exit 0
