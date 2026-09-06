# Toolchain pins — how every digest was captured (R0 rung)

`pins.json` is the **R0 reproducibility artifact** (Plan §13.7): pinned inputs +
recorded toolchain digests. It is NOT a promise of chromium-wide bit-identical
builds (R4 is never promised). Each value's capture path:

| Value | Captured how | Command |
|---|---|---|
| `clang.version` | transcribed from the pinned tree | `curl "…/+/d04cdb24…/tools/clang/scripts/update.py?format=TEXT"` → `CLANG_REVISION`/`CLANG_SUB_REVISION`/`RELEASE_VERSION` |
| `clang.linux_artifact_sha256` | **PENDING-CAPTURE** — artifact is CIPD-fetched, not in-tree | `provenance.py --record` on a synced checkout downloads the tarball and hashes it |
| `sysroot[*].sha256` | transcribed from the pinned tree | `…/build/linux/sysroot_scripts/sysroots.json?format=TEXT` (all 9 entries) |
| `mac.*` | transcribed from the pinned tree | `…/build/config/mac/mac_sdk.gni?format=TEXT` |
| `win.sdk` | transcribed from the pinned tree | `…/build/vs_toolchain.py?format=TEXT` (`SDK_VERSION = '10.0.26100.0'`) |
| `depot_tools.revision` | observed live | `git ls-remote https://chromium.googlesource.com/chromium/tools/depot_tools.git HEAD` |

`provenance.py --verify` (CI) checks schema + that every digest is a 64-hex
sha256 and flags `PENDING-CAPTURE` honestly. `provenance.py --record` (a synced
checkout, L2+) replaces PENDING-CAPTURE with a digest **from the fetched
artifact** — never typed.
