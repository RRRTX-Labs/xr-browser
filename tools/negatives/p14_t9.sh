# tools/negatives/p14_t9.sh — P14-T9 negatives: the census fix-closure table
# is ENFORCED, not decorative.
#
# The closure section (docs/spike-identity/papercut-census.md) says per
# papercut what P14 actually closed. A closure column nobody checks is a
# licence to write "fixed" fifteen times, so census_lint.py now parses the
# 5-column closure table and demands:
#
#   1. control — an untouched copy of the real doc in a fixture root
#                (sibling xr-core linked at ../xr-core) is GREEN;
#   2. a dropped closure row (C-08)             => RED "has no closure row";
#   3. an invented status ("fixed")             => RED "status ... not in";
#   4. an artifact path that does not exist     => RED "do not exist";
#   5. an open-browser row whose method cell is
#      a placeholder ("TBD")                    => RED "must name the method";
#   6. a closed-core row that cites only a repo
#      doc, not the ../xr-core law              => RED "must cite an existing
#      ../xr-core artifact".
#
# Deterministic, offline, no network; the fixture's PARENT carries a SYMLINK
# to the pinned sibling ($NEG_TMP/xr-core — ../xr-core from a fixture root
# resolves ABOVE the root, exactly as the real doc's sibling does), so
# artifact resolution is exercised for real without a second checkout.
# Sourced by tools/run_negatives.sh through NEG_FILES.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINT="$REPO_ROOT/build/spike/census_lint.py"
DOC="$REPO_ROOT/docs/spike-identity/papercut-census.md"

_census_fixture() {  # <name> -> echoes a doc path inside a rooted fixture
  # Layout per fixture (PRIVATE — an earlier case owns $NEG_TMP/xr-core as a
  # real patch-fixture directory, so a shared sibling link would land inside
  # it and silently stop resolving):
  #   $NEG_TMP/census-<name>/root/docs/...   the "repo"
  #   $NEG_TMP/census-<name>/xr-core         symlink to the pinned sibling
  # ../xr-core from the fixture root resolves to the fixture's own parent,
  # mirroring the real layout (xr-browser/../xr-core).
  local name="$1" base="$NEG_TMP/census-$name" root="$NEG_TMP/census-$name/root"
  rm -rf "$base"; mkdir -p "$root/docs/spike-identity"
  # The doc cites repo-relative artifacts (docs/qa/..., docs/XR_...md) as
  # well as sibling ones — carry the docs tree so the control is honest.
  cp -r "$REPO_ROOT/docs/." "$root/docs/"
  cp "$DOC" "$root/docs/spike-identity/papercut-census.md"
  # P14-CLOSE C-5: the ledger's test / run-here cells also cite tools/ and
  # evidence/ paths; link them read-only so the control stays honest.
  ln -sfn "$REPO_ROOT/tools" "$root/tools"
  ln -sfn "$REPO_ROOT/evidence" "$root/evidence"
  ln -sfn "$REPO_ROOT/../xr-core" "$base/xr-core"
  printf '%s\n' "$root/docs/spike-identity/papercut-census.md"
}

neg_register census_closure_control_green
case_census_closure_control_green() {
  neg_expect_inband \
    "the untouched closure table passes in the fixture root" \
    'PASS: census-lint' \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$(_census_fixture ctrl)"
}

neg_register census_closure_missing_row_reddens
case_census_closure_missing_row_reddens() {
  local d; d="$(_census_fixture drop)"
  # Drop C-08's closure row (its line ends before C-09's row).
  "$PY" - "$d" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines()
out = [l for l in lines if not l.startswith("| C-08 | Notification permission/DB stay Profile-level;")]
assert len(out) == len(lines) - 1, "C-08 closure row anchor moved — update the negative"
open(p, "w").write("\n".join(out) + "\n")
PY
  neg_expect_reject \
    "a census id without a closure row reddens" \
    'closure: census id C-08 has no closure row' \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$d"
}

neg_register census_closure_invented_status_reddens
case_census_closure_invented_status_reddens() {
  local d; d="$(_census_fixture status)"
  "$PY" - "$d" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
old = "| open-browser | ../xr-core/test/isolation/matrix.yaml (cell `downloads-metadata`, mode browser, NOT-RUN) |"
assert old in src, "C-01 status anchor moved — update the negative"
open(p, "w").write(src.replace(old, "| fixed | ../xr-core/test/isolation/matrix.yaml (cell `downloads-metadata`, mode browser, NOT-RUN) |", 1))
PY
  neg_expect_reject \
    "a status outside the vocabulary reddens" \
    "closure C-01: status 'fixed' not in" \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$d"
}

neg_register census_closure_ghost_artifact_reddens
case_census_closure_ghost_artifact_reddens() {
  local d; d="$(_census_fixture ghost)"
  "$PY" - "$d" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
old = "../xr-core/test/isolation/matrix.yaml (cell `print`, mode browser, NOT-RUN)"
assert old in src, "C-02 artifact anchor moved — update the negative"
open(p, "w").write(src.replace(old, "../xr-core/test/isolation/ghost.yaml (cell `print`, mode browser, NOT-RUN)", 1))
PY
  neg_expect_reject \
    "a closing artifact that does not exist reddens" \
    "do not exist" \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$d"
}

neg_register census_closure_placeholder_method_reddens
case_census_closure_placeholder_method_reddens() {
  local d; d="$(_census_fixture method)"
  "$PY" - "$d" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
old = "docs/qa/browser-harness.md (mixed-identity walkthrough method) | find \"foo\" in A, switch to B, assert the field is not pre-filled |"
assert old in src, "C-06 method anchor moved — update the negative"
open(p, "w").write(src.replace(old, "docs/qa/browser-harness.md (mixed-identity walkthrough method) | TBD |", 1))
PY
  neg_expect_reject \
    "an open-browser row with no method reddens (the cited-path law)" \
    "closure C-06: open-browser row must name the method" \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$d"
}

neg_register census_closure_core_citation_required
case_census_closure_core_citation_required() {
  local d; d="$(_census_fixture core)"
  "$PY" - "$d" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
old = "| closed-core | ../xr-core/identity/core/session.h + ../xr-core/identity/tests/test_session_chaos.cc |"
assert old in src, "C-14 core-citation anchor moved — update the negative"
open(p, "w").write(src.replace(
    old,
    "| closed-core | docs/identity/lifecycle.md |", 1))
PY
  neg_expect_reject \
    "a closed-core claim without the ../xr-core law reddens" \
    "closure C-14: closed-core must cite an existing ../xr-core artifact" \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$LINT" --doc "$d"
}
