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
  local R="${TMPDIR:-/tmp}/p12-invariance-drift.$$"
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
  neg_expect_reject "date_invariance_check: an artifact whose bytes move with --as-of reddens the invariance gate" \
    'release-notes-bytes' \
    "$PY" "$R/tools/date_invariance_check.py" --repo "$R"
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

# --- T0-d: scratch hygiene -------------------------------------------------
case_scratch_preflight_fails_fast() {
  # A scratch dir below the required free space must fail BEFORE any work,
  # with the number it needed — not mid-run with a tar ENOSPC.
  local out rc
  out="$(cd "$REPO_ROOT" && bash -c '. tools/scratch.sh; scratch_require 999999999' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: scratch_require accepted an impossible free-space demand"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'need >= 999999999 MiB free in'; then
    echo "NEGATIVE-FAIL: scratch_require failed but did not name the requirement"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch_require fails fast with the free space it needs"
  fi
}
neg_register scratch_preflight_fails_fast

case_scratch_preflight_skip_shape() {
  local out rc
  out="$(cd "$REPO_ROOT" && SCRATCH_SKIP_ON_SHORT=1 bash -c \
    '. tools/scratch.sh; scratch_require 999999999' 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 77 ]; then
    echo "NEGATIVE-FAIL: SCRATCH_SKIP_ON_SHORT must yield a visible SKIP (77), got rc=$rc"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'SKIP (scratch space)'; then
    echo "NEGATIVE-FAIL: the SKIP line must be visible, not silent"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch short-fall SKIPs visibly (77) rather than failing silently"
  fi
}
neg_register scratch_preflight_skip_shape

case_scratch_tar_excludes_build_outputs() {
  # The exclusion list IS the fix (build outputs are what filled the ~993 MiB
  # tmpfs), so assert it directly rather than tarring the whole tree inline --
  # a full-tree copy in a negative case costs more than the battery's budget
  # and would itself look like a hang.
  local missing=0 e
  for e in "./.git" "'*/build/*'" "'target'" "'node_modules'" \
           "'__pycache__'" "'*.o'"; do
    if ! grep -qF -- "--exclude=$e" "$REPO_ROOT/tools/scratch.sh"; then
      echo "NEGATIVE-FAIL: SCRATCH_TAR_EXCLUDES is missing $e"
      missing=$((missing + 1))
    fi
  done
  if [ "$missing" -ne 0 ]; then
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  fi
  # and prove the helper actually produces a tree WITHOUT .git on a tiny
  # synthetic source, so the assertion is about behaviour, not just text.
  local S="$NEG_TMP/scratch-src" D="$NEG_TMP/scratch-dst"
  rm -rf "$S" "$D"; mkdir -p "$S/.git" "$S/sub/build" "$S/__pycache__"
  echo keep > "$S/keep.txt"; echo junk > "$S/.git/obj"
  echo junk > "$S/sub/build/art.o"; echo junk > "$S/__pycache__/x.pyc"
  ( cd "$S" && tar "${SCRATCH_TAR_EXCLUDES[@]}" -cf - . ) \
    | ( mkdir -p "$D" && cd "$D" && tar -xf - )
  # Assert on FILES, not directories: `--exclude=*/build/*` matches the
  # CONTENTS of build/, so an emptied build/ directory may legitimately ride
  # along. What must never arrive is a .git object, a .o, or a .pyc.
  if find "$D" -name '*.o' -o -name '*.pyc' | grep -q . \
     || [ -e "$D/.git" ]; then
    echo "NEGATIVE-FAIL: the exclude list did not keep build outputs out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif [ ! -f "$D/keep.txt" ]; then
    echo "NEGATIVE-FAIL: the exclude list threw away source it should keep"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch excludes keep .git/build/__pycache__ out and source in"
  fi
}
neg_register scratch_tar_excludes_build_outputs

case_scratch_preflight_positive_control() {
  if (cd "$REPO_ROOT" && bash -c '. tools/scratch.sh; scratch_require 64') >/dev/null 2>&1; then
    echo "ok: scratch_require positive control (a satisfiable demand passes)"
  else
    echo "NEGATIVE-FAIL: scratch_require must pass when the space is there"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register scratch_preflight_positive_control

case_scratch_refuses_repo_into_itself() {
  # A tree copied under work/scratch nests recursively; one case produced a
  # 305 MB tree that made license_audit report 2759 hits against copies of its
  # own source. The guard is load-bearing, so it gets a negative.
  local out rc
  out="$(cd "$REPO_ROOT" && bash -c \
    ". tools/scratch.sh; scratch_tar_tree '$REPO_ROOT/work/scratch/x'" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: scratch_tar_tree copied the repo into itself"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    rm -rf "$REPO_ROOT/work"
  elif ! printf '%s' "$out" | grep -q 'refusing to copy the repo into itself'; then
    echo "NEGATIVE-FAIL: refused, but not with the recursion explanation"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: scratch_tar_tree refuses a dest inside the source tree (no recursive nesting)"
  fi
}
neg_register scratch_refuses_repo_into_itself

case_license_audit_skips_scratch() {
  # The other half of the same incident: a scratch tree inside the repo must
  # not be scanned as source.
  local R="$NEG_TMP/la-scratch"; rm -rf "$R"
  mkdir -p "$R/work/scratch/copy" "$R/docs/state"
  printf 'x = 1\n' > "$R/keep.py"
  # The marker text lives in a FIXTURE, not here: license_audit fails copyleft
  # tokens in code/shell files unconditionally, so spelling them out in this
  # case file reddened the very gate that runs it. The
  # tools/tests/fixtures/p11_vendor_red_licenses.json precedent.
  local FIX="$REPO_ROOT/tools/tests/fixtures/p12_copyleft_markers.json"
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); open(sys.argv[2],'w').write(d['scratch_marker']+chr(10))" \
    "$FIX" "$R/work/scratch/copy/junk.md"
  # the audit needs an allowlist to run at all (it exits 2 without one, which
  # would "pass" this case for the wrong reason)
  printf 'schema_version: 1\nallowlist: []\n' > "$R/docs/state/license-allowlist.yaml"
  cp "$REPO_ROOT/LICENSE" "$R/LICENSE"
  # positive control first: the SAME marker in a real source path must redden,
  # or a green here means the audit is simply not looking
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); open(sys.argv[2],'w').write(d['real_source_marker']+chr(10))" \
    "$FIX" "$R/real_source.md"
  if "$PY" "$REPO_ROOT/tools/license_audit.py" --repo "$R" >/dev/null 2>&1; then
    echo "NEGATIVE-FAIL: license_audit did NOT flag a copyleft marker in a real source path (the audit is not looking, so the scratch skip proves nothing)"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 1
  fi
  rm -f "$R/real_source.md"
  if "$PY" "$REPO_ROOT/tools/license_audit.py" --repo "$R" >/dev/null 2>&1; then
    echo "ok: license_audit skips the work/ scratch root (no hits on scratch copies)"
  else
    echo "NEGATIVE-FAIL: license_audit scanned work/ scratch and reddened on a copy"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register license_audit_skips_scratch
