#!/usr/bin/env bash
# ccache-setup.sh — provision local ~/.ccache for XR builders (P2-T4).
#
# Local cache only. The remote-cache template (--remote-template) contains NO
# real endpoints — placeholders only (HG-11 signs off the endpoint + sizing).
#
# Usage: ccache-setup.sh [--maxsize 50G] [--remote-template]
set -euo pipefail

CCACHE_MAXSIZE="${CCACHE_MAXSIZE:-50G}"
CCACHE_DIR="${CCACHE_DIR:-$HOME/.ccache}"

command -v ccache >/dev/null 2>&1 || {
  echo "error: ccache not on PATH. Install it first (apt/brew/winget); it is"
  echo "referenced, never vendored (Plan P2)." >&2
  exit 1
}

mkdir -p "$CCACHE_DIR"
export CCACHE_DIR
ccache --set-config=max_size="$CCACHE_MAXSIZE"
ccache --set-config=compression=true

if [[ "${1:-}" == "--remote-template" ]]; then
  cat <<'EOF'
# Remote-cache template — NO REAL ENDPOINTS (placeholders only, HG-11).
# Do not uncomment until a human signs off the endpoint + capacity.
# Integrity flags are ON: hash-checked, no sloppiness (cache-poisoning guard).
# secondary_storage=redis://USER@CACHE.example:6379|read-only|connect-timeout=50
# remote_only=false
# recache=false
# direct=false
EOF
  echo "remote-cache template emitted (no endpoints configured)."
fi

echo "ccache ready: dir=$CCACHE_DIR max_size=$CCACHE_MAXSIZE"
ccache --show-config | grep -E 'max_size|compression' || true
