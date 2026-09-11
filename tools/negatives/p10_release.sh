# tools/negatives/p10_release.sh — P10 T0-a..T9 negative cases: the release/
# signing/update gates must fail closed on bad input. Every case registered
# (counted, never hidden), per tools/negatives/lib.sh.

# --- 48. workflow_lint: a floating action tag must redden the lint ----------
# (T0-a: the enforcement used to live only in a docstring claim)
case_workflow_lint_floating_tag() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/floating.yml" <<'YML'
name: floating
on: push
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
YML
  neg_expect_reject "workflow_lint: floating uses: tag flagged" \
    'not pinned to a full 40-hex' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_lint_floating_tag

# --- 49. workflow_lint: a job without permissions: must redden the lint -----
case_workflow_lint_missing_permissions() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/noperm.yml" <<'YML'
name: noperm
on: push
jobs:
  j:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: echo hi
YML
  neg_expect_reject "workflow_lint: missing permissions flagged" \
    'declares no permissions' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_lint_missing_permissions

# --- 50. workflow_lint: a job without timeout-minutes must redden the lint --
case_workflow_lint_missing_timeout() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/notimeout.yml" <<'YML'
name: notimeout
on: push
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - run: echo hi
YML
  neg_expect_reject "workflow_lint: missing timeout-minutes flagged" \
    'declares no timeout-minutes' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_lint_missing_timeout

# --- 51. kill matrix: an xr-core with zero hosts must FAIL, never pass -----
# (T0-b: the zero-case law — a drill that executes nothing certifies nothing)
case_kill_matrix_zero_hosts() {
  local E="$NEG_TMP/empty-xr-core"; mkdir -p "$E"
  neg_expect_reject "kill_matrix: zero discovered hosts fails closed" \
    'found no \*_host targets|certify nothing' \
    "$PY" tools/kill_matrix.py --repo . --xr-core "$E"
}
neg_register kill_matrix_zero_hosts

# --- 52. mutation freshness: a score recorded before a core/** edit is STALE
case_mutation_freshness_stale() {
  local OLD OLDP
  OLD="$(git -C ../xr-core log --format=%H -1 -- themes/core)"   # the change itself
  OLD="$(git -C ../xr-core rev-parse "$OLD~1")"                  # recorded BEFORE it
  printf '{"schema_version":1,"cores":{"themes":{"xr_core_commit":"%s","transcript":"evidence/P10/logs/t0c-mutation-themes.txt","score_pct":100.0,"mutants":386,"killed":386,"survivors":[]}}}' \
    "$OLD" > "$NEG_TMP/stale-scores.json"
  neg_expect_reject "mutation_freshness: stale themes score flagged" \
    'STALE mutation score' \
    "$PY" tools/mutation_freshness.py --repo . --scores "$NEG_TMP/stale-scores.json"
}
neg_register mutation_freshness_stale
