# P14 research log

Every claim this phase makes, with the command that produced it. Rows that
could not be run say so and name the method; no row is a remembered value.
Written 2026-10-01; appended as the phase proceeds.

## P0-1 — the errexit/`!` class: the sweep, fixed or recorded harmless

The hosted `governance` failure at `724b466` was
`actionlint → shellcheck SC2251` in `core-hardening.yml` (annotation quoted in
`evidence/P14/logs/p0b-workflow-lint-before.txt`). Root cause of the
local/hosted divergence, the fifth in this program: **actionlint runs its
shellcheck pass only when `shellcheck` is installed on the host**. This
sandbox had actionlint but not shellcheck, so the deep pass was silently
shallower here than on the runner image. Both linters are now installed here
exactly as CI installs them (see the versions below), and P0-2's parity tool
makes the difference a printed fact forever after.

Linter installation, reproduced from the workflows' own recipes:

* actionlint **1.7.7**, tarball
  `https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz`,
  sha256 `023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757`
  — the exact version+hash `governance.yml` pins (`sha256sum -c` output in
  `evidence/P14/logs/p0a-linter-versions.txt`).
* shellcheck **0.10.0** via `apt-get install -y shellcheck` (local-only use;
  the runner image ships its own). The version is recorded in the same
  transcript, and P0-2's parity tool prints it on every run — a finding class
  that depends on the linter's version must at least be able to name it.

The sweep, over all 5 workflow files (64 `run:` blocks):

| where | shape | disposition |
|---|---|---|
| `core-hardening.yml:236` (Rust conformance) | `! grep -q "test result: FAILED" …` — statement-level `!`, errexit-exempt, followed by 3 more lines that mask its status | **FIXED** — `if grep -q …; then echo FAIL; exit 1; fi`. This is the line the hosted annotation named (reported at the step's `run:` line 214:9, SC2251 at 22:1 inside the script) |
| `core-hardening.yml:297` (vendored-copy build) | `! grep -qE "^error(\[|:)" …` — same shape, but the **last** statement of its script | **FIXED** — harmless as written (a trailing `! cmd`'s negated status *is* the script's exit status, which is why shellcheck 0.10.0 does not flag it), but that safety evaporates the moment a line is appended below; rewritten as the explicit check like its siblings so it cannot regress by growth |
| `core-hardening.yml:322` (offline shim build) | `! grep -qE …` followed by `test -f target/release/…` | **FIXED** — the `test -f` line decided the step's status; the hunt was inert |
| `core-hardening.yml:382` (real-engine parity) | `! grep -q '"verdict": "FAIL"' …` followed by a python block | **FIXED** — same masking shape |
| `core-hardening.yml:234,302,335,400` | `cargo … \| tee /tmp/x.log` pipelines | **harmless, recorded**: every one of those scripts sets `set -euo pipefail` (line numbers verified in the same pass), so cargo's real status propagates; the brief's "no verdict may depend on a piped exit code" law holds |
| `governance.yml:235,237` | `grep -q "MET\|DEVIATION" …` | **harmless, recorded**: the `\|` is BRE alternation inside a quoted grep *pattern*, not a shell pipeline; each is a single command whose failure triggers errexit (that is the assertion) |
| `governance.yml` + `run_checks.sh` `if cmd; then :; elif [ $? -eq 77 ]` (governance.yml lanes; `tools/run_checks.sh:197,204,343,367`; `tools/checks/p11_gates.sh:28`) | `$?` compared in a condition | **harmless, recorded**: `$?` is explicitly checked in a condition context — exactly what SC2251 asks for; this is the repo's SKIP-law idiom, not the exempt class |
| repo shell scripts (`tools/*.sh`, `tools/checks/*.sh`, `build/webui/*.sh`, `build/qa/drill/*.sh`, `build/signing/tests/*.sh`) | `grep -rn '^\s*! '` | **no hits** — the class does not exist outside the workflow set (rc=1 from grep, i.e. nothing matched) |

Sweep method: `grep -n '^\s*!' .github/workflows/*.yml` for statement-level
negation, plus a per-`run:`-block pass that flags every statement-level
pipeline, every `$(…)` inside a `[ ]` test (none found in any workflow), and
every negation — the extractor and its output are transcribed in
`evidence/P14/logs/p0b-workflow-lint-before.txt`. Post-fix, the same commands
return **no findings** and `./scripts/build workflow-lint` (actionlint 1.7.7 +
shellcheck 0.10.0 present) reports **PASS, actionlint: ran, clean**
(`evidence/P14/logs/p0c-workflow-lint-after.txt`).

What the fix does **not** prove: that no *future* workflow edit reintroduces
the class. That is P0-2's job — the parity tool prints whether shellcheck is
present locally, and the hosted lane always has it, so the next
local-green/hosted-red of this class is at least visible before the push.
