# tools/negatives/p13_p0c.sh — P13-P0-C negative cases: the phase-finality law.
#
# The brief names four cases, and each one is a shape that previously passed
# *vacuously* (evidence_check.py judged only the claims that were present):
#   1. final + no ci-run                       => red
#   2. final + a ci-run at the PARENT sha      => red  (green run, wrong head)
#   3. final + a *-PENDING-* row               => red
#   4. interim + a *-PENDING-* row             => green
# Cases 5/6 are the presence-law control for the `P13-P0-A` subject shape: the
# blocker label P0 is not a phase (no evidence/P0/ is demanded), while a real
# phase token still demands its bundle.
# Case 8 guards the CLOSING wire: `--phase-final` is the one invocation that
# demands the in-flight phase be final, and a phase must not be able to close
# with `state: "interim"` still standing.
#
# Determinism: cases 1–2 exercise evidence_ci's head law through a fixture
# resolver (evidence_check's own SKIP-not-guess shape), so no network is
# touched; cases 3–4 run tools/evidence_finality.py, which is offline by
# construction.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
P13C_HEAD_A="$(printf 'a%.0s' $(seq 40))"
P13C_HEAD_B="$(printf 'b%.0s' $(seq 40))"

# _p13c_fixture <dir> <state|-> <phase_head|-> <with-ci-run: none|parent> <row-status>
# Writes a minimal, otherwise-legal P12 bundle + the in-flight declaration.
_p13c_fixture() {
  local R="$1" state="$2" head="$3" run="$4" status="$5"
  rm -rf "$R"; mkdir -p "$R/docs/state" "$R/evidence/P12/logs"
  printf '{"phase": "P13"}\n' > "$R/docs/state/phase-base.json"
  printf 'transcript\n' > "$R/evidence/P12/logs/local.txt"
  {
    printf '## 1. one\n'
    for i in $(seq 2 12); do printf '## %s. section\n' "$i"; done
  } > "$R/evidence/P12/report.md"
  "$PY" - "$R" "$state" "$head" "$run" "$status" <<'PY'
import json, sys
R, state, head, run, status = sys.argv[1:6]
rows = [{"id": "P12-X-1", "dod": "a planted row", "status": status,
         "source": "local-run", "evidence": ["logs/local.txt"]}]
if run == "parent":
    rows.append({"id": "P12-X-CI", "dod": "a hosted run", "status": "VERIFIED",
                 "source": "ci-run", "evidence": ["logs/local.txt"],
                 "ci_run": 1, "ci_job": 2, "workflow": "governance",
                 "head_sha": "b" * 40})
doc = {"phase": "P12", "generated": "2026-09-29", "plan": "docs/plans/x.md",
       "dod_rows": rows, "ci_claimed": ["governance"],
       "not_done_by_design": ["planted fixture — nothing real here"]}
if state != "-":
    doc["state"] = state
if head != "-":
    doc["phase_head"] = head
json.dump(doc, open(f"{R}/evidence/P12/evidence.json", "w"), indent=1)
PY
}

# A driver that resolves any cited run GREEN, so the only possible finding is
# the HEAD mismatch — i.e. the case proves the head law, not luck about a run.
_p13c_driver() {
  local R="$1"
  cat > "$R/driver.py" <<PY
import sys
sys.path.insert(0, "$REPO_ROOT/tools")
import evidence_check
evidence_check.CI_RESOLVER = lambda run, job, commits: True
sys.exit(evidence_check.main(["--repo", "$R", "--strict", "--only", "P12"]))
PY
}

# --- 1: final + no ci-run => red ---------------------------------------------
case_final_without_a_ci_run() {
  local R="$NEG_TMP/p0c-nocirun"
  _p13c_fixture "$R" final "$P13C_HEAD_A" none VERIFIED
  _p13c_driver "$R"
  neg_expect_reject "final bundle with no ci-run row at its head reddens (T0-U2 head law)" \
    'no ci-run row carries a matching head_sha' \
    "$PY" "$R/driver.py"
}
neg_register final_without_a_ci_run

# --- 2: final + ci-run at the PARENT sha => red ------------------------------
case_final_cirun_at_parent_sha() {
  local R="$NEG_TMP/p0c-parentsha"
  _p13c_fixture "$R" final "$P13C_HEAD_A" parent VERIFIED
  _p13c_driver "$R"
  neg_expect_reject "final bundle whose ci-run resolves GREEN at the parent sha still reddens (head mismatch, not greenness)" \
    'no ci-run row carries a matching head_sha' \
    "$PY" "$R/driver.py"
}
neg_register final_cirun_at_parent_sha

# --- 3: final + a PENDING row => red ----------------------------------------
case_final_with_a_pending_row() {
  local R="$NEG_TMP/p0c-pending"
  _p13c_fixture "$R" final "$P13C_HEAD_A" none BLOCKED-PENDING-T5
  neg_expect_reject "final bundle carrying a *-PENDING-* row reddens (PENDING is interim's vocabulary)" \
    'PENDING is interim' \
    "$PY" "$REPO_ROOT/tools/evidence_finality.py" --repo "$R"
}
neg_register final_with_a_pending_row

# --- 4: interim + PENDING => green ------------------------------------------
case_interim_with_a_pending_row() {
  local R="$NEG_TMP/p0c-interim"
  _p13c_fixture "$R" interim - none BLOCKED-PENDING-T5
  # The bundle is P12 while the tree declares P13 in flight, so the *in-flight*
  # exemption does not cover it — that is case 5 below. For case 4 the in-flight
  # phase must own the bundle, so relabel the fixture to P13.
  rm -rf "$R/evidence/P13"; mv "$R/evidence/P12" "$R/evidence/P13"
  if "$PY" "$REPO_ROOT/tools/evidence_finality.py" --repo "$R" >/dev/null 2>&1; then
    echo "ok: interim + PENDING is green for the in-flight phase (the phase-in-progress shape)"
  else
    echo "NEGATIVE-FAIL: the in-flight interim shape must be green"
    "$PY" "$REPO_ROOT/tools/evidence_finality.py" --repo "$R" 2>&1 | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register interim_with_a_pending_row

# --- 5: a closed phase may not hide behind interim => red --------------------
case_interim_on_a_closed_phase() {
  local R="$NEG_TMP/p0c-closedinterim"
  _p13c_fixture "$R" interim - none BLOCKED-PENDING-T5
  neg_expect_reject "an interim bundle for a phase that is NOT in flight reddens (interim may not be a closed phase's state)" \
    'not the in-flight phase' \
    "$PY" "$REPO_ROOT/tools/evidence_finality.py" --repo "$R"
}
neg_register interim_on_a_closed_phase

# --- 6: the presence law: P0 is a label, not a phase ------------------------
case_presence_law_p0_is_a_label() {
  local R="$NEG_TMP/p0c-presence" out rc
  rm -rf "$R"; mkdir -p "$R/evidence/P13/logs"
  printf '{"phase":"P13","dod_rows":[{"id":"R","dod":"x","status":"VERIFIED","evidence":["logs/t.txt"]}]}\n' \
    > "$R/evidence/P13/evidence.json"
  printf 'x %.0s' $(seq 60) > "$R/evidence/P13/human-gates.md"
  printf 't\n' > "$R/evidence/P13/logs/t.txt"
  ( cd "$R" && git init -q . && git -c user.email=n@n -c user.name=n add -A \
      && git -c user.email=n@n -c user.name=n commit -qm "P13-P0-A: the blocker-label subject shape" )
  out="$("$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: a 'P13-P0-A' subject must not demand an evidence/P0/ bundle"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: P0 is a blocker label — P13's bundle satisfies the law, no evidence/P0/ demanded"
  fi
  # positive control: a REAL phase token with no bundle still reddens
  ( cd "$R" && git -c user.email=n@n -c user.name=n commit -q --allow-empty -m "P9: a real phase with no bundle" )
  neg_expect_reject "a real phase token (P9) with no bundle still reddens (the bound did not disarm the law)" \
    'evidence/P9/ does not exist' \
    "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R"
}
neg_register presence_law_p0_is_a_label

# --- 7. the harness itself: a big-output rejection keeps its verdict --------
# The first C2 run of this battery caught a real harness bug: `printf BIG |
# grep -q PAT` takes SIGPIPE (141) when grep exits at its first match, and
# with `set -o pipefail` that 141 reads exactly like "the expected reason was
# absent". A gate that flakes red is a gate nobody trusts, so the guard is a
# case whose output is large and whose verdict must still be the right one.
case_harness_big_output_verdict() {
  local before="$NEG_FAILURES"
  neg_expect_reject "harness itself: a big-output rejection keeps its verdict" \
    'BIG-MARKER' bash -c 'echo BIG-MARKER; seq 1 3000; exit 1'
  if [ "$NEG_FAILURES" -ne "$before" ]; then
    echo "NEGATIVE-FAIL: the harness lost a verdict on a big output (piped exit code?)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: harness: a ~20 KB rejection still matches its expected reason"
  fi
}
neg_register harness_big_output_verdict

# --- 8: the closing wire — interim in flight is green by default, red on close -
# `run_checks.sh --phase-final` is the closing invocation (PHASE_FINAL=1 feeds
# --require-phase-final). Both halves matter: a wire that never reddens is
# decoration, and a wire that reddens a phase in progress would be switched off
# within a day. So this case asserts the PAIR on one fixture.
case_closing_wire_demands_final() {
  local R="$NEG_TMP/p0c-closing"
  _p13c_fixture "$R" interim - none BLOCKED-PENDING-T5
  rm -rf "$R/evidence/P13"; mv "$R/evidence/P12" "$R/evidence/P13"
  printf 'HG-1 planted gate\n' > "$R/evidence/P13/human-gates.md"
  # (a) control: the phase in progress is legal while it is in progress
  if ! "$PY" "$REPO_ROOT/tools/evidence_check.py" --repo "$R" --strict \
      --no-presence --only P13 >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: an in-flight interim bundle must be green in the default run"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  echo "ok: control — the in-flight interim bundle is green in the default (push) run"
  # (b) the closing invocation must refuse to let the phase close like that
  neg_expect_reject "the closing run (--phase-final) reddens while the in-flight phase is still interim" \
    "still says 'interim'" \
    "$PY" "$REPO_ROOT/tools/evidence_check.py" --repo "$R" --strict \
    --require-phase-final --no-presence --only P13
}
neg_register closing_wire_demands_final
