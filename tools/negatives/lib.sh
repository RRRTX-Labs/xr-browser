# tools/negatives/lib.sh — shared negative-gate machinery (P9-T0-d).
#
# Why this exists: run_negatives.sh sat two lines from the 400-LOC law and
# printed no total — a silently dropped or never-registered case was
# invisible. This library makes the case count DERIVED (registered at
# source-time, executed by the dispatcher) and makes two failure classes
# structural:
#   * a registered case that never ran is an ERROR (zero-case law);
#   * a case whose command exits 0 (gate PASSED on bad input) is an ERROR —
#     the "negative harness that cannot fail" bug class P9 exists to kill;
#   * a case that captures a tool's output without capturing its STATUS in the
#     guarded shape is an ERROR — under `set -e` the capture assignment exits
#     the shell the moment the tool refuses, and refusing is what these cases
#     ask for. The battery used to die at case 1 of 3 with no FAIL line; the
#     linter below makes that shape impossible to reintroduce (P13-C-CLOSE,
#     2026-09-30).
#
# Case files register cases with `neg_register <name>` and define a
# `case_<name>()` function that builds its fixture and calls
# `neg_expect_reject` / `neg_expect_inband`. Registration is cheap (no
# fixture work), so sourcing a file can never be mistaken for running it.

# Law 4 shells out to $PY (the linter). The dispatcher exports PY; this keeps
# the library usable standalone too (a library that only works inside one
# caller is a library whose laws cannot be exercised on their own).
: "${PY:=${PYTHON:-python3}}"
export PY

NEG_TOTAL=0
NEG_RUN=0
NEG_FAILURES=0
NEG_SKIPPED=0
NEG_CASES=()

# register a case (run later by neg_run_all). The function case_<name>
# MUST exist or the run is an error (a registered case that never ran).
neg_register() {
  NEG_CASES+=("$1")
  NEG_TOTAL=$((NEG_TOTAL + 1))
}

# --- P13-P0-C harness robustness: verdicts never ride a pipeline ------------
# `printf '%s' "$out" | grep -q PAT` gives the RIGHT answer only when the
# producer finishes before grep exits. grep -q exits at the first match; on a
# big $out (a cosmetic byte-parity transcript is ~30 KB) printf/seq then take
# SIGPIPE, the pipeline status becomes 141, and `! ...` reports "not for the
# expected reason" for a case that in fact behaved exactly as required. That
# happened once in the P13-P0-C battery (2026-09-29, cosmetic naive-embedder
# case) and would be indistinguishable from a real regression. So: capture to
# a FILE once, then grep the file. No pipeline, no SIGPIPE, one verdict.
NEG_LAST_OUT_FILE="${NEG_LAST_OUT_FILE:-${NEG_TMP:-${TMPDIR:-/tmp}}/.neg-last-out.$$}"
neg_out_file() { printf '%s\n' "$1" >"$NEG_LAST_OUT_FILE"; }   # <captured out>
neg_out_has()       { grep -qE "$1" "$NEG_LAST_OUT_FILE"; }    # <ERE>
neg_out_has_fixed() { grep -qF "$1" "$NEG_LAST_OUT_FILE"; }    # <literal>

# neg_expect_reject <desc> <expected-pattern> <cmd...>
# Assert the command EXITS NON-ZERO with the expected reason.
neg_expect_reject() {
  local desc="$1" pattern="$2"
  shift 2
  local out rc
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: $desc — gate PASSED on bad input (rc=0)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! { neg_out_file "$out"; neg_out_has "$pattern"; }; then
    echo "NEGATIVE-FAIL: $desc — rejected, but not for the expected reason"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: $desc (rejected with expected reason)"
  fi
}

# neg_expect_inband <desc> <expected-pattern> <cmd...>
# For hosts that exit 0 and report status:"rejected" INSIDE the ok payload
# (the dispatch gate is the in-band rejection, not a process failure).
neg_expect_inband() {
  local desc="$1" pattern="$2"
  shift 2
  local out rc
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: $desc — command errored (rc=$rc); expected in-band rejection"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! { neg_out_file "$out"; neg_out_has "$pattern"; }; then
    echo "NEGATIVE-FAIL: $desc — in-band rejection pattern not found"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: $desc (in-band rejection observed)"
  fi
}

# visible SKIP (never counts as PASS; reported in the summary)
neg_skip() {
  echo "SKIP: $1"
  NEG_SKIPPED=$((NEG_SKIPPED + 1))
}

# run every registered case; a missing case_<name> function is an ERROR.
neg_run_all() {
  local name
  for name in "${NEG_CASES[@]}"; do
    if ! declare -F "case_${name}" >/dev/null 2>&1; then
      echo "NEGATIVE-FAIL: registered case '$name' has no case_${name}() — never ran"
      NEG_FAILURES=$((NEG_FAILURES + 1))
      continue
    fi
    "case_${name}"
  done
  NEG_RUN=$((NEG_RUN + ${#NEG_CASES[@]}))
}

# final verdict: zero cases, un-run cases, and any failure are all RED.
neg_finish() {
  if [ "$NEG_TOTAL" -lt 1 ]; then
    echo "NEGATIVE GATE FAILED: zero cases registered (zero-case law)"
    exit 1
  fi
  if [ "$NEG_RUN" -lt "$NEG_TOTAL" ]; then
    echo "NEGATIVE GATE FAILED: registered $NEG_TOTAL, ran $NEG_RUN (a case never ran)"
    exit 1
  fi
  if [ "$NEG_FAILURES" -ne 0 ]; then
    echo "NEGATIVE GATE FAILED: at least one gate accepted bad input or failed for the wrong reason"
    exit 1
  fi
  echo
  if [ "$NEG_SKIPPED" -gt 0 ]; then
    echo "note: $NEG_SKIPPED case(s) SKIPped (tool absent) — visible, never a PASS"
  fi
  echo "ALL NEGATIVE CASES REJECTED AS EXPECTED (N=$NEG_TOTAL)"
}

# neg_self_test — the canary for the harness itself. Three laws:
#   1. a case whose command exits 0 MUST turn the gate red (the harness can
#      fail — the exact bug class this phase exists to eliminate);
#   2. the case count is DERIVED: dropping a case file changes N;
#   3. a case file that registers nothing is an error.

# --- P13-P0-C: make a fixture bundle satisfy the phase-finality law ----------
# Fixtures exist to test ONE law each, but since P13-P0-C a bundle whose phase
# dir is P12+ is also judged as FINAL (state absent => final): it needs a
# report.md, a declared phase_head and a same-head ci-run row per claimed
# workflow. This helper adds exactly those, so a positive control keeps
# proving its own rule instead of failing on the new one. It never edits the
# rows a case is testing.
# Fixtures may only cite runs whose head matches the head they record: the
# resolver checks the JOB's conclusion AND the run's head against the bundle's
# recorded commits, so a fixed run id is only safe for the head it ran on.
# (head prefix -> run, job) — both verified green + head-matched on 2026-09-29.
neg_ci_pair_for_head() {   # <head> -> "run job"
  case "$1" in
    8fadb0ee*) echo "34615191984 103315238760" ;;   # core-hardening server-conformance
    *)         echo "34905296564 104180441172" ;;   # governance at 7922648a
  esac
}

neg_finality_props() {   # <repo-root> <phase-dir> [head]
  local R="$1" PH="$2" head="${3:-}"
  # The head must be known BEFORE the run/job pair is chosen: the resolver
  # certifies a ci-run row only when the JOB is green AND the RUN's head_sha is
  # a commit the bundle records, so a pair picked for the wrong head reddens the
  # fixture for a reason that has nothing to do with the law under test. (This
  # bit once the API quota returned: live resolution made it visible where the
  # 403-era SKIP had hidden it — 2026-09-29.)
  if [ -z "$head" ] || [ "$head" = "0000000000000000000000000000000000000000" ]; then
    head="$("$PY" - "$R/evidence/$PH/evidence.json" <<'PYH'
import json, re, sys
doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
blob = " ".join(str(doc.get(k, "")) for k in ("pin", "repos"))
m = re.search(r"\b[0-9a-f]{7,40}\b", blob, re.I)
print(m.group(0) if m else "")
PYH
)"
  fi
  [ -n "$head" ] || head="0000000000000000000000000000000000000000"
  local CI_PAIR; CI_PAIR="$(neg_ci_pair_for_head "$head")"
  mkdir -p "$R/evidence/$PH/logs"
  [ -f "$R/evidence/$PH/human-gates.md" ] || printf 'fixture human gates\n' > "$R/evidence/$PH/human-gates.md"
  [ -f "$R/evidence/$PH/logs/x.txt" ] || printf 'transcript\n' > "$R/evidence/$PH/logs/x.txt"
  # shellcheck disable=SC2086
  "$PY" - "$R" "$PH" "$head" $CI_PAIR <<'PYEOF'
import json, pathlib, re, sys
R, PH, head = sys.argv[1], sys.argv[2], sys.argv[3]
CI_RUN, CI_JOB = sys.argv[4], sys.argv[5]
d = pathlib.Path(R) / "evidence" / PH
f = d / "evidence.json"
doc = json.loads(f.read_text())
if head == "0000000000000000000000000000000000000000" or not head:
    # Prefer a head the bundle ALREADY records (pin/repos): the ci-run row's
    # head_sha must agree with both phase_head and the recorded commit set, or
    # the resolver's head check would redden the fixture for the wrong reason.
    blob = " ".join(str(doc.get(k, "")) for k in ("pin", "repos"))
    m = re.search(r"\b[0-9a-f]{7,40}\b", blob, re.I)
    head = m.group(0) if m else head
doc.setdefault("phase_head", head)
doc.setdefault("ci_claimed", ["governance"])
head = doc["phase_head"]
rows = doc.get("dod_rows")
if not isinstance(rows, list):
    rows = []
if not any(r.get("source") == "ci-run"
           and str(r.get("head_sha", "")).lower().startswith(head[:7].lower())
           for r in rows if isinstance(r, dict)):
    rows.append({"id": f"{PH}-FIXTURE-CI", "dod": "fixture head coverage",
                 "status": "VERIFIED", "source": "ci-run",
                 "ci_run": int(CI_RUN), "ci_job": int(CI_JOB),
                 "workflow": "governance", "head_sha": head,
                 "evidence": ["logs/x.txt"]})
doc["dod_rows"] = rows
f.write_text(json.dumps(doc, indent=1))
(d / "report.md").write_text("\n".join(f"## {i}. fixture section"
                                       for i in range(1, 13)))
PYEOF
}

# neg_lint_bare_captures <case-file...> — law 4 of the harness self-test.
#
# The incident (P13-C-CLOSE, 2026-09-30): tools/negatives/p13_c3.sh captured a
# refusing tool with
#     out="$("$PY" "$BR" ... 2>&1)"
#     rc=$?
# Under the battery's `set -e` the ASSIGNMENT carries the command's status, so
# the first refusal — the thing the case exists to observe — ended the whole
# run: no FAIL line, no summary, the remaining case files never sourced, and a
# product-looking red in a transcript that was really a harness bug.
#
# The required shape is one statement, so the status is captured even when the
# tool refuses:
#     out="$("$PY" "$BR" ... 2>&1)" && rc=0 || rc=$?
#
# A capture whose status is deliberately discarded (`... || true`) is not a
# verdict and is not flagged. Output: one line per offender; rc=1 if any.
neg_lint_bare_captures() {
  # Non-files are skipped inside the linter (a missing case file is already a
  # hard error in the dispatcher; this law is about the shape of what exists).
  "$PY" - "$@" <<'PYLINT'
import re
import sys

CAPTURE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*="\$\(')
GUARDED = re.compile(r'&&\s*[A-Za-z_][A-Za-z0-9_]*=0\s*\|\|')
STATUS_READ = re.compile(r'(^|[^\w$])[A-Za-z_][A-Za-z0-9_]*=\$\?')

bad = 0
for path in sys.argv[1:]:
    try:
        raw = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        continue
    # join backslash continuations so a capture spanning lines is one statement
    logical, buf, start = [], "", 0
    for i, line in enumerate(raw, 1):
        if not buf:
            start = i
        buf += line[:-1] if line.rstrip().endswith("\\") else line
        if not line.rstrip().endswith("\\"):
            logical.append((start, buf))
            buf = ""
    if buf:
        logical.append((start, buf))
    for idx, (lineno, text) in enumerate(logical):
        stripped = text.strip()
        if not CAPTURE.match(stripped):
            continue
        if GUARDED.search(stripped):
            continue          # the guarded shape: status taken on one statement
        if re.search(r'\|\|\s*true\s*$', stripped):
            continue          # status deliberately discarded: never a verdict
        # what follows the capture, on this statement or the next one
        tail = stripped.split(')"', 1)[1] if ')"' in stripped else ''
        nxt = logical[idx + 1][1].strip() if idx + 1 < len(logical) else ""
        if STATUS_READ.search(tail) or STATUS_READ.search(nxt):
            print(f"  {path}:{lineno}: capture whose status is read without the "
                  "guarded shape (`cmd) && rc=0 || rc=$?`)")
            bad += 1
sys.exit(1 if bad else 0)
PYLINT
}

neg_self_test() {   # <case-file...> — the same list the dispatcher will source
  # Every law here is a CANARY: it proves the harness can fail, not that a
  # product rule holds. Two properties were added on 2026-09-30 (P13-C-CLOSE)
  # after the battery died silently at case 1 of 3:
  #   * the canaries are counter-neutral — a canary that reddens the gate it is
  #     demonstrating is a trap for the next reader;
  #   * every capture of a subshell's status is guarded, because under `set -e`
  #     the very failure a law expects to observe would abort the run instead.

  # (1) a case whose command exits 0 MUST redden the gate.
  local before=$NEG_FAILURES
  neg_expect_reject "self-test canary: harness flags rc=0" "x" /bin/true >/dev/null
  if [ "$NEG_FAILURES" -ne "$((before + 1))" ]; then
    echo "SELF-TEST FAIL: a command that exits 0 did not redden the gate"
    exit 1
  fi
  NEG_FAILURES=$before        # counter-neutral: the canary was not a real case
  echo "ok: self-test (rc=0 canary fires — the harness can fail)"

  # (2) the case count is DERIVED: dropping a case file changes N.
  # `set +e` inside the walk: sourcing 40 case files is a measurement, and one
  # unexpected non-zero must not abort the self-test before it reports.
  local n_all="" n_minus=""
  n_all=$( ( set +e
             . tools/negatives/lib.sh
             for f in "$@"; do . "tools/negatives/$f"; done
             printf '%s' "$NEG_TOTAL" ) ) || n_all=""
  n_minus=$( ( set +e
               . tools/negatives/lib.sh
               for f in "$@"; do
                 [ "$f" = "${1:-}" ] || . "tools/negatives/$f"
               done
               printf '%s' "$NEG_TOTAL" ) ) || n_minus=""
  if [ -z "$n_all" ] || [ -z "$n_minus" ] || [ "$n_all" -lt 1 ] \
     || [ "$n_minus" -ge "$n_all" ]; then
    echo "SELF-TEST FAIL: dropping a case file did not change N (count is not derived)"
    exit 1
  fi
  echo "ok: self-test (dropping a case file changes N: $n_all -> $n_minus)"

  # (3) a registered case that never ran is an error.
  # The guarded capture matters here: neg_finish exits non-zero on purpose, so
  # a bare `ghost_rc=$( ... )` would abort the self-test instead of judging it.
  local ghost_rc=""
  ghost_rc=$( ( set +e
                . tools/negatives/lib.sh
                neg_register ghost_without_body
                neg_run_all
                neg_finish
                printf '0' ) ) || ghost_rc=$?
  if [ "$ghost_rc" -eq 0 ]; then
    echo "SELF-TEST FAIL: a registered case with no body did not error"
    exit 1
  fi
  echo "ok: self-test (registered-but-never-ran case errors)"

  # (4) law 4 — every case file captures tool status in the guarded shape, and
  # the linter that enforces it bites on the incident itself. Without the
  # canary this law would be a vacuous green: a linter that matches nothing
  # looks exactly like a tree with no offenders.
  local canary files=() f
  canary="$(mktemp "${NEG_TMP:-${TMPDIR:-/tmp}}/neg-lint-canary.XXXXXX.sh")"
  cat >"$canary" <<'CANARY'
case_canary() {
  out="$(false)"
  rc=$?
  [ "$rc" -eq 1 ] || echo "unreachable"
}
CANARY
  local canary_rc=0
  neg_lint_bare_captures "$canary" >/dev/null 2>&1 || canary_rc=$?
  rm -f "$canary"
  if [ "$canary_rc" -ne 1 ]; then
    echo "SELF-TEST FAIL: the bare-capture linter did not bite the incident shape"
    exit 1
  fi
  for f in "$@"; do
    if [ -f "$f" ]; then files+=("$f"); elif [ -f "tools/negatives/$f" ]; then files+=("tools/negatives/$f"); fi
  done
  if [ "${#files[@]}" -eq 0 ]; then
    echo "SELF-TEST FAIL: no case file handed to the linter (nothing to check is not a pass)"
    exit 1
  fi
  if ! neg_lint_bare_captures "${files[@]}"; then
    echo "SELF-TEST FAIL: a case file captures a tool's status without the guarded shape"
    exit 1
  fi
  echo "ok: self-test (no bare command capture in the case files; linter canary bites)"
}
