# tools/checks/p11_gates.sh — the P11 gate sections of run_checks.sh.
#
# P11-T0-e split by the touched-file size law (<=380 lines): run_checks.sh
# is the DISPATCHER; the P11 gate bodies live here as functions called from
# the right point in the sequence. New P11 gates (T1–T8) join this file,
# not the dispatcher. Sourced by tools/run_checks.sh; uses $PY and runs
# under the caller's `set -euo pipefail` (an `exit 1` here ends the run,
# exactly as the inline blocks did before the split).

p11_caps_gates() {
  # P11-T0-d: the runner-capabilities ledger rule (e) consumes must itself
  # obey the citation law — present claims cite real runs (ci_run+ci_job) or
  # transcripts, UNOBSERVED entries say why, comment-claims are refused —
  # and the self-test proves those refusals offline.
  "$PY" tools/runner_caps.py --check
  "$PY" tools/runner_caps.py --self-test
}

p11_lane_gates() {
  echo "== P11-T0-c: scheduled-lane health (a red nightly is a red check within a day) =="
  # Reads the newest schedule-event run of every scheduled workflow through
  # the fetch.py chokepoint. Network absent/rate-limited => visible SKIP
  # (exit 77, skip-policy); the offline self-test runs FIRST so a SKIP can
  # never mask a broken checker. A lane red on its CURRENT definition is a
  # hard failure; STALE-FAIL/NOT-RUN/DISABLED are visible and non-fatal BY
  # RULE (the circularity guards are proven by the self-test's fixture).
  "$PY" tools/scheduled_lane_check.py --self-test
  if "$PY" tools/scheduled_lane_check.py; then :; elif [ $? -eq 77 ]; then
    echo "SKIP: SKIP (network unavailable for api.github.com) — needed for: scheduled-lane verdicts (silent-red-nightly visibility); local hint: re-run with network; the self-test above proved the checker itself"
  else
    exit 1
  fi
}

p11_crypto_gates() {
  echo "== P11-T0-b: no-new-crypto gate (ONE copy of a public algorithm, never a new one — ADR-0043) =="
  "$PY" tools/no_new_crypto_check.py
  "$PY" tools/no_new_crypto_check.py --self-test
}

p11_hostdoc_gates() {
  echo "== P11-T0-a: host protocol doc gate (every method-dispatching host documented, both directions) =="
  "$PY" tools/host_protocol_check.py
}

p11_size_law() {
  echo "== P11-T0-e: touched-file size law (every .py/.sh touched this phase is <=380 lines) =="
  "$PY" build/tests/test_file_size_law.py --touched
}

p11_vendor_gates() {
  echo "== P11-T1: vendored Rust pin (offline verification + the chokepoint law) =="
  # vendor_check hashes the whole vendored tree against the lock/manifests —
  # offline, deterministic, ~1s; needs the sibling xr-core checkout (every CI
  # lane has it at the DEPS pin). fetch_allowlist_check proves the ceremony
  # (ADR-0044) did not widen: static.crates.io joined, index/API hosts refused.
  "$PY" tools/vendor_check.py --check
  "$PY" tools/fetch_allowlist_check.py
}
