# PHASE 1 RELEASE — XR Browser (RRRTX Labs)

- **Phase:** P1 — Governance, legal gates, repository skeleton (Plan Stage 0)
- **Release prep date:** 2026-09-07
- **Brand:** RRRTX Labs (official; see §4 fix F1)
- **Target GitHub home:** `github.com/RRRTX-Labs/xr-browser`, `github.com/RRRTX-Labs/xr-core`
  (organization exists; repos created + pushed per human gate HG-3)
- **Packages:** `xr-browser-phase1.zip`, `xr-core-phase1.zip` (§6)

---

## 1. Final repo state

| | xr-browser (meta) | xr-core (product) |
|---|---|---|
| Branch | `main` | `main` |
| Commits at packaging | 18 (16 listed in §2 + this file's commit + the final fixup commit) | 3 (all listed in §2) |
| License | MPL-2.0 (canonical verbatim, sha256 `3f3d9e00…9b9d04`) | same file, same hash |
| Working tree | clean (`git status` empty) | clean |
| Untracked/temp files | none | none |
| Contents | plan (pinned v2), register, registry, ADRs, legal briefs, 12 dependency evals, threat model v0, limitations, 9 governance tools + 55 tests + negative corpus, CI definition, evidence bundle, README/CONTRIBUTING/PR+issue templates, ci/ README | LICENSE, README, CONTRIBUTING, OWNERS (Chromium-style), CODEOWNERS, .clang-format, .gitignore |
| Secrets/credentials | **none** — only RFC 2606 placeholder identities (`@rrrtx.example`, `@xr/*`), documented as such in human gates HG-2/HG-3 | same |
| Scope boundary | governance/docs/tooling/CI only — **no GN, no DEPS, no patches, no product source** (P2+ not stubbed) | same |

**Pinned plan (v2):** `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md`
- sha256: `02743146146fa139cd53b15216aaa26b79f9d9307998b1814019d27406265a7b` (298,077 B)
- v1 digest (superseded): `a74b2aa4e8fd6f427c71cadfe932489249afe208a10413bf78c04734fd343e1b`
- v1→v2 = exactly one token (line 3 brand), recorded in ADR-0003

**Key counts (machine-verified):** feature registry 122 rows (100 active / 3 deferred / 19 dropped) + 6 reserved interfaces (P5 freeze); decision register DR-01..DR-30 (26 RATIFIED, 2 OPEN, 1 GATE-PENDING, 1 MONITORED); 12 dependency evals; 3 ADRs (+ template, RESERVED 0042); 8 human gates.

## 2. Exact commit hashes

**xr-browser** (oldest → newest):

| # | SHA | Subject |
|---|---|---|
| 1 | `3e78f06c85ae4518b2a151d9d459f481cc6c3117` | initialize xr-browser meta-repo (XR-P1-T1) |
| 2 | `7d40c2dac3030a48e787416b53964e205c375a82` | ADR system with reserved numbering (XR-P1-T2) |
| 3 | `bebb7dc3e3d94f09bd79a9f58002ee72e1d3fc13` | SECURITY.md, disclosure policy, bounty draft, intake drill (XR-P1-T3) |
| 4 | `370f3cb7302577bd806920cc9c06325ba8b6679a` | threat model v0 + published limitations (XR-P1-T4) |
| 5 | `966191ab8b64e2352a117d72229ebebd38bbdcf7` | LG-1..LG-3 counsel briefs, DRAFT-FOR-COUNSEL (XR-P1-T5) |
| 6 | `dc91649686bfe37454c4856f67608b9887e6bec1` | funding gate DR-01 + open assumptions (XR-P1-T6) |
| 7 | `ac30eaeb87de1f809a3bf71391f07cd82d058c0d` | S0 CODEOWNERS + owners sync tool (XR-P1-T7) |
| 8 | `3989cfafcbeabe1c1882638e121ae309721d703f` | L9 evaluation pack for §8 INTEGRATE rows (XR-P1-T8) |
| 9 | `48f2c1cbfa560a3fe8165de820e3439a78ead2f7` | decision register linter + trailer check (XR-P1-T9) |
| 10 | `30730c6340affc2dcf3b23bd622a85e1a6328057` | feature registry derived from pinned plan (XR-P1-T10) |
| 11 | `6644a96994ae88903ece5ddfdcfb59d6e925b5ac` | master plan pinned in-tree by SHA-256 (XR-P1-T11) |
| 12 | `bc56a9ba782147b116c7a0a4add6f223a5f95b16` | banned-claims vocabulary lint + allowlist (XR-P1-T12) |
| 13 | `f7178bff6bcc9703286ad3e7c1354d7501debf5d` | security gate tools, CI definition, hash-pinned dev deps (XR-P1-T13) |
| 14 | `aa7a39934fb80fa363d6a1978271b9041fd620c5` | P1 evidence bundle + final repo docs (XR-P1-T14) |
| 15 | `2aada3652fcd91df85ea29f2da341794dfa0ac48` | final evidence capture + repo-map/README/CONTRIBUTING updates (XR-P1-T14) |
| 16 | `885d13191367e8940a632114f6a298faf91a8fb1` | brand correction to RRRTX Labs + plan v2 re-pin (release prep) |
| 17 | *(commit adding this file)* | PHASE1_RELEASE.md (release prep) |
| 18 | *(final commit — HEAD at packaging; `git log -1` inside the ZIP)* | release doc fixup: old-brand string kept out of the release note (audit trail stays in ADR-0003) |

**xr-core** (oldest → newest):

| # | SHA | Subject |
|---|---|---|
| 1 | `0050c5300c081972d93f305370ee5ba47ef69955` | initialize xr-core product repo (XR-P1-T1) |
| 2 | `22922d85ede6a2a706ebd0e815f36d2ddeb6171a` | OWNERS/CODEOWNERS for S0 paths (XR-P1-T7) |
| 3 | `6fb5411bab4d95800a3e56848cecb3013f9bd33f` | fix placeholder-domain comment in OWNERS (XR-P1-T7) |

All commits carry DCO `Signed-off-by` (verified by `dco_check.py` over full history); register-touching commits carry `Register-Change: ADR-<nnnn>` trailers (verified by `dr_parse.py --check-trailers`).

## 3. Verification results (all executed 2026-09-07)

**Gate suite** (`tools/run_checks.sh`, both in-repo and inside the extracted ZIP):

| Gate | Result |
|---|---|
| `plan_pin_check` (plan == v2 pin) | PASS |
| `registry_lint` (122 rows == plan §2 parse; 6 reserved; COUNTS) | PASS |
| `dr_parse` (30 DR rows, schema, statuses) | PASS |
| `dr_parse --check-trailers` (full history) | PASS |
| `license_audit` (canonical MPL-2.0 ×2 repos; 0 code hits; 16/16 doc citations allowlisted) | PASS |
| `dco_check` (full history, both repos) | PASS |
| `check_threat_model` (plan-SHA binding, T1–T11 honesty, 14 invariants, T8/T9 out-of-scope) | PASS |
| `vocab_lint` (0 unallowlisted hits; 38 justified entries) | PASS |
| `owners_sync --check` (CODEOWNERS/OWNERS ↔ s0-paths) | PASS |
| test suites | **55/55 passed** |

**Negative proofs** (`tools/run_negatives.sh`): 7/7 rejected with expected reason —
injected GPL sample in code; unsigned commit; hand-edited registry; banned vocab
in new doc; bad register enum; emptied threat-model honesty cell; tampered plan copy.

**Report-claim cross-check** (independent script vs the P1 final report):
plan pin cascade (5 anchors), registry 122 rows + status split, reserved 6,
register 30 rows + status split, threat-model SHA, 12 evals, MPL-2.0 hashes —
**all verified**; one report inaccuracy found and corrected here: register
statuses are **26** RATIFIED (the report's "27" was an arithmetic slip;
26+2 OPEN+1 GATE-PENDING+1 MONITORED = 30).

**Brand scan** (case-insensitive grep for the old brand string, both
repos, excl. `.git`): **0 branding occurrences remain.** The old string
survives *only* inside the amendment's own audit trail — ADR-0003
(title/body), research-log §8, and `evidence.json`
`plan_repin.change` — where a record of the correction must quote the old
token by design; removing it there would falsify the audit trail. Every
other file, including this release note, is free of it.

**ZIP reproducibility:** both ZIPs extracted to a clean directory; git
history intact (`git log`, `git status` clean); the extracted xr-browser
re-ran the complete gate suite green (55/55 + 7/7 negatives).

## 4. Important fixes in this pass

| # | Fix |
|---|---|
| F1 | **Brand correction:** the stale old company name (still used on plan v1 line 3 while line 8 of the same file already used the official brand) was corrected to **RRRTX Labs** everywhere it appears as project branding: README, SECURITY.md title, and the plan (via v2). Plan v1 was internally inconsistent about the brand; v2 resolves it. Executed per the amendment path as **plan v2** (one token; no lines added/removed, so all line-number anchors stayed valid) with a full re-pin in one commit — **ADR-0003** records both digests and the exact token. |
| F2 | SECURITY.md + human-gates HG-3 now reference the real organization `github.com/RRRTX-Labs` (status still PENDING-OPS: repos not yet pushed, GHSA not yet enabled). |
| F3 | Removed `tools/tests/__pycache__` build junk (was gitignored, removed from disk). |
| F4 | Corrected register-status count in the release record (26 RATIFIED, see §3). |
| — | Deliberately **not** changed: `/home/user/uploads/` original spec (read-only source), `rrrtx.example` RFC 2606 placeholder identities (HG-2/HG-3), git commit author metadata (immutable history), owner IDs `RRRTX-*` (role prefixes), third-party copyright/license attributions. |

## 5. Known limitations & human gates

**Phase verdict (unchanged from P1 close):** 10 of 12 DoD rows VERIFIED with
executed evidence; 2 rows HUMAN-GATED by the plan's own design. No agent-scope
item open. No Phase 2 work started or stubbed.

| Gate | What must happen | Owner (placeholder) |
|---|---|---|
| HG-1 | Counsel verdicts LG-1/LG-2/LG-3 → DR-14/DR-15 ratified | RRRTX-LEGAL-01 |
| HG-2 | `security@rrrtx.example` mailbox + DNS live | RRRTX-OPS-01 |
| HG-3 | Push both repos to `RRRTX-Labs`, branch protection on `main`, real CODEOWNERS handles | RRRTX-OPS-02 |
| HG-4 | Enable GHSA on both repos | RRRTX-OPS-02 |
| HG-5 | Domain/trademark filings | RRRTX-LEGAL-02 |
| HG-6 | Funding confirmation (DR-01; §15-R17 fallback trigger recorded) | RRRTX-PRINCIPALS |
| HG-7 | Human re-read of ADRs 0001/0002/0003 + register transcription | RRRTX-PLATFORM-LEAD |
| HG-8 | Live intake-drill re-run after hosting | RRRTX-G-LEAD |

**UNVERIFIED items (recorded, never guessed):** argon2 0.6.0 license field
empty (re-verify P28 before vendoring); Widevine per-platform details
(freshports/Brave-wiki 404s — LG-3 open item for counsel); browsermt
mirror-signing license (raw fetch 404'd — re-verify before P34).

**Governance-only scope:** the threat model is explicitly pre-implementation;
every protection stated in it is target posture, not shipped functionality.

## 6. Packages & verification commands

| Package | Contents |
|---|---|
| `xr-browser-phase1.zip` | complete `xr-browser` repository at the release HEAD, **including `.git`** (full history + DCO signoffs), no untracked files |
| `xr-core-phase1.zip` | complete `xr-core` repository at `6fb5411…`, including `.git`, no untracked files |

Verified procedure (reproducible on any machine with git + Python 3.12 +
`pip install --require-hashes -r tools/requirements-dev.txt`):

```sh
# unpack
unzip xr-browser-phase1.zip
unzip xr-core-phase1.zip

# integrity: history + clean trees
git -C xr-browser log --oneline -3          # top = 885d131… (brand/re-pin)
git -C xr-core    log --oneline -3          # top = 6fb5411… (OWNERS fixup)
git -C xr-browser status --short            # (empty)
git -C xr-core    status --short            # (empty)

# full governance gate in the extracted meta repo
cd xr-browser
pip install --require-hashes -r tools/requirements-dev.txt
tools/run_checks.sh          # 8 gates + 55 tests — expect "ALL GOVERNANCE CHECKS PASSED"
tools/run_negatives.sh       # expect "ALL NEGATIVE CASES REJECTED AS EXPECTED"
python3 -m pytest tools/tests/ -q   # 55 passed
```

**Result on the released ZIPs (2026-09-07):** all of the above passed in a
clean extraction (see §3 "ZIP reproducibility").
