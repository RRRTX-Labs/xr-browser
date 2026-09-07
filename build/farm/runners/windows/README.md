# Windows build runner — provisioning (definition; HG-9 runs it live)

Windows runners are VMs (Plan §13.1) running the GitHub Actions self-hosted
runner **as a service**. No GUI pipelines (§13.1); everything below is
PowerShell, scripted, reviewable.

## Provision

```powershell
# 1. Create the service account (no interactive login needed)
$pw = Read-Host -AsSecureString
New-LocalUser -Name "xrbuilder" -Password $pw -PasswordNeverExpires

# 2. Download + extract the actions-runner tarball (docs.github.com:
#    "about self-hosted runners") to C:\actions-runner

# 3. Configure with the xr-win label
cd C:\actions-runner
.\config.cmd --url https://github.com/RRRTX-Labs/xr-browser --labels xr-win

# 4. Install as a service (run as xrbuilder, auto-start)
.\svc.cmd install
.\svc.cmd start
```

## Requirements

- Windows 11 Enterprise (or Server 2022) x64; WDK/SDK per
  `build/toolchain/pins.json` (`win.sdk`, `win.wdk`).
- `depot_tools` NOT pre-installed — `./scripts/build sync` fetches it at runtime.
- ccache via winget/`choco install ccache`; ccache-setup.sh is POSIX — the
  Windows equivalent is `ccache --set-config=max_size=50G` run once.
- Hardware: ≥ 16 cores, ≥ 64 GB RAM, ≥ 500 GB SSD (same sizing as Linux).

## Capacity note (Plan P2-T4)

The farm is sized for **26 Chromium canaries/year × 3 OS × {dbg, rel}** plus
per-PR subset builds (§13.3). Nightly full-Chromium builds run on the nightly
job (P3), not on every PR — see `ci/build-lane.yml`.
