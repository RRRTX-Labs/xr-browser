# P1 Research Log (2026-09-07)

Purpose: single record of what Phase P1 verified against primary
sources, what it could NOT verify (and where that gets re-verified), and
where live evidence drifted from the pinned plan. Raw fetched artifacts
live in `/home/user/.research-p1/` (working scratch; deleted at P1
close — this log + the dependency evals are the durable record).

Method: live fetch on 2026-09-07 from primary sources (project
repositories, official blogs/docs, PyPI JSON). Anything not verifiable
from a live primary source is marked UNVERIFIED, never guessed
(user constraint: denylist-adjacent uncertainty stops the artifact).

## 1. Licensing

| Fact | Source (fetched 2026-09-07) |
|---|---|
| Verbatim MPL-2.0 text: 16,726 B, sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04` | brave/adblock-rust `LICENSE` (repo ships the verbatim text). Committed as `LICENSE` in both repos; `tools/license_audit.py` pins the hash. |
| DCO v1.1 full text | developercertificate.org |
| PyPI digest pins for PyYAML 6.0.3, pytest 9.0.3, iniconfig 2.3.0, packaging 26.2, pluggy 1.6.0, Pygments 2.20.0 | `pypi.org/pypi/<pkg>/<ver>/json` → `urls[].digests.sha256` (in `tools/requirements-dev.txt`) |

Unusable live sources (recorded, do not retry): mozilla.org MPL page
(JS-only render), hg.mozilla.org, spdx.org license page, opensource.org
page. The adblock-rust copy served as the verbatim source instead —
cross-checked at 16,726 B against the known MPL-2.0 length.

## 2. Chromium / fork viability (feeds LG-1, DR-01/02/03)

| Fact | Source |
|---|---|
| Chrome ships new beta + stable every two weeks from the Chrome 153 stable (2026-09-08), all platforms | developer.chrome.com blog "Chrome two-week release" |
| Even-milestone (Extended-Stable-equivalent) update strategy is the post-two-week norm | CEF issue #4114 (CEF update-strategy discussion) |
| In-tree Widevine CDM component installer exists under `BUILDFLAG(ENABLE_WIDEVINE_CDM_COMPONENT)` with `BUNDLE_WIDEVINE_CDM` handling; CDM lands under `user_data_path/WidevineCdm` | chromium/src `chrome/browser/component_updater/widevine_cdm_component_installer.cc` (saved copy in .research-p1) |
| "Widevine CDM is available free of charge provided you download it from Google using Chromium's component updater"; MLA required only to *encrypt content and issue licenses*; a mere client of other services "shouldn't need a license to enable Widevine support" | chromium-dev mailing list, Marshall Greenblatt re CEF (2015-10-15, thread `16hDHEpgUb8`) |
| "Automated download of the binary from Google is allowed but bundling of the Widevine CDM with third-party applications requires a license"; Alloy restored component-updater Widevine (2021) | CEF issues #1631, #3149 |

UNVERIFIED-live (404s at fetch time; NOT guessed — recorded in LG-3 as
open items for counsel): freshports Widevine page, Brave-wiki Widevine
page. Verdicts remain counsel's (LG-3).

## 3. Safe Browsing v5 (feeds LG-2, DR-15, F-015)

| Fact | Source |
|---|---|
| SB OHTTP Gateway API is built on IETF RFC 9458, V5 only (not V4) | developers.google.com/safe-browsing/ohttp/reference (page itself marked "documentation currently under development") |
| Clients may choose any relay provider (e.g. Fastly); the relay must use OAuth 2.0 with scope `https://www.googleapis.com/auth/3p-relay-safe-browsing`; all requests end-to-end encrypted so truncated URL hashes are not visible to the relay | same page |
| OHTTP public-key endpoint `GET https://safebrowsingohttpgateway.googleapis.com/v1/ohttp/hpkekeyconfig?key=<API key>`; Google provides client libraries and recommends Quiche | same page |
| SB terms: non-commercial use requires a separate agreement; attribution + conspicuous reliability/accuracy notice before first use and per warning; 30-minute freshness window (drives the Local-List operational constraint); SearchUrls submissions may be used/shared by Google | Safe Browsing Terms of Service (fetched; clauses quoted in LG-2) |

## 4. Dependency verification (feeds docs/dependencies/*, §8 INTEGRATE rows)

| Dependency | Verified 2026-09-07 |
|---|---|
| adblock-rust | MPL-2.0 (LICENSE file sha256 in §1); now under **brave** org (moved from adblock); uBlock Origin code itself is GPLv3 → REJECTED as linked code (DR-04) |
| EasyList family | EasyList is **GPL-3.0-or-later OR CC-BY-SA-3.0** (dual) — consumed data-only with LICENSE.data sidecars; EasyPrivacy/uAssets/Peter Lowe/AdGuard companion files verified; **Disconnect lists excluded** (CC BY-NC-SA 4.0) |
| keepass-rs | MIT; live version **0.13.25** (released 2026-08-30; plan said 0.13.6 — drift recorded); README: "experimental support for KDBX4.1 writing" (basis for DR-30 reader-yes/writer-no); crates.io `argon2` 0.6.0 license field **empty** → UNVERIFIED, re-verify at P28 before vendoring |
| Arti | Apache-2.0 OR MIT (main codebase); optional parts LGPLv3 — must be excluded/evaluated at P31 vendoring; "suitable for general client usage"; tag **arti-v2.6.0 dated 2026-09-01** |
| C-tor fallback dir | 3-clause BSD |
| wireguard-go | MIT; userspace wg per **RFC 8791** (WG over SOCKS/TLS patterns); (RFC 9458 is OHTTP — citation corrected in eval) |
| boringtun | **REJECTED-AS-DEFAULT**: org restructuring warning live-verified; freshports evidence 404 (UNVERIFIED-live); reconsideration triggers written in the eval |
| libsodium | ISC (not "BSD" as loosely phrased in places — convention drift recorded) |
| Lit | BSD-3-Clause (one pin = Chromium in-tree pin) |
| Inter, JetBrains Mono | OFL-1.1 (data); JetBrains Mono last push 2025-01-31 (stable) |
| helper tools | PyYAML 6.0.3 / pytest 9.0.3 (+ closure) MIT, hash-pinned (tools/DEPS.md) |

Fork-precedent research (context for LG-1, not a dependency):
Thorium (Alex313031, formerly Everdevs.io — org-move drift) builds on
the latest LTS Chromium; brave-core uses the patches/manifest model;
ungoogled-chromium does domain substitution; browsermt mirror-signing
is MIT-licensed.

## 5. Drift vs the pinned plan (recorded, plan NOT edited — see docs/process/plan-amendment.md)

| Item | Plan says | Live evidence (2026-09-07) | Where recorded |
|---|---|---|---|
| keepass-rs version | 0.13.6 | 0.13.25 (2026-08-30) | docs/dependencies/keepass-rs.yaml |
| adblock-rust org | adblock | brave | docs/dependencies/adblock-rust.yaml |
| Thorium org | Everdevs.io | Alex313031 | LG-1 research section |
| libsodium license phrasing | BSD | ISC | docs/dependencies/libsodium-rustcrypto.yaml |
| EasyList CC variant | BY-SA 4.0 | BY-SA 3.0-unported | docs/dependencies/easylist-family.yaml |
| registry row count | ~115±2 (working estimate) | **122** (§2.1–§2.9, counted line-by-line) | evidence/P1/registry-recount.md |

All are counting/version drift, not plan deviations: no plan passage
was changed, so no amendment or draft issue was required.

## 6. Dead ends (do not retry without reason)

- GitHub release JSON `commit_url` empty for actions/* → use
  `commits/<tag>` API for the action SHA pins (governance.yml).
- raw.githubusercontent 404s from wrong branch/filename (master vs
  main; OFL.txt vs LICENSE.txt variants) — verify branch first.
- gitlab.torproject.org raw/blob 403 → API v4 `files/:path/raw` works.
- freshports.org / Brave wiki Widevine pages → 404 (recorded §2).

## 7. Human-gated items (this log is NOT evidence for these)

- Counsel verdicts on LG-1/LG-2/LG-3 (briefs are DRAFT-FOR-COUNSEL;
  verdicts blank by design).
- GitHub CI execution (no remote yet — workflow committed; local runs
  in evidence/P1/ are the executed equivalent).
- Funding-gate evidence for DR-01 (HR/finance; HG-6).
- Any claim about runtime security properties: P1 ships governance
  only; the threat model v0 is explicitly pre-implementation.
