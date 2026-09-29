# tools/ci_capture.sh — every gate step leaves its reason in the annotation (P13-P0-B).
#
# Sourced as the FIRST line of a workflow `run:` block:
#
#       - name: Governance checks
#         run: |
#           . tools/ci_capture.sh governance-checks
#           <the step body, verbatim>
#
# What it does (three lines of mechanism, no rewrite of the step bodies):
#   * the step's stdout+stderr keep flowing to the runner log AND are tee'd to a
#     transcript file, so the failing gate's own text is captured without
#     changing any pipeline a gate already uses;
#   * an EXIT trap fires on any non-zero exit and asks tools/gate_annotation.py
#     for the FIRST failing gate and a one-line reason;
#   * that becomes one GitHub workflow command:
#         ::error::<lane>: <first failing gate> - <one-line reason>
#     which the runner lifts into the check-run's public annotation — the exact
#     place where "Process completed with exit code 126." used to be the whole
#     story.
#
# Locally (no runner) the same line is printed, so a developer sees the same
# diagnosis CI sees. Sourced (`.`), never executed: a sourced file is an
# interpreted invocation and is exempt from the entry-point mode law by design.
#
# The lane name is the FIRST argument. The transcript lives in $RUNNER_TEMP
# (runner) or $TMPDIR (local) — never in the repository tree.

ci_capture_lane="${1:?usage: . tools/ci_capture.sh <lane-name>}"
ci_capture_log="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/xr-ci-${ci_capture_lane}.$$.log"
: > "$ci_capture_log"
export CI_CAPTURE_LOG="$ci_capture_log" CI_CAPTURE_LANE="$ci_capture_lane"

# Keep the live log AND a transcript. `exec` keeps this in the step's own shell
# (no subshell), so `set -e` semantics and exit codes are unchanged.
exec > >(tee -a "$ci_capture_log") 2>&1

_ci_capture_finish() {
  local rc="$1"
  [ "$rc" -eq 0 ] && return 0
  # Flush the tee before reading the transcript.
  sleep 0.2
  if [ -f tools/gate_annotation.py ]; then
    echo "== P13-P0-B: failure annotation (lane: $ci_capture_lane, exit $rc) =="
    python3 tools/gate_annotation.py --lane "$ci_capture_lane" --log "$ci_capture_log" || true
  fi
  echo "== transcript: $ci_capture_log =="
}
trap '_ci_capture_finish $?' EXIT
