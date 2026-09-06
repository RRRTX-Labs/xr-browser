# Network audit — the zero-egress build rule (Plan P2 security req)

**Rule:** after `./build sync`, build time performs **no fetches**. This is a
*checkable property*, not a promise in prose. L5-honest scope: the mechanisms
below are implemented and recorded; the strace/dtrace capture is a documented
procedure (human-run on the build hosts), not a service this repo can run for
you.

## 1. What `sync` records

`buildsys/sync.py` writes `<checkout>/.xr/egress.json` — an egress manifest:

```json
{
  "schema_version": 1,
  "synced_at": "ISO-8601",
  "chromium_rev": "d04cdb24…",
  "xr_core_rev": "6fb5411b…",
  "contacts": [
    {"url": "https://chromium.googlesource.com/chromium/src.git", "purpose": "solution checkout", "at": "ISO-8601"},
    {"url": "https://github.com/RRRTX-Labs/xr-core.git", "purpose": "mount src/xr", "at": "ISO-8601"},
    {"url": "https://chromium.googlesource.com/chromium/tools/depot_tools.git", "purpose": "runtime tool fetch", "at": "ISO-8601"}
  ]
}
```

This is the *declared* contact set. The declared set must equal the observed
set, exactly (§11.8 endpoint-audit discipline started here).

## 2. Verifying the observed set (documented procedure)

- **Linux:** `strace -f -e trace=network -o net.log ./build sync …` then
  `grep -oE 'sin_port=htons\([0-9]+\)|AF_INET' net.log` and cross-check the
  resolved endpoints against `.xr/egress.json`.
- **macOS:** `dtruss -f -t network ./build sync …` (SIP may require `sudo`).
- **Windows:** Sysmon `EventID 3` network-connection events during the sync
  window.

## 3. Build-time (post-sync)

`./build gen`, `./build compile`, `./build brand-check`, `./build sbom` make
**no network calls by construction** (no `urllib`, no `subprocess` reaching a
remote, no `pip install`). CI's `endpoint-scan` step (see
`buildsys/branding/brand_check.py --scan`) deny-matches
`google|gvt1|update\.chromium|update\.googleapis` against this repo's own
files. A build step that needs network is a stop-condition: design it in
(ADR + register), never smuggle it.
