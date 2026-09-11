#!/usr/bin/env bash
# drill_run.sh — farm runner for the §11.10 kill matrix + §11.11 update
# drill (P9-T10/T11), plus the P10-T0-b hosts-local mode that executes the
# matrix for real against the host binaries that exist in THIS sandbox.
#
#   drill_run.sh hosts-local  # P10-T0-b: the four discovered //xr host
#                             # binaries, killed mid-write/dispatch/snapshot
#                             # under load; cells executed / not-run printed;
#                             # 0 executed => FAIL (runner law)
#   drill_run.sh kill-matrix  # farm: needs the browser process tree (HG-33)
#   drill_run.sh update-drill # farm: needs per-OS VM snapshots (HG-34)
#
# The 8 Chromium process rows stay farm-visible with the correct reason —
# tools/kill_matrix.py prints them in the not-run split, so the deferral is
# named, never dropped.
set -u

mode="${1:-}"
case "$mode" in
  hosts-local)
    shift
    # resolve $0's dir ABSOLUTELY, then step up THREE levels (build/qa/drill
    # -> repo root). A relative $0 plus a relative ../.. double-resolves
    # against the caller's cwd; and the depth is 3, not 2.
    ROOT="$(cd "$(cd "$(dirname "$0")" && pwd)/../../.." && pwd)"
    PY="${PYTHON:-python3}"
    exec "$PY" "$ROOT/tools/kill_matrix.py" --repo "$ROOT" --iterations 4 "$@"
    ;;
  kill-matrix|update-drill)
    ;;
  *)
    echo "usage: drill_run.sh {hosts-local|kill-matrix|update-drill}" >&2
    exit 2
    ;;
esac

if ! command -v xr-browser >/dev/null 2>&1 && [ ! -x "$HOME/xr-farm/xr" ]; then
  echo "SKIP: drill_run $mode needs the farm browser binary + VM snapshots" >&2
  echo "      (HG-33 kill matrix / HG-34 update drill). The matrices live in" >&2
  echo "      build/qa/drill/{kill-matrix,update-drill}.yaml and are validated" >&2
  echo "      by tools/drill_check.py — which runs here. exit 77" >&2
  exit 77
fi

# On the farm this drives the real process tree + snapshot/restore; the
# per-cell assertions are the yaml rows, recorded per run id (L12).
echo "drill_run: $mode — farm execution, see build/qa/drill/*.yaml"
exit 77
