# P9 human gates + farm rows

The P9 objective is infrastructure: every §11 verification surface *exists*
before the feature phases need it. The surfaces that need a browser, a VM
farm, clang, rustc, or a live network are NOT executable in the P9 sandbox.
They are recorded below with their owner and command — never marked green
in-sandbox (anti-fabrication law L11).

## Farm rows (HG-28 … HG-37)

| id | surface | what runs there | sandbox twin (green today) |
|---|---|---|---|
| HG-28 | 24 h fuzz campaigns | `tools/policy_fuzz.py --timebox 86400 --seed <fixed>` + CI libFuzzer jobs | fleet gate 60 s + evidence 600 s (clean) |
| HG-29 | Mojo bind-side fuzz | clang + browser process | `tools/mojom_fuzz_gen.py` (contract-driven generator) |
| HG-30 | SAST heavy tools | Semgrep CLI / clang-tidy custom checks / cargo vet+audit | `tools/sast_check.py` + `tools/mode_lint.py` |
| HG-31 | browser tests · E2E · compat live replay · WPT · axe run | real browser | lint gates + offline replay + AXTree snapshots |
| HG-32 | SR / keyboard / human a11y passes | NVDA/VoiceOver/Orca; 12 keyboard tasks | `keyboard_tasks_check.py` (the list) + a11y lints |
| HG-33 | §11.10 kill matrix execution | browser process tree + VM snapshots | `tools/drill_check.py` (data) |
| HG-34 | §11.11 update-drill execution | per-OS VM farm | `tools/drill_check.py` (data) |
| HG-35 | §11.7 dedicated bench rigs | fixed-hardware list `docs/hw.md` | `gen_perf_budgets` + `perf_gate` (trend rig) |
| HG-36 | §11.8 per-route capture + endpoint audit | root + pcap | `tools/leaktest.py` loopback canary |
| HG-37 | §11.6 visual Gold bridge | Chromium Gold | `tools/visual_diff.py` stdlib engine + self-test |

## Human decisions recorded this phase

1. **axe-core needs a real DOM.** The only DOM shim that would run it
   without a browser is jsdom — a second package, not authorized by
   DEPENDENCY RULES. Decision: axe-core is pinned as the phase's single
   authorized dev-dep (ceremony in `docs/dependencies/axe-core.yaml`); the
   browser-side axe run is HG-31; the in-sandbox lane is the AXTree snapshot
   harness (`tools/a11y_tree.py`, documented heuristic transform, canary).
2. **libFuzzer / clang-tidy / cargo gates are CI-side.** No clang, no rustc,
   no semgrep host in the sandbox (zero-new-host law). Entry points and rule
   files are committed; execution is recorded, never fabricated.
3. **The trend-rig perf numbers are a record, not a claim.** `docs/state/
   bench-trend.json` freezes the run that generated `docs/state/
   perf-budgets.md` so `perf_gate --check` is reproducible; the report
   regenerates from it.
4. **PAT hygiene.** The phase brief's token was used only for the
   `git push` (remote URL), never written to any file. Secret-pattern grep:
   the token VALUE is absent from both trees; the string `ghp_` appears only
   as a pattern reference in P3/P4/P7/P8 hygiene notes (see
   `logs/secret-grep.txt`).

## Not done by design (this phase)

- Real browser tests, live corpus replay, real WPT runs (no browser).
- Per-route pcap capture / endpoint audit (no root, no live browser).
- Gold-bridge visual uploads (no Chromium checkout).
- axe-core execution against a rendered view (no DOM shim authorized).
- Update-drill / kill-matrix execution (no VM farm).
- 24 h fuzz campaigns and 10⁹-exec milestones (farm cadence, Spec-B bar).
