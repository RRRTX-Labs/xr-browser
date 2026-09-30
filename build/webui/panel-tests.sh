#!/usr/bin/env bash
# build/webui/panel-tests.sh — the panel's pure-core lanes (P13-T1, P13-C-P0.1).
#
# What runs:
#   1. esbuild-bundles xr-core/ui/panel/focus-trap.ts into a SCRATCH directory
#      outside both repos (tests never write into the tree), using the pinned,
#      allowlisted toolchain (ui/toolchain: lit/axe-core/esbuild/typescript);
#   2. runs xr-core/ui/panel/tests/focus-trap.test.mjs under node:test against
#      that bundle;
#   2b. the same for tab-registry.ts + tests/tab-registry.test.mjs, with the
#      REAL inventory (ui/panel/tabs.json) pointed in — the runtime half of the
#      P13-C-P0.1 §10 unit change (a tab is DECLARED; a `.ts` file is not a tab);
#   2c. site-tab.ts (P13-T2) against the REAL reason-code table
#      (docs/shield/reason-codes.json), so the two repos cannot drift about the
#      closed verdict vocabulary.
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
PY="${PYTHON:-python3}"
# P13-C-P0.2b: the sibling is RESOLVED AND PROVEN, never guessed. This was
# `${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}` — the same defect class as the
# python tools, in the one language the first sweep's patterns did not describe:
# a stale or absent ../xr-core here would have bundled a DIFFERENT panel into
# the suite, and the suite would have passed. `--xr-core`/XR_CORE still wins as
# an explicit override; otherwise one resolver answers, and BLOCKED-LAYOUT /
# STALE-SIBLING / DIRTY-SIBLING are reported as themselves, exit 2.
UI_CORE="${XR_CORE:-}"
if [ -z "$UI_CORE" ]; then
  UI_CORE="$("$PY" "$REPO/tools/xr_sibling.py" --repo "$REPO" --print-path)" || {
    echo "panel-tests: FAIL — the sibling checkout is not at the DEPS pin (above)"; exit 2; }
fi
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
cp "$PANEL/tab-registry.ts" "$SCRATCH/src/tab-registry.ts"
cp "$PANEL/site-tab.ts" "$SCRATCH/src/site-tab.ts"
cp "$PANEL/observatory-tab.ts" "$SCRATCH/src/observatory-tab.ts"
cp "$PANEL/update-tab.ts" "$SCRATCH/src/update-tab.ts"
cp "$PANEL/sent-tab.ts" "$SCRATCH/src/sent-tab.ts"
cp "$PANEL/breakage-tab.ts" "$SCRATCH/src/breakage-tab.ts"

_bundle() {   # <src-ts> <out-mjs> <label>
  ( cd "$TOOLCHAIN" && node_modules/.bin/esbuild "$1" --bundle --format=esm \
      --platform=neutral --target=es2022 --outfile="$2" --log-level=warning ) \
    || { echo "panel-tests: FAIL — esbuild could not bundle $3"; exit 1; }
}

_bundle "$SCRATCH/src/focus-trap.ts" "$SCRATCH/focus-trap.mjs" focus-trap.ts
_bundle "$SCRATCH/src/tab-registry.ts" "$SCRATCH/tab-registry.mjs" tab-registry.ts
_bundle "$SCRATCH/src/site-tab.ts" "$SCRATCH/site-tab.mjs" site-tab.ts
_bundle "$SCRATCH/src/observatory-tab.ts" "$SCRATCH/observatory-tab.mjs" observatory-tab.ts
_bundle "$SCRATCH/src/update-tab.ts" "$SCRATCH/update-tab.mjs" update-tab.ts
_bundle "$SCRATCH/src/sent-tab.ts" "$SCRATCH/sent-tab.mjs" sent-tab.ts
_bundle "$SCRATCH/src/breakage-tab.ts" "$SCRATCH/breakage-tab.mjs" breakage-tab.ts

echo "panel-tests: node --test ui/panel/tests/focus-trap.test.mjs"
TAP_OUT="$SCRATCH/focus-trap-tap.txt"
XR_PANEL_TRAP_BUNDLE="$SCRATCH/focus-trap.mjs" \
  node --test "$PANEL/tests/focus-trap.test.mjs" >"$TAP_OUT" 2>&1 && SUITE=0 || SUITE=1
if [ "$PLANTED" = "1" ] && [ "$SUITE" -ne 0 ] && [ "${XR_PANEL_TAP:-0}" != "1" ]; then
  # The planted-leak control prints its VERDICT, not its diagnostics. The suite
  # is REQUIRED to fail here, and node:test labels an unnamed callback
  # `TestContext.<anonymous>` — a banned-vocabulary string that every transcript
  # quoting this lane carries into evidence/, which the vocabulary lane scans.
  # The closing battery hit exactly that (P13-C-CLOSE, 2026-09-30): the same six
  # frames sat at a different line in each regeneration, so line-precise
  # allowlisting of a GENERATED transcript was a losing game — and a lane whose
  # PASS path prints banned words poisons every capture that includes it.
  # What is printed is what the control is for: the failing subtest names and
  # the counts (the leak must break the laws, not crash the runner). The full
  # TAP is one env var away, and a control that FAILS TO FIRE still prints
  # everything, so a broken trap can never hide behind the summary.
  grep -E 'not ok [0-9]+|^# (tests|pass|fail)' "$TAP_OUT" | sed "s/^/  /"
  echo "  (verdict only — XR_PANEL_TAP=1 prints the full node:test TAP)"
else
  sed "s/^/  /" "$TAP_OUT"
fi

if [ "$PLANTED" = "0" ]; then
  echo "panel-tests: node --test ui/panel/tests/tab-registry.test.mjs"
  if XR_PANEL_TABS_BUNDLE="$SCRATCH/tab-registry.mjs" \
     XR_PANEL_TABS_INVENTORY="$PANEL/tabs.json" \
     node --test "$PANEL/tests/tab-registry.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
  # P13-T6: the what-would-be-sent viewer. One serializer drives both the
  # payload and the preview; the planted-field control lives in the suite.
  echo "panel-tests: node --test ui/panel/tests/sent-tab.test.mjs"
  if XR_PANEL_SENT_BUNDLE="$SCRATCH/sent-tab.mjs" \
     node --test "$PANEL/tests/sent-tab.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
  # P13-T4: the breakage tab's core — a closed row set, a fixture-only queue,
  # and a confirmation that throws if anything asks for a modal.
  echo "panel-tests: node --test ui/panel/tests/breakage-tab.test.mjs"
  if XR_PANEL_BREAKAGE_BUNDLE="$SCRATCH/breakage-tab.mjs" \
     node --test "$PANEL/tests/breakage-tab.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
  # P13-T5: the update tab's pure core (closed verb set; no progress states).
  echo "panel-tests: node --test ui/panel/tests/update-tab.test.mjs"
  if XR_PANEL_UPDATE_BUNDLE="$SCRATCH/update-tab.mjs" \
     node --test "$PANEL/tests/update-tab.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
  # P13-T3: the Observatory's pure core (windowing + the a11y position law).
  echo "panel-tests: node --test ui/panel/tests/observatory-tab.test.mjs"
  if XR_PANEL_OBSERVATORY_BUNDLE="$SCRATCH/observatory-tab.mjs" \
     node --test "$PANEL/tests/observatory-tab.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
  # P13-T2: the Site tab's pure core. The why table is xr-browser's own
  # (docs/shield/reason-codes.json), so this lane also proves the two repos
  # agree on the closed verdict vocabulary without a copy in either.
  echo "panel-tests: node --test ui/panel/tests/site-tab.test.mjs"
  if XR_PANEL_SITE_BUNDLE="$SCRATCH/site-tab.mjs" \
     XR_PANEL_WHY_TABLE="$REPO/docs/shield/reason-codes.json" \
     node --test "$PANEL/tests/site-tab.test.mjs" 2>&1 | sed "s/^/  /"; then
    :
  else
    SUITE=1
  fi
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
  echo "panel-tests: FAIL — focus-containment/tab-registry suite failed"
  exit 1
fi
echo "panel-tests: PASS (focus containment: wrap, intercept, re-open race, restore, planted-leak control; tab registry: inventory bijection, typed refusals; site tab: single-scope dial, why-drill over every reason code + typed fallback; observatory: 2k ring, last-screenful clamp, a11y positions; update tab: closed verb set, no progress states; breakage tab: closed row set, fixture queue, non-attentional confirm; what-would-be-sent: one serializer, planted field renders)"
exit 0
