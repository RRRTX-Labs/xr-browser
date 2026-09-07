# Toolchain pins — how every digest was captured (R0 rung)

`pins.json` is the **R0 reproducibility artifact** (Plan §13.7): pinned inputs +
recorded toolchain digests. It is NOT a promise of chromium-wide bit-identical
builds (R4 is never promised). Each value's capture path:

| Value | Captured how | Command |
|---|---|---|
| `clang.version` | transcribed from the pinned tree | `curl "…/+/d04cdb24…/tools/clang/scripts/update.py?format=TEXT"` → `CLANG_REVISION`/`CLANG_SUB_REVISION`/`RELEASE_VERSION` |
| `clang.linux_artifact_sha256` | **captured 2026-09-07** from the fetched tarball (`e22e06c0…c98c42`) | `provenance.py --record` downloaded the `.tar.xz` (per `update.py:226 cds_file = "%s-%s.tar.xz"`) and hashed it |
| `sysroot[*].sha256` | transcribed from the pinned tree | `…/build/linux/sysroot_scripts/sysroots.json?format=TEXT` (all 9 entries); download is content-addressed — `install-sysroot.py: url = URL + '/' + Sha256Sum` |
| `sysroot_url_base` | transcribed from `sysroots.json` `URL` field | `https://commondatastorage.googleapis.com/chrome-linux-sysroot` |
| `mac.*` | transcribed from the pinned tree | `…/build/config/mac/mac_sdk.gni?format=TEXT` |
| `win.sdk` | transcribed from the pinned tree | `…/build/vs_toolchain.py?format=TEXT` (`SDK_VERSION = '10.0.26100.0'`) |
| `depot_tools.revision` | observed live | `git ls-remote https://chromium.googlesource.com/chromium/tools/depot_tools.git HEAD` |

`provenance.py --verify` (CI) checks schema + that every digest is a 64-hex
sha256. `provenance.py --record` fetches the clang `.tar.xz` and the amd64
sysroot tarball (content-addressed by its pinned sha256), hashes them, and
writes the clang digest into `pins.json` — digests are recorded from fetched
artifacts, never typed.
