# tools/negatives/p12_t0.sh — P12-T0 negative cases.
#
# T0-a (date invariance): the wall-clock lint must redden on a planted
# clock read in the gate's closure and on a stale allowlist row, and the
# date-invariance gate must redden when a lane's bytes move with --as-of or
# when the probe dates cannot prove the freshness law still bites.
# T0-b (evidence bundles): a logs/-only phase dir and a zero-row bundle must
# both redden evidence_check --require.
# T0-c (tee asserts): a verdict-bearing `| tee` step with no pipefail and no
# negative assert must redden workflow_lint.
# T0-d (scratch hygiene): a scratch dir below the required free space must
# fail fast with a clear preflight message, not mid-run tar ENOSPC.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- wall_clock_lint: a planted clock read in the closure reddens -----------
case_wall_clock_offender() {
  local R="$NEG_TMP/wallclock"; mkdir -p "$R/tools/checks"
  printf '#!/bin/sh\n"$PY" tools/leaky.py\n' > "$R/tools/run_checks.sh"
  cat > "$R/tools/leaky.py" <<'PY'
import datetime
def verdict():
    # planted: a VERDICT computed from the wall clock
    return "EXPIRED" if datetime.date.today() > datetime.date(2000, 1, 1) else "OK"
PY
  neg_expect_reject "wall_clock_lint: a planted date.today() in the gate closure reddens" \
    'wall-clock read outside an argument default' \
    "$PY" "$REPO_ROOT/tools/wall_clock_lint.py" --repo "$R"
}
neg_register wall_clock_offender

# --- wall_clock_lint: the argument-default carve-out stays green -----------
case_wall_clock_default_ok() {
  local R="$NEG_TMP/wallclock-ok"; mkdir -p "$R/tools"
  printf '#!/bin/sh\n"$PY" tools/good.py\n' > "$R/tools/run_checks.sh"
  cat > "$R/tools/good.py" <<'PY'
import argparse, datetime
p = argparse.ArgumentParser()
p.add_argument("--as-of", default=datetime.date.today().isoformat())
PY
  if "$PY" "$REPO_ROOT/tools/wall_clock_lint.py" --repo "$R" >/dev/null 2>&1; then
    echo "ok: wall_clock_lint positive control (argument default permitted)"
  else
    echo "NEGATIVE-FAIL: wall_clock_lint must permit an add_argument default"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register wall_clock_default_ok

# --- wall_clock_lint: a dead allowlist row is a silent hole ----------------
case_wall_clock_dead_row() {
  local R="$NEG_TMP/wallclock-dead"; mkdir -p "$R/tools" "$R/build"
  printf '#!/bin/sh\n"$PY" tools/x.py\n' > "$R/tools/run_checks.sh"
  printf 'X = 1\n' > "$R/tools/x.py"
  # build/gone.py MUST be in the scanned closure, else the lint cannot judge
  # the row ("not scanned" != "no longer needed") and correctly stays silent.
  mkdir -p "$R/build"
  printf 'import tools.x  # pulls build/gone.py into the closure\n' > "$R/build/gone.py"
  printf 'import build.gone  # noqa\n' >> "$R/tools/x.py"
  # point the lint at a temp allowlist by copying the tool + a doctored row
  cp "$REPO_ROOT/tools/wall_clock_lint.py" "$R/tools/wall_clock_lint.py"
  sed -i "s#^ALLOWLIST = .*#ALLOWLIST = __import__('pathlib').Path('$R/dead.yaml')#" \
    "$R/tools/wall_clock_lint.py"
  printf 'schema_version: 1\nrows:\n  - path: build/gone.py\n    line: 99\n    reason: stale\n' \
    > "$R/dead.yaml"
  neg_expect_reject "wall_clock_lint: an allowlist row that matches nothing reddens (dead row = silent hole)" \
    'dead allowlist row' \
    "$PY" "$R/tools/wall_clock_lint.py" --repo "$R"
}
neg_register wall_clock_dead_row

# --- date_invariance_check: probe dates that cannot prove freshness --------
case_invariance_no_straddle() {
  neg_expect_reject "date_invariance_check: probe dates that do not straddle the expiry boundary cannot prove the freshness law" \
    'do not straddle' \
    "$PY" "$REPO_ROOT/tools/date_invariance_check.py" --repo "$REPO_ROOT" \
      --dates 2026-01-01,2026-06-01
}
neg_register invariance_no_straddle

# --- date_invariance_check: one date is a usage error ---------------------
case_invariance_one_date() {
  neg_expect_reject "date_invariance_check: a single probe date is a usage error" \
    'at least two far-apart' \
    "$PY" "$REPO_ROOT/tools/date_invariance_check.py" --repo "$REPO_ROOT" \
      --dates 2026-01-01
}
neg_register invariance_one_date

# --- date_invariance_check: a date-dependent artifact reddens -------------
# The plant: make the release-notes citation depend on --as-of (the exact
# P11-tip defect class, where the rendered bytes moved with the calendar).
case_invariance_drift() {
  # Isolated from $NEG_TMP on purpose: this plant is a full tree copy (~10 MB)
  # and P12-T0-d makes scratch space a first-class concern — a fixture that
  # fills the scratch dir would fail the very preflight it is meant to test.
  # The copy lives in the REAL parent directory because the gate tools resolve
  # sibling paths relative to the repo root (exception_ledger_check reads
  # ../xr-core/test/isolation/isolation-matrix.json); a copy under /tmp makes
  # that lane error out and its noise masks the drift this case must prove.
  # NOT $NEG_TMP and NOT $TMPDIR: the runner now points both inside the repo
  # (work/scratch), and tarring the repo into a directory inside itself fails
  # with "cannot copy a directory into itself" — which would mask the drift
  # this case exists to prove. The real parent is the only layout that both
  # keeps the sibling ../xr-core resolution working and stays outside the copy.
  local R
  R="$(cd "$REPO_ROOT/.." && pwd)/.p12-invariance-drift.$$"
  rm -rf "$R"
  mkdir -p "$R"
  (cd "$REPO_ROOT" && tar cf - --exclude=./.git .) | (cd "$R" && tar xf -)
  rm -f "$R/tools/release_notes.py"
  # The plant reproduces the EXACT P11-tip defect: the citation embedded
  # datetime.date.today(), so the rendered bytes moved with the calendar.
  # Both anchors are asserted — a fixture whose sed silently stops matching is
  # the invisible-negative class this whole file exists to prevent.
  python3 - "$REPO_ROOT/tools/release_notes.py" "$R/tools/release_notes.py" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
t = open(src, encoding="utf-8").read()
a1 = '    return (f"chromiumdash fetch_releases (allowlisted host, fetched "'
a2 = '            f"{fetched})")'
assert a1 in t and a2 in t, "citation_for anchors moved — update this fixture"
t = t.replace(a1 + "\n" + a2,
              a1 + "\n" + '            f"{fetched} at {datetime.date.today()}")')
open(dst, "w", encoding="utf-8").write(t)
PY
  # the plant must actually have taken, or this case proves nothing
  grep -q 'date.today()' "$R/tools/release_notes.py" || {
    echo "NEGATIVE-FAIL: invariance_drift plant did not apply"
    NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$R"; return 1; }
  # T0-U1: the drift is only visible under an AMBIENT displacement (a
  # date.today() read hides from the --as-of half by definition). faketime is
  # an OPTIONAL helper tool (skip-policy law), so a host without it SKIPs this
  # case visibly — the strict-probe red is separately covered by
  # p12_close.sh's ambient_demand_red. Never a silent pass, never a false red.
  if ! command -v faketime >/dev/null 2>&1; then
    neg_skip "invariance_drift needs the optional faketime helper tool (visible, never a PASS)"
  else
    neg_expect_reject "date_invariance_check: an artifact whose bytes move with the ambient clock reddens the invariance gate" \
      'release-notes-bytes' \
      "$PY" "$R/tools/date_invariance_check.py" --repo "$R" --require-ambient-probe
  fi
  # positive control: the unmodified copy is date-invariant, so the red above
  # is the plant's and not the harness's
  if "$PY" "$REPO_ROOT/tools/date_invariance_check.py" --repo "$REPO_ROOT" >/dev/null 2>&1; then
    echo "ok: date_invariance_check positive control (unmodified tree invariant)"
  else
    echo "NEGATIVE-FAIL: date_invariance_check positive control must pass on the real tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
  rm -rf "$R"
}
neg_register invariance_drift

# --- T0-b: evidence presence law ------------------------------------------
# A phase that produced commits but no bundle must redden — that is P11's
# exact shape, and it was invisible by design until P12-T0-b.
_mk_phase_repo() {
  local R="$1"
  rm -rf "$R"; mkdir -p "$R/evidence"
  git -C "$R" init -q
  git -C "$R" config user.email "neg@fixture"
  git -C "$R" config user.name "neg fixture"
  git -C "$R" commit -q --allow-empty -m "P42: a phase that shipped logs and no bundle"
}

case_evidence_logs_only() {
  local R="$NEG_TMP/ev-logs-only"; _mk_phase_repo "$R"
  mkdir -p "$R/evidence/P42/logs"
  echo "transcript" > "$R/evidence/P42/logs/t1.txt"
  neg_expect_reject "evidence_presence_check: a logs/-only phase dir reddens (P11's shape)" \
    'logs/-only' \
    "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R"
}
neg_register evidence_logs_only

case_evidence_missing_dir() {
  local R="$NEG_TMP/ev-missing"; _mk_phase_repo "$R"
  neg_expect_reject "evidence_presence_check: a phase in git history with no evidence dir at all reddens" \
    'does not exist' \
    "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R"
}
neg_register evidence_missing_dir

case_evidence_zero_rows() {
  local R="$NEG_TMP/ev-zero-rows"; _mk_phase_repo "$R"
  mkdir -p "$R/evidence/P42"
  printf '{"phase":"P42","generated":"2026-09-17","plan":"p.md","dod_rows":[]}\n' \
    > "$R/evidence/P42/evidence.json"
  printf '# human gates\n\n| id | gate |\n|---|---|\n| HG-1 | something a sandbox cannot do |\n' \
    > "$R/evidence/P42/human-gates.md"
  neg_expect_reject "evidence_presence_check: a bundle with zero dod_rows reddens (an empty bundle is not evidence)" \
    'zero dod_rows' \
    "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R"
}
neg_register evidence_zero_rows

case_evidence_empty_humangates() {
  local R="$NEG_TMP/ev-empty-hg"; _mk_phase_repo "$R"
  mkdir -p "$R/evidence/P42"
  printf '{"phase":"P42","generated":"2026-09-17","plan":"p.md","dod_rows":[{"id":"P42-D1","dod":"x","status":"VERIFIED","evidence":["a.txt"]}]}\n' \
    > "$R/evidence/P42/evidence.json"
  printf '# hg\n' > "$R/evidence/P42/human-gates.md"
  neg_expect_reject "evidence_presence_check: a near-empty human-gates.md reddens" \
    'empty or near-empty' \
    "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$R"
}
neg_register evidence_empty_humangates

case_evidence_presence_positive_control() {
  # The real tree is green: 11 phases derived from git history, all bundled.
  if "$PY" "$REPO_ROOT/tools/evidence_presence_check.py" --repo "$REPO_ROOT" \
       --also-repo "$REPO_ROOT/../xr-core" >/dev/null 2>&1; then
    echo "ok: evidence_presence_check positive control (11 phases, all bundled)"
  else
    echo "NEGATIVE-FAIL: evidence_presence_check positive control must pass on the real tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register evidence_presence_positive_control

# --- T0-c: the tee-assert rule --------------------------------------------
case_tee_unguarded() {
  local R="$NEG_TMP/tee-bad"; rm -rf "$R"; mkdir -p "$R/.github/workflows"
  cat > "$R/.github/workflows/bad.yml" <<'YML'
jobs:
  j:
    steps:
      - name: unguarded
        run: |
          cargo test --locked 2>&1 | tee /tmp/t.log
          grep -q "test result: ok" /tmp/t.log
YML
  neg_expect_reject "tee_assert_lint: a verdict-bearing pipe with no pipefail and no negative assert reddens" \
    'exit status is swallowed' \
    "$PY" "$REPO_ROOT/build/tee_assert_lint.py" --root "$R"
}
neg_register tee_unguarded

case_tee_zero_case() {
  # Deleting every tee must not "pass" the lint by removing its input.
  local R="$NEG_TMP/tee-empty"; rm -rf "$R"; mkdir -p "$R/.github/workflows"
  cat > "$R/.github/workflows/quiet.yml" <<'YML'
jobs:
  j:
    steps:
      - name: no pipes at all
        run: echo nothing to inspect
YML
  neg_expect_reject "tee_assert_lint: zero verdict-bearing pipes inspected reddens (zero-case law)" \
    'zero-case' \
    "$PY" "$REPO_ROOT/build/tee_assert_lint.py" --root "$R"
}
neg_register tee_zero_case

case_tee_multiline_counted() {
  # The bug this guards: a `\\`-continued command splits the verdict command
  # and its `| tee` across physical lines, so a per-line scan misses it.
  local R="$NEG_TMP/tee-multiline"; rm -rf "$R"; mkdir -p "$R/.github/workflows"
  cat > "$R/.github/workflows/ml.yml" <<'YML'
jobs:
  j:
    steps:
      - name: continued
        run: |
          python3 tools/some_check.py --repo . \
            --json 2>&1 | tee /tmp/out.log
          grep -q PASS /tmp/out.log
YML
  neg_expect_reject "tee_assert_lint: a backslash-continued command's pipe is still inspected (no per-line blind spot)" \
    'some_check.py' \
    "$PY" "$REPO_ROOT/build/tee_assert_lint.py" --root "$R"
}
neg_register tee_multiline_counted

# --- vocab_lint: a malformed allowlist row must not silently un-allowlist ----
case_vocab_allowlist_missing_line() {
  # load_allowlist() returns failures when a row lacks a required field, and
  # vocab_lint then treats the allowlist as EMPTY. So one malformed row does
  # not merely fail to allowlist its own hit — it un-allowlists every other
  # row, reddening unrelated files. That blast radius is why this is a
  # negative rather than a footnote: the failure looks like "39 new vocab
  # violations" and points at files nobody touched.
  local R="$NEG_TMP/vocabrow"
  rm -rf "$R"; mkdir -p "$R/docs/state" "$R/tools"
  # vocab_lint loads tools/_common.py by path, so the fixture needs it too —
  # copying only the tool produces a FileNotFoundError, which would be a
  # rejection "for the wrong reason" and lib.sh would not accept it.
  cp tools/vocab_lint.py tools/_common.py "$R/tools/"
  "$PY" - "$R" <<'PY'
import sys, pathlib
root = pathlib.Path(sys.argv[1])
(root / "docs" / "state" / "vocab-allowlist.yaml").write_text(
    "schema_version: 1\n"
    "allowlist:\n"
    "  - path: docs/x.md\n"
    "    pattern: anonymous\n"          # <- no `line:` field
    "    justification: malformed on purpose\n")
(root / "docs").mkdir(parents=True, exist_ok=True)
(root / "docs" / "x.md").write_text("we never claim anonymous browsing\n")
PY
  neg_expect_reject "vocab_lint: an allowlist row missing its line field fails the load, and the failure is reported rather than swallowed" \
    "missing field 'line'" \
    "$PY" "$R/tools/vocab_lint.py" --repo "$R"
}
neg_register vocab_allowlist_missing_line
