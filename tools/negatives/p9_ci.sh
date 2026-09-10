# tools/negatives/p9_ci.sh — P9 T1–T12 runner canaries: each runner MUST be
# able to turn red. Every case is registered (counted, never hidden).

# --- 36. npm allowlist: a lockfile package outside the allowlist -----------
case_npm_allowlist_unknown() {
  local L="$NEG_TMP/package-lock.json" A="$NEG_TMP/npm-allowlist.json"
  printf '{"packages":{"":{"name":"x"},"node_modules/evil-pkg":{"version":"1.0.0"},"node_modules/lit":{"version":"3.3.3"}}}' > "$L"
  printf '{"schema_version":1,"packages":[{"name":"lit","match":"exact","version":"3.3.3","license":"BSD","role":"r","docs":"d"}]}' > "$A"
  neg_expect_reject "npm_allowlist: unknown package flagged" \
    'evil-pkg|violation' \
    "$PY" tools/npm_allowlist_check.py --repo . --lockfile "$L" --allowlist "$A"
}
neg_register npm_allowlist_unknown

# --- 37. copy lint: a score-looking number must be flagged -----------------
case_copy_lint_score() {
  local G="$NEG_TMP/xr_strings.grdp"
  printf '<grit-part><message name="M1" xr-id="a">Protection score is 9/10</message></grit-part>\n' > "$G"
  neg_expect_reject "copy_lint: score-looking number flagged" \
    '9/10|score' \
    "$PY" tools/copy_lint.py --repo . --grdp "$G"
}
neg_register copy_lint_score

# --- 38. a11y tree: a nameless button must be flagged ----------------------
case_a11y_tree_nameless() {
  local U="$NEG_TMP/ui"; mkdir -p "$U"
  printf '<button role="button"></button>\n' > "$U/bad.ts"
  neg_expect_reject "a11y_tree: nameless button flagged" \
    'no accessible name' \
    "$PY" tools/a11y_tree.py --repo . --ui-dir "$U"
}
neg_register a11y_tree_nameless

# --- 39. keyboard tasks: 11 tasks instead of the plan's 12 -----------------
case_keyboard_tasks_short() {
  local T="$NEG_TMP/keyboard-tasks.yaml"
  printf 'schema_version: 1\ntasks:\n' > "$T"
  for i in $(seq 1 11); do
    printf '  - id: kt-%02d\n    task: t\n    surface: s\n    owner: o\n' "$i" >> "$T"
  done
  neg_expect_reject "keyboard_tasks: 11 tasks != 12 flagged" \
    '11 tasks' \
    "$PY" tools/keyboard_tasks_check.py --repo . --tasks "$T"
}
neg_register keyboard_tasks_short

# --- 40. mojom fuzz generator: a drifted stream must fail --check ----------
case_mojom_fuzz_gen_drift() {
  local O="$NEG_TMP/fuzz-stream.jsonl"
  printf '{"host":"ghost"}\n' > "$O"
  neg_expect_reject "mojom_fuzz_gen: drifted stream flagged" \
    'drifted' \
    "$PY" tools/mojom_fuzz_gen.py --repo . --count 20 --seed 1 --out "$O" --check
}
neg_register mojom_fuzz_gen_drift

# --- 41. perf gate: a bench value over budget must MISS --------------------
case_perf_gate_missed() {
  local B="$NEG_TMP/bench-missed.json"
  printf '{"name":"canary","rig_class":"trend","unit":"us","rows":[{"metric":"resolve_cold_us","value_us":999999.0,"unit":"us"}]}' > "$B"
  neg_expect_reject "perf_gate: over-budget value MISSED" \
    'MISSED|FAIL' \
    "$PY" tools/perf_gate.py --repo . --bench "$B"
}
neg_register perf_gate_missed

# --- 42. drill check: a row without assertions must fail -------------------
case_drill_check_no_assertions() {
  local K="$NEG_TMP/kill-matrix.yaml"
  printf 'schema_version: 1\nrows:\n  - process: browser\n    kill: SIGKILL\n    assertions: []\n' > "$K"
  neg_expect_reject "drill_check: assertion-less row flagged" \
    'no assertions' \
    "$PY" tools/drill_check.py --repo . --kill-matrix "$K"
}
neg_register drill_check_no_assertions

# --- 43. surfaces check: a surface with no home must fail ------------------
case_surfaces_check_nohome() {
  local S="$NEG_TMP/surfaces.yaml"
  printf 'schema_version: 1\nsurfaces:\n  - id: "11.1"\n    name: unit\n    green: "x"\n' > "$S"
  neg_expect_reject "surfaces_check: homeless surface flagged" \
    'no home' \
    "$PY" tools/surfaces_check.py --repo . --surfaces "$S"
}
neg_register surfaces_check_nohome

# --- 44. sast check: a rule whose fixture cannot trip it must fail ---------
case_sast_check_dead_rule() {
  local B="$NEG_TMP/xb"; mkdir -p "$B/build/sast/rules/semgrep" "$B/build/sast/fixtures/ts-no-eval"
  printf '%s\n' \
    'schema_version: 1' \
    'rules:' \
    '  - id: ts-no-eval' \
    '    title: t' \
    '    tool: semgrep' \
    '    home: both' \
    '    severity: critical' \
    '    scope: []' \
    '    exts: [".ts"]' \
    '    patterns: ["eval("]' \
    '    fixture: build/sast/fixtures/ts-no-eval/bad.ts' \
    '    intent: x' > "$B/build/sast/rules/sast-rules.yaml"
  printf 'export const x = 1;\n' > "$B/build/sast/fixtures/ts-no-eval/bad.ts"
  printf 'rules:\n  - id: x\n    severity: ERROR\n    languages: [ts]\n    message: m\n    pattern: y\n' > "$B/build/sast/rules/semgrep/x.yaml"
  neg_expect_reject "sast_check: dead rule (fixture cannot trip) flagged" \
    'cannot trip|does not contain' \
    "$PY" tools/sast_check.py --repo "$B"
}
neg_register sast_check_dead_rule

# --- 45. evidence (P9+): an open row with empty not_done_by_design ----------
case_evidence_open_row_notdone() {
  local EV="$NEG_TMP/ev9a"; mkdir -p "$EV/evidence/P9"
  printf '# P9 gates\n\nfarm rows HG-31..HG-37.\n' > "$EV/evidence/P9/human-gates.md"
  printf '{"phase":"P9","generated":"2026-09-10","plan":"p","not_done_by_design":[],"dod_rows":[{"id":"E1","dod":"d","status":"BLOCKED-NET","evidence":["HG-31"]}]}' \
    > "$EV/evidence/P9/evidence.json"
  neg_expect_reject "evidence: open row with empty not_done_by_design flagged" \
    'not_done_by_design' \
    "$PY" tools/evidence_check.py --repo "$EV" --strict
}
neg_register evidence_open_row_notdone

# --- 46. evidence (P9+): a local-run row must cite a logs/* transcript -----
case_evidence_localrun_no_log() {
  local EV="$NEG_TMP/ev9b"; mkdir -p "$EV/evidence/P9" "$EV/docs/qa"
  printf '# P9 gates\n\nfarm rows HG-31..HG-37.\n' > "$EV/evidence/P9/human-gates.md"
  printf 'x\n' > "$EV/docs/qa/x.md"
  printf '{"phase":"P9","generated":"2026-09-10","plan":"p","source_labels":["local-run"],"dod_rows":[{"id":"E1","dod":"d","status":"VERIFIED","source":"local-run","evidence":["docs/qa/x.md"]}]}' \
    > "$EV/evidence/P9/evidence.json"
  neg_expect_reject "evidence: local-run row without a logs transcript flagged" \
    'transcript' \
    "$PY" tools/evidence_check.py --repo "$EV" --strict
}
neg_register evidence_localrun_no_log

# --- 47. evidence (P9+): a ci-run row must carry ci_run + ci_job ids --------
case_evidence_cirun_no_ids() {
  local EV="$NEG_TMP/ev9c"; mkdir -p "$EV/evidence/P9/logs"
  printf '# P9 gates\n\nfarm rows HG-31..HG-37.\n' > "$EV/evidence/P9/human-gates.md"
  printf 'ok\n' > "$EV/evidence/P9/logs/x.txt"
  printf '{"phase":"P9","generated":"2026-09-10","plan":"p","source_labels":["ci-run"],"dod_rows":[{"id":"E1","dod":"d","status":"VERIFIED","source":"ci-run","evidence":["logs/x.txt"]}]}' \
    > "$EV/evidence/P9/evidence.json"
  neg_expect_reject "evidence: ci-run row without ci_run/ci_job ids flagged" \
    'ci_job' \
    "$PY" tools/evidence_check.py --repo "$EV" --strict
}
neg_register evidence_cirun_no_ids
