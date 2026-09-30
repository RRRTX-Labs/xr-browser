# panel-tab-registration-v1

**Status:** LIVING (born P13; registered post-freeze in
`docs/contracts/registry-post-freeze.md`; `FROZEN.yaml` bytes untouched, its 14
rows still `PENDING` under HG-26). Ratification is a human act (HG-35).
**Schema:** `docs/contracts/panel-tab-registration-v1.schema.json`
**Vectors:** `docs/contracts/vectors/panel-tab-registration-v1.json`
**Runtime:** `xr-core/ui/panel/tab-registry.ts` (+ `ui/panel/tests/tab-registry.test.mjs`)
**Inventory:** `xr-core/ui/panel/tabs.json`
**Gates:** `tools/panel_registry_check.py` (this contract),
`tools/coverage_check.py` (§10's bijection + roster half)

## The decision

A panel tab is a **declared** thing, not a `.ts` file that happens to live under
`ui/panel/`. That sentence is the whole contract, and it is what makes §10's
check — "every Settings section and panel tab maps to a command" — have a
legitimate unit: a file cannot be mapped to a command, a declaration can.

The alternative was measured and rejected. Before P13 the §10 lane treated any
`ui/panel/*.ts` as a surface, so `focus-trap.ts` and `panel-frame.ts` — the
frame's containment and chrome, not tabs at all — read as unaccounted features,
and the honest fixes available were all bad: exempt the directory (weakening the
law), invent a command or a tab (a fake), or widen the check (a third
weakening). The contract replaces the exemption with a declaration.

## The shape

```json
{ "id": "site", "title_msgid": "panel.tab.site", "order": 10,
  "requires_identity_scope": true }
```

`additionalProperties: false` — a registration carries these four fields and
nothing else. No copy (a title is a msgid; prose here would be untranslatable and
absent from `l10n_extract`'s view), no render callback, no route, no capability list.

## Laws

1. **Additive-only.** A subsystem adds a tab by registering it; there is no
   `unregister`. Removing a tab from the inventory is a contract change, not a
   runtime call — a tab that disappears because a later edit renumbered things is
   the silent-disappearance class this repo keeps paying for.
2. **Order is first-class and spaced by 10** (10/20/30/…, reserved band 10–990).
   Two tabs claiming one `order` is a validation failure (`order-collision`,
   `duplicate-order`), resolved by editing the inventory — never by a tie-breaker
   in the renderer. Spacing means a later subsystem inserts between two tabs
   without renumbering, because renumbering breaks every bookmarked deep link.
3. **The inventory owns the order.** A registration whose `order` disagrees with
   the declared one is refused (`order-mismatch`), not silently re-ordered: a
   subsystem that renumbers itself reshuffles every user's tab strip.
4. **Unknown ids are REFUSED with a typed error** (`unknown-tab-id`), never
   dropped. A dropped tab is indistinguishable from a tab a user never opened.
5. **`title_msgid` must exist in the message table.** `tools/panel_registry_check.py`
   asserts every declared id's msgid is in `xr-core/l10n/xr_strings.grdp`; a
   missing one renders the raw id — a machine token shown to a user.
6. **The §10 claim.** Every declared tab's allowlist entry
   (`docs/contracts/coverage-allowlist.yaml`, `unit: tab`, `target: <id>`) claims
   at least one `sources:` file, and the entry's `command` is a real command
   (`coverage_check` R1). A declared tab with no implementation is a placeholder,
   and a placeholder that passes a gate is how a phase reports a tab it never
   built. `skip:` is not a claim; `tools/negatives/p13_c5.sh` proves it.
7. **The BYPASS law.** `ui/panel/panel-frame.ts` and `ui/panel/tab-strip.ts` may
   know the *registry*, never the *tabs*: no declared tab id may appear as a
   quoted literal in either file. A frame that names a tab has stopped being
   registry-driven, and every later tab it fails to mention disappears without an
   error. Registered negative: `tools/negatives/p13_c5.sh` case 1.
8. **Strings are msgids; diagnostics are machine tokens.** The registry renders
   no text and owns no copy, and its refusal `detail` values are tokens
   (`duplicate-order:<owner>:<id>`), because `l10n_extract`'s R4 rule forbids
   space-bearing literals anywhere under `ui/**` — they are indistinguishable
   from user-visible copy at rest.

## Semantic vs structural refusals

The schema owns the **structural** half (types, required fields, extra fields);
the runtime owns the **semantic** half (unknown id, order collision, order
mismatch, duplicate id), because judging those needs the inventory. Both halves
are proven, and neither pretends to cover the other:

| Refusal | Owner | Where it is proven |
|---|---|---|
| extra field / missing field / wrong type | `panel-tab-registration-v1.schema.json` | vectors + `tools/tests/test_p13_c5_panel_registry.py` |
| `unknown-tab-id`, `order-collision`, `order-mismatch`, `order-out-of-range`, `duplicate-id`, `duplicate-order`, `bad-shape` | `tab-registry.ts` | `ui/panel/tests/tab-registry.test.mjs` (node) |

## What this does not claim

No rendered result. The panel's DOM half is `tsc --strict` plus the node suites;
open latency (≤150 ms) and ring scroll (≤16 fps) are `NOT-RUN` with methods in
`docs/qa/browser-harness.md`, because there is no browser in this environment
(HG-31).
