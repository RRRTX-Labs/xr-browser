# Help ↔ Settings deep-link contract v1 (Plan P8-T7)

Status: v1, machine-checked by `tools/help_deep_link.py` (P8-T7 run_checks
lane). Consumers: `xr-help-index` (anchor target + fallback status) and the
settings shell (anchors emitted on jump/search).

## 1. Anchor grammar

Both schemes are lowercase, `[a-z0-9.-]+` segments only:

| scheme | shape | target |
| --- | --- | --- |
| help | `xr://help/<command-id>` | the registry row whose `id` equals `<command-id>` in the help index; rows carry `id="xr-help-<command-id>"` |
| settings | `xr://settings/<section>` | the settings section (jump/scroll; shell's section registry) |
| settings | `xr://settings/<section>/<setting-key>` | one setting row inside the section |

The schema's top-level `anchor_root` is `xr://settings` and the section
registry (`settings_schema_v1.json` → `sections[].id`) is the authority for
the `<section>` segment; the command registry
(`docs/contracts/commands.md`, generated) is the authority for
`<command-id>`.

## 2. Settings ↔ help mapping law

Every settings section is reachable from help and every help row for a
settings command is reachable from settings:

1. **Settings → help.** For each section `S` in the settings schema there is
   a registered command `settings.S` in the command registry, and it is
   `enabled` (the §10 coverage ratchet binds the section to the command).
   Its help anchor is `xr://help/settings.S`.
2. **Help → settings.** Each registered `settings.*` command deep-links back
   to the section it controls: `xr://help/settings.S` ⇄
   `xr://settings/S`.
3. **Granularity.** v1 help anchors are command-granular only. Per-setting
   anchors (`xr://settings/S/k`) exist inside the settings view; help has no
   per-key rows in v1 (per-key help content is P36/P37 scope, explicitly out
   of this contract).
4. **Both directions are machine-checked** for the 3 sections (network,
   privacy, identity) ⇄ 3 commands (`settings.network`, `settings.privacy`,
   `settings.identity`): no schema section may lack its command and no
   `settings.*` command may point at a nonexistent section.

## 3. Resolution and fallback (honesty law)

- `xr://help/<id>`: the help index scrolls to the matching row
  (`scrollIntoView`, block center). An id the registry does not contain
  leaves the index visible and shows the status message `help.no-entry`
  (message id into `xr_strings.grdp`) naming the requested id — a
  placeholder entry is never fabricated.
- `xr://settings/...`: unknown section/key resolution is the settings
  shell's existing behavior (section-unavailable status; the shell's
  no-sections/flag-off states unchanged). Nothing invented.

## 4. Non-goals (recorded)

- Anchors never dispatch commands (help anchors only scroll/highlight).
- No anchors into non-registry surfaces in v1.
- No per-key help content pages in v1.

## 5. Future adopters

The P37 help center (`F-105`) and P36 l10n completion adopt this grammar;
grammar changes require a contract amendment (never a silent widen).

## 6. Enforcement

- `tools/help_deep_link.py`: schema ↔ registry mapping (both directions),
  contract-file presence.
- `run_checks.sh` P8-T7 lane; `l10n_extract` cross-checks the view's
  `help.no-entry` reference against the grdp.
