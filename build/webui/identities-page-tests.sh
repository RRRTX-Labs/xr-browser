#!/usr/bin/env bash
# build/webui/identities-page-tests.sh — the xr://identities dev page's
# pure-core lane (P14-T7, P14-CLOSE C-3).
#
# 1. Builds the identity host OUT OF TREE (scratch; the sibling stays clean)
#    and captures REAL replies: `manager-page` under --build-channel release
#    and nightly-test (the refusal) and under dev (normal / empty /
#    purge-unverified, the last via the host's named plant_residual hook).
# 2. esbuild-bundles ui/identities/identities-core.ts into scratch with the
#    pinned, allowlisted toolchain (ui/toolchain).
# 3. Runs ui/identities/tests/identities.test.mjs under node:test with the
#    core's kManagerPageStates (read from identity/core/manager_page.h) and
#    the captured replies pointed in: the view must render every state the
#    host can produce, live.
#
# --plant-drift (the negative): drops the 'purge-unverified' stateText arm
# in a scratch copy of the core and REQUIRES the suite to fail.
#
# The lit view (identities.ts) is type-checked by the toolchain lane
# (`tsc --strict`; ui/tsconfig.json includes identities/*.ts). The rendered
# page is NOT-RUN (docs/qa/browser-harness.md#identities-page-rendered).
#
# Exit: 0 pass · 1 fail · 2 layout · 77 skip-visible (node/npm/g++ absent).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
UI_CORE="${XR_CORE:-}"
if [ -z "$UI_CORE" ]; then
  UI_CORE="$("$PY" "$REPO/tools/xr_sibling.py" --repo "$REPO" --print-path)" || {
    echo "identities-page-tests: FAIL — the sibling checkout is not at the DEPS pin (above)"; exit 2; }
fi
TOOLCHAIN="$UI_CORE/ui/toolchain"
IDS="$UI_CORE/ui/identities"
MODE="${1:-}"
N="identities-page-tests"

command -v node >/dev/null 2>&1 || { echo "$N: SKIP (node not installed) — sources shipped"; exit 77; }
command -v make >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1 \
  || { echo "$N: SKIP (g++/make not installed) — the live host replies need the compiled host"; exit 77; }
[ -f "$IDS/identities-core.ts" ] || { echo "$N: FAIL — no $IDS/identities-core.ts"; exit 1; }
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/xr-ids-tests.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

if [ ! -d "$TOOLCHAIN/node_modules/esbuild" ]; then
  command -v npm >/dev/null 2>&1 || { echo "$N: SKIP (npm not installed) — sources shipped"; exit 77; }
  ( cd "$TOOLCHAIN" && npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 ) \
    || { echo "$N: SKIP — npm ci failed (registry unreachable or lock drift)"; exit 77; }
fi

make -s -C "$UI_CORE/identity/tests" "$SCRATCH/build/identity_host" BUILD="$SCRATCH/build" \
  >"$SCRATCH/make.txt" 2>&1 || { tail -20 "$SCRATCH/make.txt"; echo "$N: FAIL — identity_host did not build"; exit 1; }

"$PY" - "$SCRATCH/build/identity_host" "$UI_CORE/identity/core/manager_page.h" \
  "$SCRATCH/states.json" "$SCRATCH/replies.json" <<'PYEOF' || { echo "$N: FAIL — could not capture host replies"; exit 1; }
import json, re, subprocess, sys
host, header, states_out, replies_out = sys.argv[1:5]
m = re.search(r"kManagerPageStates\[\]\s*=\s*\{(.*?)\}", open(header, encoding="utf-8").read(), re.S)
assert m, "kManagerPageStates not found in manager_page.h"
open(states_out, "w").write(json.dumps(re.findall(r'"([a-z-]+)"', m.group(1))))
ids = [{"entropy": "ids-a", "display_name": "Work"}, {"entropy": "ids-b", "display_name": "Bank"}]
cases = {
    "dev-refused:release": ("release", {"identities": ids}),
    "dev-refused:nightly-test": ("nightly-test", {"identities": ids}),
    "normal:dev": ("dev", {"identities": ids, "tabs": [{"identity": 0, "tab_id": 1}]}),
    "empty:dev": ("dev", {"identities": []}),
    "purge-unverified:dev": ("dev", {"identities": ids, "plant_residual": [1], "purge": [1]}),
}
out = {}
for name, (ch, args) in cases.items():
    r = subprocess.run([host, "--build-channel", ch, "manager-page", json.dumps(args)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{name}: exit {r.returncode} {r.stderr[:200]}"
    out[name] = json.loads(r.stdout)
open(replies_out, "w").write(json.dumps(out))
PYEOF

cp "$IDS/identities-core.ts" "$SCRATCH/identities-core.ts"
if [ "$MODE" = "--plant-drift" ]; then
  "$PY" - "$SCRATCH/identities-core.ts" <<'PYEOF' || { echo "$N: FAIL — could not plant the drift"; exit 1; }
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
anchor = "    case 'purge-unverified':\n      return { msg: 'IDS_XR_IDENTITIES_STATE_PURGE_UNVERIFIED' };\n"
assert anchor in t, "plant anchor missing (has identities-core.ts changed shape?)"
p.write_text(t.replace(anchor, "", 1), encoding="utf-8")
PYEOF
  echo "$N: --plant-drift: the purge-unverified stateText arm removed in a scratch copy"
fi

( cd "$TOOLCHAIN" && node_modules/.bin/esbuild "$SCRATCH/identities-core.ts" --bundle --format=esm \
    --platform=neutral --target=es2022 --outfile="$SCRATCH/identities-core.mjs" --log-level=warning ) \
  || { echo "$N: FAIL — esbuild could not bundle identities-core.ts"; exit 1; }

echo "$N: node --test ui/identities/tests/identities.test.mjs"
TAP="$SCRATCH/tap.txt"
XR_IDS_CORE_BUNDLE="$SCRATCH/identities-core.mjs" \
XR_IDS_HOST_STATES="$(cat "$SCRATCH/states.json")" \
XR_IDS_HOST_REPLIES="$SCRATCH/replies.json" \
  node --test "$IDS/tests/identities.test.mjs" >"$TAP" 2>&1 && SUITE=0 || SUITE=1

if [ "$MODE" = "--plant-drift" ]; then
  grep -E 'not ok [0-9]+|^# (tests|pass|fail)' "$TAP" | sed 's/^/  /'
  if [ "$SUITE" -eq 0 ]; then
    echo "$N: FAIL — the planted drift did NOT redden the suite"
    exit 1
  fi
  echo "$N: PASS — the planted missing state arm reddens the suite"
  exit 0
fi
sed 's/^/  /' "$TAP"
if [ "$SUITE" -ne 0 ]; then
  echo "$N: FAIL — identities page core suite failed"
  exit 1
fi
echo "$N: PASS (host state union == view union; every state rendered from LIVE host replies; routes; typed purge + dev-only reset-all locks; unknown renders honestly)"
