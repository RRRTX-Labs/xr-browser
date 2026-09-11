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
