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
