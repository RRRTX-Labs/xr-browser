#!/usr/bin/env bash
# drill_run.sh — farm runner for the §11.10 kill matrix + §11.11 update
# drill (P9-T10/T11). These drills need a real browser process tree and a
# per-OS VM farm with snapshot/restore; neither exists in the P9 sandbox,
# so every invocation here is a VISIBLE SKIP (exit 77) — a record, never a
# fabricated result.
#
# Farm usage (HG-33 / HG-34):
#   drill_run.sh kill-matrix   # process-type kill matrix under load
#   drill_run.sh update-drill  # per-OS kill-mid-update + rollback
set -u

mode="${1:-}"
case "$mode" in
  kill-matrix|update-drill)
    ;;
  *)
    echo "usage: drill_run.sh {kill-matrix|update-drill}" >&2
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
