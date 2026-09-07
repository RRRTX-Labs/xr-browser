#!/usr/bin/env bash
# provision-linux.sh — provision a Linux bare-metal XR build runner (P2-T4).
#
# Creates the service user, installs the systemd unit (xr-builder.service),
# and prints the GitHub Actions self-hosted runner registration command.
# This is a PROVISIONING SCRIPT, not a live machine (HG-9: provisioning runs
# on real hardware by ops). Idempotent.
set -euo pipefail

SVC_USER="${SVC_USER:-xrbuilder}"

if ! id "$SVC_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "$SVC_USER"
fi

install -d -o "$SVC_USER" -g "$SVC_USER" /opt/xr-runner
install -m 0644 "$(dirname "$0")/xr-builder.service" /etc/systemd/system/xr-builder.service
systemctl daemon-reload

cat <<'EOF'
Provisioned. Next (manual, once, on the machine):
  1. su - xrbuilder && cd /opt/xr-runner
  2. download + run the actions-runner tarball (docs.github.com, "about self-hosted runners")
  3. ./config.sh --url https://github.com/RRRTX-Labs/xr-browser --labels xr-linux
  4. systemctl enable --now xr-builder.service

Hardware minimum (Plan §13.1, sized for 26 canaries/yr × 3 OS × dbg+rel):
  ≥ 16 cores, ≥ 64 GB RAM, ≥ 500 GB NVMe (checkout ~120 GB + ccache 50 GB +
  out/ dirs), x86-64 (arm64 lane separate).
EOF
