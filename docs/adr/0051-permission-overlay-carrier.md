# ADR-0051: Permission overlay carrier and capability envelope

- **Status:** DRAFT (PROPOSED by the P15 coding agent; NOT approved. Ratification is a human act under HG-35; `ratified:` is never written by this phase.)
- **Date:** 2026-10-09
- **Deciders (humans):** Platform lead + Privacy lead (the overlay decides what a site may do for a given identity, and the audit row it leaves is user-visible).
- **Plan anchor:** §4 P15 (T0 to T10); the Permission Firewall v1 brief (`PHASE-P15.md`, §2 and §4 lines 799 to 815).

## Context

P15 needs per-identity permission state (per-identity defaults, temporary grants, a Fortress deny-list) without touching the frozen contracts. The frozen surface is narrow:

- `PermissionPolicy` (mojom `policy_resolver.mojom`) has exactly four fields: geolocation, camera, microphone, notifications. Each is a `PermissionState` of kDeny, kAsk or kAllow.
- `ActivityRow` (mojom `activity_log.mojom`) has no capability, origin or expiry fields.
- The 66 frozen resolver vectors (`policy-resolver-v1.json`) pin the resolver's output byte-for-byte. Their pin is `8d35c4c3…`, and `FROZEN.yaml` is pinned at `0b79e439…`.

Two facts make the design non-trivial. First, the resolver's parser drops an invalid layer entry and keeps the rest. For an overlay, a dropped *allow-narrowing* entry widens the answer. Second, a store that is repaired by an empty write silently reverts every identity to the tier table, which is itself a widening.

## Decision

1. **Carrier R2: the overlay is resolver input data.** `ResolveRequest` gains one field, `permission_overlay`, consulted in `resolve.cc` after the tier defaults and every other layer. It is the last word on the four frozen fields. The overlay never adds a field to the frozen ledger shape and never adds `identity_id` to it.
   - **Absent** means inert: the tier table decides. This is the parity proof, since the 66 frozen vectors carry no overlay.
   - **Present but malformed, or explicit `null`,** means CORRUPT. The whole overlay is fail-closed and all four permissions deny for every identity. A malformed overlay is never partially applied.
   - Order inside the overlay: corrupt, then the Fortress deny-list (FINAL, nothing after it can widen), then per-identity defaults (override the tier), then active temporary grants (widen only the matching identity AND registrable domain).
2. **Envelope (i): the carrier can only name the frozen four.** A capability with a `PermissionState` slot is widenable by the overlay. Any other capability has no output slot, so it cannot be represented as an answer.
3. **Envelope (ii): extras are deny-only data.** The four extras (clipboard-read-write, sensors, midi, pics) can be recorded as kDeny or kAsk only. A record that claims kAllow for an extra is refused at parse time, which makes the record corrupt. An extra can only narrow upstream's answer, and `NarrowExtra` is proven monotone over all nine state pairs.
4. **Store integrity: corrupt means deny, and corruption persists.** A stored document is accepted only if its bytes are exactly the canonical serialization of what they parse to, and it satisfies a strict schema. The canonical round-trip rejects duplicate keys, which the shared parser otherwise resolves keep-last. A corrupt store serializes to a marker that is itself corrupt on reload, so no save path can erase the deny. Only an explicit reset clears it.
5. **Time is an input.** Every operation takes `now_ms`. The 7d scope is active only while `expires_at > now` (fail-closed at equality, matching `ExceptionActive`). A session grant is active only while its `session_id` matches the request's. A once grant is active only while `remaining_uses > 0`. Evaluation uses `EffectiveNow(last_seen, observed) = max(...)`, so time never runs backward and a backward clock jump cannot un-expire a grant.
6. **The Fortress deny-list is host data.** The host writes `denied_identities` from the identity grade. The resolver never derives it from grade, and nothing in the resolver or permissions core can widen it. Fortress identities therefore never prompt for the frozen four.
7. **Revocation is tombstoned and never widens.** Revoke-site and revoke-all leave tombstones, so a stale copy cannot revive a grant. Revoke-all clears grants and per-capability defaults. It deliberately leaves the host-owned deny-list and the deny-only extras untouched, so it can never widen an identity beyond upstream.
8. **The audit contract is `permission-audit-event-v1` (post-freeze, LIVING).** One row is emitted per real mutation, and none for a no-op. Rows carry a `deciding_layer` label: after a grant or revoke, the overlay decides, and after an expiry, the global fallback decides (unless the identity still has its own default). The origin is a bare registrable domain or the empty string for identity-wide rows. A full origin is refused, never truncated. The frozen `ActivityRow` is reused for the activity feed (kind = kPermission), so no frozen byte changes.
9. **Attention (T7).** A permission prompt is an anchored T3 prompt. It is capped at 3 per hour from a local counter, and over the cap it demotes one tier to T2 and is logged. A second prompt while one is pending is demoted and logged, so prompts are never stacked.
10. **Write path (T9.2).** The overlay is mutated only by `xr-core/permissions/core/ops.cc`. Any call to a mutator from product source outside `permissions/` is a second write path, and the static lint treats it as RED.

## Alternatives considered

- **R1, a new mojom field on `PermissionPolicy`.** Rejected for P15. It edits a frozen file, which the brief forbids, and it requires a contract amendment. The widening itself (four `[MinVersion=1]` slots for the extras, needed by P35 and P21) is drafted as `docs/rfcs/RFC-0002.md` (DRAFT, human gate HG-P15-RFC2); envelope (ii) stays the law until a human approves it.
- **R3, a separate permission service that the resolver consults over IPC.** Rejected. It creates a second decision point and a second brain, and it brings no benefit that the pure in-process input does not already give.
- **Per-entry drop for malformed overlay records (the other layers' behaviour).** Rejected. A dropped allow-narrowing entry widens the answer, so the failure mode is the wrong way round.
- **Trusting the parser's duplicate-key behaviour.** Rejected. The shared parser keeps the last duplicate, so the store relies on the canonical round-trip instead.

## Consequences

- The 66 frozen vectors are byte-identical and their expectations are unchanged. The new overlay vectors are an additive file (`permission-overlay-v1.json`, 33 vectors).
- The overlay is a new input on the resolver request. Any future host must send it or omit it, and a malformed value denies.
- Tests and the bench are reproducible off-tree (g++ and make, as in `policy/tests`). The C++ suite is discovered by `ci_lane_discovery` and recorded in `docs/state/ci-lanes.json`.

## Does NOT prove

- **Authenticity of the store.** A local writer with profile access can write a canonical, schema-valid document. The store defends against corruption and partial writes, not against a hostile local writer.
- **Delivery and UI.** The Panel surface, the one-time patch half of T2, the settings section (T8), live propagation to open tabs, and the browser runtime are not built in this phase. They are NOT-RUN or deferred, with reasons in the research log.
- **Localization.** The `ActivityRow.summary` text is an English default. The strings go through the l10n pipeline when the UI half lands.
- **Reference-hardware performance.** The bench numbers are measured on one shared host and are labelled as such (HG-28).

## Register

`docs/register/decisions.yaml` is NOT edited. `tools/dr_parse.py` fixes the register at `DR-01..DR-30` (`EXPECTED_IDS`), so a P15 row cannot be appended without changing the validator. This is a human decision: either extend the register's id set by a separate ADR, or record P15's decisions here as the authority. It is listed in the phase's human gates.

## Addendum 2026-10-10 (P15-CLOSE; still DRAFT)

Dated decisions taken while closing P15. Each is a claim for human review like the rest of this record; none is ratified.

- **C5, the settings section: a new section, and `privacy.notifications` stays where it is.** `xr://settings/permissions` is section `permissions` in `xr-core/settings/core/settings_schema_v1.json`: order 10 (spaced after 1, 2, 3, following `ui/panel/tabs.json`'s reserved orders), availability `always`, no schema rows in v0. Moving `privacy.notifications` would be a settings-schema migration: it breaks the fakes, the search index, the grdp counts and P13's deep links, so it is not done. The command is `settings.permissions`; the coverage-allowlist row has `unit: section`; the help deep link holds in both directions. Search words are data, not code: `settings-search.ts` holds no term list (results are ranked by the C++ core), so the words are the section's new search-only `aliases` field (permission, site permissions, camera, microphone, location, geolocation, clipboard), parsed strictly and indexed identically by `settings_schema.cc`/`search.cc` and `fakes/settings.py`. "notifications" is deliberately not an alias: it keeps landing on `privacy.notifications`, an existing search law. The section adds no enum value, so `shield_state_check` gains no state.
- **C6, the keyboard task: option (a).** The prompt-focus tasks live in `docs/qa/keyboard-tasks-permissions.yaml` with their own law (`tools/keyboard_tasks_permissions_check.py`: one task per core capability, derived, no count literal; focus lands on the first button; one-time first when sensitive; the scope-copy key present) and their own negatives (`tools/negatives/p15c_c6.sh`). The plan §11.6 12-task law is untouched. `permissions/tests/test_present.cc` reads the file and asserts every row equals the core.
- **C7, the patch half: a patch, because there is no public API.** Upstream builds the prompt's buttons inside a private method, `PermissionPromptBubbleBaseView::CreatePermissionButtons`, and stacks "Allow while visiting" above "Allow this time" in its one-time branch. No delegate or public call can reorder them, so a component cannot do it. Patch `0400-permission-prompt-order` is one file under `chrome/browser/ui/views/permissions/`, order only, and guarded by `ENABLE_XR_PERMISSIONS`. `build/webui/permission_patch_roundtrip.py` regenerates it from the pinned bytes, byte-compares it with the committed patch, and refuses added lines that are new code. Upstream offers one-time grants for geolocation, camera and microphone, which is exactly the core's sensitive set. Notifications use the OK/Cancel dialog buttons, which the platform orders; they are **not** patched. The core's deny-first order for notifications therefore stays a UX review item (HG-P15-UX). The `ui` budget goes from 9 to 10 of 35, regenerated by `build/farm/budget_meter.py`.
- **C9, the Activity surface: option (b).** Neither repo has an Activity tab in code; P13's Activity surface is interim and has no file to render into. The audit core still emits `kind: kPermission` ActivityRow JSON (`permissions/core/audit.cc`). Rendering is NOT-RUN (method: `docs/qa/browser-harness.md#p15-activity-rows`) and human gate HG-P15-ACTIVITY-SURFACE is open. No tab was invented.

## Status of this record

This ADR is a DRAFT. It is not approved, and nothing in the phase writes a `ratified:` key. Each decision above is a claim for human review, backed by the tests named in the research log.
