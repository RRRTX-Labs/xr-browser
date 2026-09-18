# tools/negatives/p12_close.sh — P12-CLOSE (T0-U1) negative cases.
#
# T0-U1 (dev-dependency closure + optional-tool SKIP law):
#   * the closure gate reddens on a transitive that is pinned but unhashed
#     (the exact libfaketime -> python-dateutil shape) and on one that is
#     unpinned;
#   * the current requirements-dev.txt passes (positive control);
#   * a host WITHOUT faketime that passes --require-ambient-probe must redden
#     (it certifies less than it claims) while the default path stays green;
#   * the --keep-going runner reports EVERY failing lane in one pass instead
#     of aborting at the first.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- dev_deps_closure_check: unhashed transitive reddens -------------------
case_closure_unhashed() {
  local R="$NEG_TMP/closure-unhashed"; mkdir -p "$R/tools/fixtures"
  cp "$REPO_ROOT/tools/dev_deps_closure_check.py" "$R/tools/"
  # current file, but with pluggy's pin kept and its two hash lines stripped
  # (still pinned, unhashed — the libfaketime/python-dateutil shape), AND its
  # trailing backslash dropped so the next pin does not glue into its tail.
  python3 - "$REPO_ROOT/tools/requirements-dev.txt" "$R/tools/requirements-dev.txt" <<'PY'
import sys
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
out, strip_hash, prev_pluggy = [], False, False
for ln in lines:
    if ln.startswith("pluggy=="):
        prev_pluggy = True
        ln = ln.rstrip("\t").rstrip()
        if ln.endswith("\\"):
            ln = ln[:-1].rstrip()          # drop the dangling continuation
        out.append(ln)
        strip_hash = True
        continue
    if strip_hash and ln.lstrip().startswith("--hash=sha256:"):
        continue                            # unhashed by design
    if prev_pluggy and ln.startswith("--hash"):
        continue
    prev_pluggy = False
    strip_hash = False
    out.append(ln)
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out) + "\n")
assert "pluggy==1.6.0" in out and not any(
    l.startswith("pluggy==1.6.0") and l.endswith("\\") for l in out), \
    "pluggy fixture mangled (dangling backslash survived)"
PY
  # prove the plant took: pluggy is pinned with no hash
  grep -q '^pluggy==' "$R/tools/requirements-dev.txt" || {
    echo "NEGATIVE-FAIL: closure_unhashed plant lost the pluggy pin"; return 1; }
  cp "$REPO_ROOT/tools/fixtures/dev-deps-closure.json" "$R/tools/fixtures/"
  neg_expect_reject "dev_deps_closure_check: a pinned-but-unhashed transitive reddens (the libfaketime shape)" \
    'carries no sha256 hash' \
    "$PY" "$R/tools/dev_deps_closure_check.py" --repo "$R"
}
neg_register closure_unhashed

# --- dev_deps_closure_check: unpinned transitive reddens -------------------
case_closure_unpinned() {
  local R="$NEG_TMP/closure-unpinned"; mkdir -p "$R/tools/fixtures"
  cp "$REPO_ROOT/tools/dev_deps_closure_check.py" "$R/tools/"
  grep -v '^pluggy==' "$REPO_ROOT/tools/requirements-dev.txt" \
    > "$R/tools/requirements-dev.txt"
  cp "$REPO_ROOT/tools/fixtures/dev-deps-closure.json" "$R/tools/fixtures/"
  neg_expect_reject "dev_deps_closure_check: a fixture-transitive absent from the file reddens" \
    'is NOT pinned' \
    "$PY" "$R/tools/dev_deps_closure_check.py" --repo "$R"
}
neg_register closure_unpinned

# --- dev_deps_closure_check: the current file is green ---------------------
case_closure_positive() {
  if "$PY" "$REPO_ROOT/tools/dev_deps_closure_check.py" --repo "$REPO_ROOT" \
       >/dev/null 2>&1; then
    echo "ok: dev_deps_closure_check positive control (current file closes)"
  else
    echo "NEGATIVE-FAIL: dev_deps_closure_check must pass on the current requirements-dev.txt"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register closure_positive

# --- date_invariance --require-ambient-probe, tool absent => red -----------
case_ambient_demand_red() {
  # XR_TEST_FAKETIME_ABSENT is the deterministic "tool absent" seam: this
  # host HAS the package (the strict governance lane shape), so the red path
  # must be provable WITHOUT uninstalling it.
  neg_expect_reject "date_invariance_check: --require-ambient-probe on a host without faketime reddens (a run that demands the probe must not certify less than it claims)" \
    'require-ambient-probe was set' \
    env XR_TEST_FAKETIME_ABSENT=1 \
    "$PY" "$REPO_ROOT/tools/date_invariance_check.py" --repo "$REPO_ROOT" \
      --require-ambient-probe
}
neg_register ambient_demand_red

# --- date_invariance default path, tool absent => still green ---------------
case_ambient_default_green() {
  if env XR_TEST_FAKETIME_ABSENT=1 \
       "$PY" "$REPO_ROOT/tools/date_invariance_check.py" --repo "$REPO_ROOT" \
       >/dev/null 2>&1; then
    echo "ok: date_invariance default path green without faketime (--as-of half is the verdict)"
  else
    echo "NEGATIVE-FAIL: date_invariance default path must green without faketime"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register ambient_default_green

# --- --keep-going reports every failing lane in one pass -------------------
case_keepgoing_all_failures() {
  local R="$NEG_TMP/keepgoing"; mkdir -p "$R/tools/checks"
  cp "$REPO_ROOT/tools/checks/gate_runner.sh" "$R/tools/checks/"
  cat > "$R/tools/run_checks.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/checks/gate_runner.sh"
kr_parse_args "$@"
echo "== lane A =="
"/bin/false"        # a lane that fails under fail-fast
echo "== lane B =="
die                 # a second, different failure class
echo "== lane C (must still run) =="
echo "lane C ran"
kr_finish
SH
  # the `&& rc=0 || rc=$?` shape is load-bearing: a bare `out=$(...);
  # rc=$?` lets `set -euo pipefail` abort the dispatcher on the inner
  # script's (expected) non-zero exit before rc is even assigned.
  out="$(bash "$R/tools/run_checks.sh" --keep-going 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q "LANE FAIL" \
       && printf '%s' "$out" | grep -q "lane C ran"; then
    echo "ok: --keep-going reported the failures AND still ran the downstream lane (single pass)"
  else
    echo "NEGATIVE-FAIL: --keep-going must run every lane and report each failure"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
  # and the default path still aborts at the first failure
  out_d="$(bash "$R/tools/run_checks.sh" 2>&1)" && rc_d=0 || rc_d=$?
  if [ "$rc_d" -ne 0 ] && ! printf '%s' "$out_d" | grep -q "lane C ran"; then
    echo "ok: default path still aborts at the first failing lane"
  else
    echo "NEGATIVE-FAIL: default path must abort at the first failing lane"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register keepgoing_all_failures
