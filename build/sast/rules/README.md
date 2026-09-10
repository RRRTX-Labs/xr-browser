# SAST rules (P9-T9)

The plan names four SAST families — clang-tidy custom checks, rust-clippy +
`cargo vet` + `cargo audit`, Semgrep banned-API rules — and the deps-audit
row (GPL-link hard fail, advisory feeds). Their in-sandbox enforcement is
`tools/sast_check.py` over `sast-rules.yaml` (this directory); the heavy
tools run CI-side (HG-30), never in the P9 sandbox (no clang, no rustc, and
Semgrep is a new host).

## How the split works

| plan item | in-sandbox (gate) | CI-side (depth) |
|---|---|---|
| "no mode-logic outside `//xr/policy`" | `tools/mode_lint.py` (green today) | clang-tidy check `xr-mode-logic-outside-policy` |
| "no direct pref reads bypassing resolver" | literal scan (`prefs::`, `GetPrefs()`, `->GetBoolean(`) | clang-tidy `xr-no-pref-bypass` + Semgrep AST rule |
| Semgrep banned APIs | literal subset in `tools/sast_check.py` | `semgrep --config build/sast/rules/semgrep/ --error` |
| rust-clippy / `cargo vet` / `cargo audit` | n/a (no Rust code) | activate with the first crate (P11) |
| deps audit (GPL-link hard fail, advisories) | `tools/license_audit.py` (P1) + `npm ci` audit in T7 | CI advisory feeds |

## The canary law, restated for rules

Every active rule has a `fixtures/<rule-id>/bad.*` file containing its
literal pattern, and the gate fails if that fixture can't trip the rule (a
rule that can't turn red is theater). `fixtures/negative/` proves the
opposite direction: compliant code trips nothing. Fixtures are never built,
bundled, or scanned as product (they are outside every rule's scope).

## CI commands (HG-30, recorded not run here)

```sh
# Semgrep (banned APIs)
semgrep --config build/sast/rules/semgrep/ --error --strict \
  xr-core/xr xr-browser/tools

# clang-tidy custom checks (xr-mode-logic-outside-policy, xr-no-pref-bypass)
clang-tidy -p build/compile_commands.json -checks=-*,xr-* \
  $(find xr-core -name '*.cc')

# Rust gates (activate with the first crate, P11)
cargo clippy -- -D warnings && cargo vet --locked && cargo audit --deny warnings
```

## Adding a rule

1. Add the row to `sast-rules.yaml` (id, tool, home, severity, scope, exts,
   patterns, fixture, intent).
2. Add `fixtures/<id>/bad.*` with the literal pattern.
3. Extend `fixtures/negative/` if the pattern has an easy false-positive
   shape.
4. `python3 tools/sast_check.py --repo .` must be green; the new fixture
   must be the only file that trips the rule.
