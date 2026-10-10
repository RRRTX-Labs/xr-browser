# Papercut census — what identity-as-partition breaks, and who fixes it

**Pin:** `d04cdb24d67b081f6cf80200ffc5233f44b61109` · **Phase:** P4 ·
**Status:** census is a *static* analysis here (no compiled browser). Every
"repro" is written so the farm can execute it unchanged; every row therefore
has an owner and an estimate, because a census nobody can action is decoration.

**Lint:** `./scripts/build spike census-lint` — fails if any of the Plan's named
surfaces is missing, if a row lacks a field, if the owner is not in
{A,B,E,F,G}, or if the patch estimate does not parse. Negative-proven in
`tools/run_negatives.sh`.

Severity scale: **S1** = identity-breaking / data crosses identities ·
**S2** = user-visible regression · **S3** = cosmetic or rare.
Owner letters follow the Plan: **A** Platform/Chromium · **B** Browser UI ·
**E** Release/Build · **F** Security · **G** Product/UX.

| id | surface | what breaks | repro | severity | owner | patch estimate (files x category) | landing phase | attacker-observable cross-identity |
|----|---------|-------------|-------|----------|-------|-----------------------------------|---------------|-------------------------------------|
| C-01 | Downloads | The downloads DB is Profile-level (S-20/§1.4.5), so a download started in identity A is visible in identity B's shelf and history; the target directory is shared | `spike/probes/isolation_matrix_browsertest.cc` extended: download one file per identity to the same filename, assert the two do not collide and that neither shelf shows the other | S1 | B | 6 files x ui + 3 files x hook_points | P14 | Yes — filename + timestamp reveal that an identity downloaded something; see threat model TM-P4-1 |
| C-02 | Printing | The print preview is a `chrome://` WebUI in the *profile's* partition; printing identity A's tab can surface identity B's print settings and recent destinations | print from a tab in each identity; assert per-identity print settings and no shared destination MRU | S2 | B | 4 files x ui | P14 | Partial — the destination list is a weak activity signal |
| C-03 | DevTools attach | DevTools is a per-WebContents client but the target registry and `chrome://inspect` are browser-wide; an attached DevTools session can enumerate tabs across identities | open DevTools in identity A, list targets, assert identity B's tabs are not enumerable | S1 | F | 5 files x hook_points + 2 files x ui | P14 | Yes — tab titles and URLs across identities; TM-P4-2 |
| C-04 | Omnibox providers | History/keyword providers read Profile-level History (P-2), so typing in identity A autocompletes identity B's history | type a prefix visited only in B while in A; assert no completion | S1 | B | 8 files x ui + 2 files x hook_points | P14 | Yes — full history autocomplete leak; the single largest user-visible leak in this census |
| C-05 | Cross-identity drag-and-drop | Dragging a link or text between two identity tabs crosses a partition boundary; the drop is a same-profile operation so nothing blocks it | drag a URL from identity A's tab into identity B's tab; assert the drop is refused or re-keyed | S1 | B | 3 files x ui + 2 files x blink_seams | P14 | Yes — deliberate or accidental exfiltration of a URL/text into another identity |
| C-06 | Find-in-page | Find is per-WebContents and therefore correctly scoped, but the *search string* is held by the browser UI and pre-filled from the last find | find "foo" in A, switch to B, open find; assert the field is not pre-filled | S3 | B | 2 files x ui | P14 | Minor — a previous find string is a weak signal |
| C-07 | Picture-in-Picture | The PiP window is owned by the browser window, not the tab's partition; its document can outlive the identity tab | open PiP in A, close the tab, assert the PiP window closes and holds no A state | S2 | B | 3 files x ui | P14 | Yes — a surviving PiP window can keep rendering identity A content after the tab is gone |
| C-08 | Service-Worker notifications | The notification permission and the notification DB are Profile-level; a SW in identity A can display a notification whose click opens identity B | register a SW per identity, fire a notification, assert the click targets the originating identity's partition | S1 | A | 5 files x content_seams + 3 files x ui | P14 | Yes — notification content crosses identities outright |
| C-09 | `chrome://` pages | WebUI pages load in the profile's default partition, so a `chrome://settings` tab opened from identity A is not in A's partition | open `chrome://settings` from each identity; assert each resolves to its own partition or is explicitly declared out of scope | S2 | A | 6 files x hook_points | P14 | Partial — WebUI state is shared, but the page content is not user data |
| C-10 | Autofill UI | The autofill store is Profile-level (P-3); the suggestion popup in identity A offers identity B's saved addresses and cards | save a card in B, focus a form field in A, assert no cross-identity suggestion | S1 | B | 7 files x ui + 2 files x hook_points | P14 | Yes — saved card/address data is offered across identities |
| C-11 | Tab search + soft-reuse corner cases | Tab search indexes titles/URLs across identities (browser-wide), and process soft-reuse must never co-locate two identities even under memory pressure | open 50 tabs across 2 identities, run tab search, assert results are filtered to the active identity; assert process-internals shows no shared RPH | S1 | B | 6 files x ui + 4 files x content_seams | P14 | Yes — a global tab index is a complete cross-identity activity map |
| C-12 | Favicon cache | The favicon DB is Profile-level (P-6); fetching a favicon for `xr-a.example` in identity A populates a cache entry identity B's tab reads, and the *fetch itself* is a network request from the wrong identity | visit `xr-a.example` in A only, then load a page in B that references the same favicon; assert no shared cache hit and no network fetch attributable to B | S1 | A | 4 files x hook_points + 2 files x network_seams | P14 | Yes — cache-hit timing discloses whether another identity visited a site; TM-P4-3 |
| C-13 | Desktop drag (OS drag-out / drop-in) | Dragging an image or file out of an identity tab to the desktop writes to a shared filesystem location, and dropping a file in crosses into the partition | drag an image out of identity A to the desktop, then drop it into identity B; assert the written path is identity-scoped or the drop is refused | S2 | B | 3 files x ui | P14 | Yes — the desktop is a shared channel between identities |
| C-14 | Session restore | Session restore recreates tabs from a Profile-level session file; a restored identity tab must re-derive its partition, not fall back to the default | kill and restart with one tab per identity open; assert both restore into their own partitions (`XRIdentityTabData::PartitionMatchesLiveSiteInstance()`) | S1 | A | 5 files x hook_points | P14 | Yes — a restore that falls back to the default partition silently merges two identities |
| C-15 | Extension messaging | One extension registry per Profile (P-4); an extension's background page is in the default partition and can message tabs in any identity | install a test extension, open tabs in two identities, assert the extension cannot correlate them | S1 | F | 8 files x extension_chokepoint + 4 files x hook_points | P14 | Yes — extensions become a cross-identity oracle unless the chokepoint is enforced |

## Notes on method

* Every estimate is **files x budget category** so it can be summed against the
  §1.2 caps (total 150, `hook_points` 45, `content_seams` 30,
  `network_seams` 20, `ui` 35, `extension_chokepoint` 2).
* The census deliberately includes rows whose severity is S3: a papercut list
  that only contains S1s is a list someone edited to look decisive.
* Rows C-01, C-04, C-08, C-10, C-11, C-12 and C-15 are also threat-model rows
  (TM-P4-1..TM-P4-7) — the census and the threat model are the same facts seen
  from the maintainer's and the defender's side.

## P14 fix closure (added when the identity runtime landed — the honesty section)

The "landing phase" column above says every fix was *planned* for P14. What
P14 actually landed is the identity **runtime** (provisioning, binding,
hibernation, templates, attribution, session — xr-core `identity/`, pinned by
`DEPS.xr_core_rev`), which is the substrate these fifteen fixes plug into.
This section records, per row, what closed and what did not — a census whose
closure column says "fixed" fifteen times, with no compiled browser in the
tree, would be the dishonesty this repository bans.

Statuses (enforced by `census-lint`, negative-proven in `run_negatives.sh`):
**closed-core** = the removing law exists and is *proven* in the identity
core/suites; **matrix-covered** = the mechanism is exercised by a passing
isolation-matrix cell (fake mode — the model, not the build); **exception-
documented** = consciously not fixed, a §1.13 published-limitations row;
**open-browser** = not fixed in P14, and the row names the method that will
prove it when the browser build exists (a NOT-RUN row must carry its method).

| id | P14 outcome | status | closing artifact (verified to exist) | the browser half (method when it runs) |
|----|-------------|--------|--------------------------------------|----------------------------------------|
| C-01 | Downloads shelf/history stay Profile-level; the identity-scoped `downloads-metadata` mechanism is specified but not executed | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `downloads-metadata`, mode browser, NOT-RUN) | spike/probes/isolation_matrix_browsertest.cc — one download per identity, assert no shelf/history crossover |
| C-02 | Print settings/destination MRU stay shared; `print` cell specified, not executed | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `print`, mode browser, NOT-RUN) | per-identity print from the probe matrix; assert per-identity destinations |
| C-03 | `chrome://inspect` still enumerates across identities; `devtools-attach` cell specified, not executed | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `devtools-attach`, mode browser, NOT-RUN) | attach in A, list targets, assert B's tabs are not enumerable |
| C-04 | Omnibox providers still read Profile-level history; `omnibox` cell specified, not executed. The ledger overlay half landed in P14-CLOSE C-2: every omnibox row carries `identity_id`, and a planted cross-identity omnibox leak reddens | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `omnibox`, mode browser, NOT-RUN) | type a B-only prefix in A, assert no completion |
| C-05 | Cross-identity drag is unblocked in the model; `drag-across-identity` cell specified, not executed | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `drag-across-identity`, mode browser, NOT-RUN) | drag URL A→B, assert refused or re-keyed |
| C-06 | Find pre-fill is a UI string; no mechanism landed | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough method) | find "foo" in A, switch to B, assert the field is not pre-filled |
| C-07 | PiP ownership unchanged; no mechanism landed | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough method) | PiP in A, close the tab, assert the window closes with it |
| C-08 | Notification permission/DB stay Profile-level; `serviceworker` + `notification-state` cells specified, not executed | open-browser | ../xr-core/test/isolation/matrix.yaml (cells `serviceworker`, `notification-state`, mode browser, NOT-RUN) | SW per identity, fire a notification, assert the click targets the originating partition |
| C-09 | `chrome://` pages still load in the default partition; no matrix cell yet | open-browser | docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md (§1.13 published limitations — WebUI partitioning) | open `chrome://settings` per identity, assert own partition or the §1.13 row is the disclosure |
| C-10 | Autofill store stays Profile-level; no matrix cell yet | open-browser | docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md (§1.13 published limitations — autofill) | save a card in B, focus a field in A, assert no cross suggestion |
| C-11 | Soft-reuse half: the `process-isolation` cell PASSES in fake mode (never co-located); tab-search half not executed | matrix-covered | ../xr-core/test/isolation/matrix.yaml (cell `process-isolation`, mode fake, PASS) | tab search across 50 tabs / 2 identities, assert filtered results + no shared RPH |
| C-12 | Shared favicon cache consciously NOT fixed — a timing side channel that survives partitioning | exception-documented | ../xr-core/test/isolation/matrix.yaml (cell `favicon-cache`, mode exception) + docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md §1.13 | disclosed, not proven; revisit only with per-identity favicon storage (owner A, post-P14) |
| C-13 | OS-level drag-out writes to the shared desktop; no mechanism landed | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough method) | drag out of A to the desktop, drop into B, assert identity-scoped path or refusal |
| C-14 | The session store carries each tab's recorded binding; restore REFUSES (kMalformedInput, tab named) rather than fall back to the default partition — proven by 345-check seeded chaos suite + the `session-restore-no-bleed` matrix cell (PASS, all 5 pairs) | closed-core | ../xr-core/identity/core/session.h + ../xr-core/identity/tests/test_session_chaos.cc | kill -9 / restore drill on the real browser (docs/qa/drill.md, NOT-RUN this phase) |
| C-15 | Extension registry stays per-Profile; the chokepoint cannot land before extensions exist | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `extension-availability`, mode not-yet, phase P13) | install a test extension, assert it cannot correlate two identities' tabs |

## P14-CLOSE ledger — status, test, owner, budget for every row (zero silent)

The closure table above says what P14 closed. This ledger makes each row
actionable: the **test** that proves it (here, or on the browser build), the
**owner** letter and the **budget** reservation (both copied from the census
row, and checked equal to it), and whether the test **ran here**. A row
cannot be silent: `census-lint` (build/spike/census_lint.py) fails when a
census id has no ledger row, when a status differs from the closure table,
when an owner or budget differs from the census row, when a test cell cites
no path that exists, when a closed-core or matrix-covered row has no
`yes: <log>` transcript, or when an open-browser row has no
`NOT-RUN: <method>` path (negatives: tools/negatives/p14c_c5.sh). Paths
starting `../xr-core/` resolve in the pinned sibling.

| id | status | test (what proves it) | owner | budget (files x category) | run here |
|----|--------|-----------------------|-------|---------------------------|----------|
| C-01 | open-browser | ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cell `downloads-metadata`) | B | 6 files x ui + 3 files x hook_points | NOT-RUN: docs/qa/browser-harness.md |
| C-02 | open-browser | ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cell `print`) | B | 4 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-03 | open-browser | ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cell `devtools-attach`) | F | 5 files x hook_points + 2 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-04 | open-browser | ../xr-core/identity/tests/test_ledger_tag.cc (overlay half: an omnibox row tagged with identity B never surfaces in A; the planted leak reddens) + ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cell `omnibox`, provider half) | B | 8 files x ui + 2 files x hook_points | yes: evidence/P14/logs/c2-ledger-identity.txt (overlay half); NOT-RUN: docs/qa/browser-harness.md (provider half) |
| C-05 | open-browser | ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cell `drag-across-identity`) | B | 3 files x ui + 2 files x blink_seams | NOT-RUN: docs/qa/browser-harness.md |
| C-06 | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough: find pre-fill) | B | 2 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-07 | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough: PiP closes with its tab) | B | 3 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-08 | open-browser | ../xr-core/spike/identity_seam/probes/isolation_matrix_browsertest.cc (cells `serviceworker`, `notification-state`) | A | 5 files x content_seams + 3 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-09 | open-browser | docs/qa/browser-harness.md (`chrome://settings` opened per identity) | A | 6 files x hook_points | NOT-RUN: docs/qa/browser-harness.md |
| C-10 | open-browser | docs/qa/browser-harness.md (a card saved in B is never suggested in A) | B | 7 files x ui + 2 files x hook_points | NOT-RUN: docs/qa/browser-harness.md |
| C-11 | matrix-covered | tools/isolation_matrix.py (cell `process-isolation`, 5 of 5 pairs; soft-reuse half) | B | 6 files x ui + 4 files x content_seams | yes: evidence/P14/logs/t5-t6-isolation-matrix.txt; NOT-RUN: docs/qa/browser-harness.md (tab-search half) |
| C-12 | exception-documented | tools/exception_ledger_check.py (the `favicon-cache` exception cell must carry its §1.13 row in docs/limitations.md) | A | 4 files x hook_points + 2 files x network_seams | NOT-RUN: docs/qa/browser-harness.md (the timing measurement) |
| C-13 | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough: OS drag-out / drop-in) | B | 3 files x ui | NOT-RUN: docs/qa/browser-harness.md |
| C-14 | closed-core | ../xr-core/identity/tests/test_session_chaos.cc (seeded chaos: restore re-binds the recorded identity or refuses, never the default) | A | 5 files x hook_points | yes: evidence/P14/logs/t8-identity-suite.txt; NOT-RUN: docs/qa/drill.md (real kill -9) |
| C-15 | open-browser | ../xr-core/test/isolation/matrix.yaml (cell `extension-availability`, mode not-yet) | F | 8 files x extension_chokepoint + 4 files x hook_points | NOT-RUN: docs/qa/browser-harness.md |

**Budget, summed honestly.** The fifteen reservations total 99 upstream
files: ui 47, hook_points 31, content_seams 9, extension_chokepoint 8,
blink_seams 2, network_seams 2. Against the §1.2 caps (ui 35,
extension_chokepoint 2), the ui and extension_chokepoint reservations do
NOT fit as estimated. That is a planning fact for the phases that land the
browser halves, not something this ledger can fix: those estimates must be
cut, shared, or the cap raised by the budget process
(build/farm/budget_meter.py measures what actually lands). Nothing in this
ledger has been spent: P14-CLOSE landed no upstream patch files.
