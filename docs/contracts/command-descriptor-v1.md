# Contract: CommandRegistry descriptor v1 (§1.11 #10, §2.6, §10)

- **Schema:** `command-descriptor-v1.schema.json`. **Version:** 1.
- **Migration note:** `xr-schema-v1.md`. **Fixture:** `fakes/fixtures/command-descriptor-v1.json`.

## Rules (§10 Attention Budget)

Every command descriptor MUST carry:
- `id`, `title`, `attention_tier` (∈ `tier0`|`tier1`|`tier2`; §10 tiers),
- `danger_class` (∈ `safe`|`caution`|`destructive`) — REQUIRED on every command
  (§10 "danger-class on every command"),
- `surface` (where it appears), `handler` (a registered action id — never inline
  code; declarative only).

"Every feature without a command does not ship" (§2.6 CI-check): the registry
lint (P7) cross-checks features.yaml ↔ command ids. Themes are declarative JSON
only (R13); command handlers reference registered actions, never scripts.
