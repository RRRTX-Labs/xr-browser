# WebUI end-to-end (P7): one registry, four views, window chrome

P7 is the first real consumer of the P5 frozen contracts + the P6 one-brain.
There is **one command registry** (`commands/core/roster_v1.json`, 20 commands)
and **four views** over it, plus a **window-chrome skeleton** carrying the
identity/trust slots. All command logic lives in the C++ `commands_host`; the
WebUI is thin presentational views over the host protocol.

## The one-brain data flow

```
            ┌─────────────────────────────────────────────────────────┐
            │                    commands_host (C++)                  │
            │  roster_v1.json ─▶ registry ─▶ matcher / availability   │
            │                       │                        │        │
            │                 dispatch (id + source +        │        │
            │                 danger-class confirm gate)      │        │
            └──────────────┬───────────────────────────────────┼───────┘
                           │ host protocol v1                  │ reads P6
                           │ (one canonical sorted-key         │ resolver
                           │  JSON line per request)           │ snapshot
        ┌──────────────────┼──────────────────────┐           │
   ┌────▼─────┐      ┌─────▼─────┐         ┌──────▼─────┐    ┌──▼──────────────┐
   │  palette │      │  menus    │         │shortcut    │    │ trust-bindings  │
   │ (view #1)│      │ (view #2) │         │editor #3   │    │ v1 (P6, C++)    │
   ├──────────┤      ├───────────┤         ├────────────┤    └─────────────────┘
   │help index│      │           │         │            │
   │  view #4 │      │           │         │            │
   └──────────┘      └───────────┘         └────────────┘
```

The four views are **views over one registry**: the palette queries the
matcher; the menus render the menu-model; the shortcut editor manages bindings
(conflict checked against the C++ conflict matrix); the help index renders the
full roster. No view holds business logic — a view that computes a score or
decides availability is a P7 violation.

## The host protocol (v1)

One canonical, sorted-key JSON line per request, `{"method","args"}` positional.
Full table in `commands/host_protocol.md`. The methods:

| Method | Returns | Notes |
|---|---|---|
| `flag-status` | `{"ok":{"xr_command_registry_v1":"on\|off"}}` | off ⇒ stock chrome, empty views |
| `list` (`group?`) | `{"ok":{"commands":[{descriptor,registry}],"count"}}` | the registry, filtered |
| `query` (`query`) | `{"ok":{"results":[{available,id,kind,reason,score,title}],"count"}}` | ranked by the matcher |
| `invoke` (`id`,`source`,`confirmed`,`site`) | `{"ok":{"status":"rejected\|confirmation-required\|authorized",...,"ledger":[row]}}` | the dispatch gate |
| `bindings-set` | `{"ok":{"bound","command_id","conflict","persisted",...}}` | kill-durable store |
| `bindings-list` | `{"ok":{...sorted...}}` | committed bindings |
| `bindings-clear` | `{"ok":{"cleared":id\|null,"persisted"}}` | one or all |
| `menu-model` | `{"ok":{"flag","menus":[...],"tier1":{"count","items"}}}` | the view-#2 model |
| `register` (`descriptor`,`registry`) | `{"ok":{"id","order","status","tier1_count"}}` \| `{"error":...}` | dynamic add |

**Security order in `invoke`** (all in C++, never TS):
1. **source-tag whitelist** — `source` must be one of
   `{ui-chrome, palette, menu, shortcut, test}`. A `page`-originated invoke is
   rejected **and written to the ledger** *before* the id is even looked up.
2. **id whitelist** — an unknown id never reaches a handler.
3. **availability predicate** — the command must be available (read from the P6
   resolver snapshot); unavailable ⇒ disabled with a reason.
4. **danger-class confirmation** — a `destructive` command without `confirmed`
   returns `confirmation-required`, not a silent action.

## The four views

### View #1 — the palette (SR-first combobox)

The palette is an **ARIA APG combobox with listbox popup** — a screen-reader
user's *only* path to commands. The input keeps focus; arrow keys move the
highlight (announced via `aria-activedescendant`); Enter executes; Esc closes;
Tab moves out. Empty states are a live region (`aria-live="polite"`).

**Budgets (DoD):**
- **End-to-end** ≤ 50 ms warm / ≤ 150 ms cold (measured on the HG-31 farm).
- **Core sub-budget** ≤ 5 ms p99 on the 2000-command corpus — **measured in-
  sandbox** at **972 µs p99** (32-char query, 20,000 iters, seed 20260908) —
  see `commands/tests/bench-results.json`.

### View #2 — the menus (app + toolbar)

A view over the menu-model. Tier-1 (≤ 9 always-visible controls) is separate
from the tools-menu items; grouping order is stable (registration order).
`tools/menu_model_check.py` re-asserts the tier rules on the *generated* model
so the view cannot drift, and `--check` goldens it.

### View #3 — the shortcut editor

Renders committed bindings. On a conflict, the payload is shown **before** the
bind is committed, with the **conflicting command named** (or "reserved by the
browser / OS"). The conflict matrix + the kill-durable store (write-tmp-fsync-
rename) live in `commands/core/shortcuts.cc`.

### View #4 — the help index + printable cheatsheet

Renders the **full** roster as a printable artifact generated from the registry.
**No coming-soon rails** (§10): a placeholder (e.g. the Tor session, disabled by
its `tor.engine-ready` predicate) renders `disabled — <reason>`, never a "coming
soon" surface.

## Window chrome skeleton

The chrome patch (`patches/ui-skeleton/0100-ui-skeleton`, 9 files ≤ 12) carries
the **identity/trust slots** only: an `xr_command_bridge` (the C++ seam the P16
glue will drive) + an `xr_identity_color_bar` (the §1.4 identity/trust color
vocabulary). It does not implement the views — it reserves the slots so identity
and trust are *never* a "container" (they are first-class chrome).

## Keyboard model (the palette)

| Key | Action |
|---|---|
| `Alt+K` (host-registered) | open/focus the palette |
| `↑` / `↓` | move the highlight (announced via `aria-activedescendant`); wraps |
| `Enter` | execute the highlighted command (source=`palette`) |
| `Esc` | close the popup, return focus to the input |
| `Tab` | move focus out (the APG pattern keeps the SR announcement state) |
| typing | filters the ranked results live (core query, ≤ 5 ms p99) |

The palette is the *only* surface that reorders on keystrokes; the menus,
shortcut editor and help index are static renderings of the same registry.
