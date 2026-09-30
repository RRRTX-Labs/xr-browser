# tools/negatives/p13_c02.sh — P13-C-P0.2 negatives: the cross-repo pin law.
#
# The defect class: a verdict computed from a sibling checkout that is not at
# the pin. Measured at e503f9e in three directions, and this battery covers all
# three plus the register that keeps the class from growing back:
#
#   1. sibling ONE COMMIT BEHIND => STALE-SIBLING, and the message must carry
#      BOTH shas (have/want) — a typed refusal that does not name the expected
#      value cannot be acted on;
#   2. sibling ABSENT => BLOCKED-LAYOUT, exit **2**, and specifically NOT exit 0
#      (the vacuous pass) and not a traceback (the ImportError that reads as
#      "broken environment");
#   3. a ROUTED VERDICT TOOL run against an absent sibling => exit 2 with the
#      typed line and no verdict printed. This is the case the brief asks for:
#      "a tool that ignores the assertion when the sibling is missing => red".
#      Without it, the helper could be imported and never called, and this
#      battery would still be green;
#   4. the REGISTER bites: a file that resolves a sibling path but is not
#      classified is a failure, so a new sibling reader cannot land silently.
#
# Deterministic and offline: the fixtures are scratch git repos, no network.
# Sourced by tools/run_negatives.sh through NEG_FILES.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# _p13c02_repo <dir> [--sibling <sha-offset>] — a scratch "repo" with its own
# DEPS pin and a scratch xr-core sibling whose HEAD is <offset> commits away.
_p13c02_repo() {
  local D="$1" offset="${2:-0}"
  rm -rf "$D"
  mkdir -p "$D/repo" "$D/xr-core"
  git -C "$D/xr-core" init -q
  git -C "$D/xr-core" config user.email n@example.invalid
  git -C "$D/xr-core" config user.name fixture
  echo one > "$D/xr-core/f.txt"
  git -C "$D/xr-core" add -A
  git -C "$D/xr-core" commit -qm "c1"
  local pin
  pin="$(git -C "$D/xr-core" rev-parse HEAD)"
  local i=0
  while [ "$i" -lt "$offset" ]; do
    echo "$i" >> "$D/xr-core/f.txt"
    git -C "$D/xr-core" add -A
    git -C "$D/xr-core" commit -qm "c$i"
    i=$((i + 1))
  done
  printf 'chromium_rev: "0000000000000000000000000000000000000000"\nxr_core_rev: "%s"\n' "$pin" \
    > "$D/repo/DEPS"
  echo "$pin"
}

# --- 1: one commit behind => STALE-SIBLING naming both shas -----------------
case_c02_stale_sibling_reddens() {
  local D="$NEG_TMP/c02-stale" out rc
  mkdir -p "$NEG_TMP"
  _p13c02_repo "$D" 1 >/dev/null
  out="$("$PY" tools/sibling_pin_check.py --repo "$D/repo" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 2 ]; then
    echo "NEGATIVE-FAIL: a stale sibling must exit 2 (BLOCKED, not a verdict); got rc=$rc"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  neg_out_file "$out"
  local have want
  have="$(git -C "$D/xr-core" rev-parse HEAD)"
  want="$(sed -n 's/^xr_core_rev: "\([0-9a-f]\{40\}\)".*/\1/p' "$D/repo/DEPS")"
  if neg_out_has_fixed "STALE-SIBLING" && neg_out_has_fixed "$have" \
     && neg_out_has_fixed "$want"; then
    echo "ok: cross-repo pin: a sibling one commit behind is STALE-SIBLING with both shas"
  else
    echo "NEGATIVE-FAIL: STALE-SIBLING must name both shas (have $have, want $want)"
    sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c02_stale_sibling_reddens

# --- 2: sibling absent => BLOCKED-LAYOUT exit 2 -----------------------------
case_c02_absent_sibling_is_blocked_layout() {
  local D="$NEG_TMP/c02-absent" out rc
  mkdir -p "$D/repo"
  printf 'xr_core_rev: "0000000000000000000000000000000000000000"\n' > "$D/repo/DEPS"
  out="$("$PY" tools/sibling_pin_check.py --repo "$D/repo" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 2 ] && { neg_out_file "$out"; neg_out_has_fixed "BLOCKED-LAYOUT"; }; then
    echo "ok: cross-repo pin: an absent sibling is BLOCKED-LAYOUT, exit 2"
  else
    echo "NEGATIVE-FAIL: absent sibling must be BLOCKED-LAYOUT exit 2 (got rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c02_absent_sibling_is_blocked_layout

# --- 3: a routed VERDICT tool must not render a verdict without the sibling --
case_c02_routed_tool_refuses_without_sibling() {
  local D="$NEG_TMP/c02-tool" out rc
  mkdir -p "$D/repo"
  printf 'xr_core_rev: "0000000000000000000000000000000000000000"\n' > "$D/repo/DEPS"
  out="$("$PY" tools/coverage_check.py --repo "$D/repo" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 2 ] && { neg_out_file "$out"; neg_out_has_fixed "BLOCKED-LAYOUT"; } \
     && ! neg_out_has_fixed "PASS: coverage_check"; then
    echo "ok: a routed verdict tool refuses with BLOCKED-LAYOUT exit 2 and prints no verdict"
  else
    echo "NEGATIVE-FAIL: coverage_check must refuse (rc=2, BLOCKED-LAYOUT, no PASS) with no sibling; got rc=$rc"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c02_routed_tool_refuses_without_sibling

# --- 4: the register bites — an unclassified sibling reader is a FAILURE ----
case_c02_unclassified_reader_reddens() {
  local D="$NEG_TMP/c02-reg" out rc
  rm -rf "$D"
  cp -r "$REPO_ROOT/tools" "$D-tools" 2>/dev/null || true
  mkdir -p "$D"
  # a tree whose tools/ is a copy of the real one plus a NEW sibling reader
  cp -r "$REPO_ROOT/tools" "$D/tools"
  rm -rf "$D/tools/__pycache__" "$D/tools/tests/__pycache__"
  cat > "$D/tools/new_reader.py" <<'PY'
from pathlib import Path
XR_CORE = Path(__file__).resolve().parents[1].parent / "xr-core"
PY
  out="$("$PY" "$D/tools/sibling_pin_check.py" --repo "$D" --audit-only 2>&1)" && rc=0 || rc=$?
  rm -rf "$D"
  if [ "$rc" -eq 1 ] && { neg_out_file "$out"; neg_out_has_fixed "tools/new_reader.py"; }; then
    echo "ok: the register bites (an unclassified sibling reader is a FAILURE, not a warning)"
  else
    echo "NEGATIVE-FAIL: an unclassified sibling reader must redden the audit (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c02_unclassified_reader_reddens

# --- 5: the SHELL shape is in the pattern set (P13-C-P0.2b) ------------------
# Found by building on the law instead of trusting it: the first sweep's five
# patterns were written from Python examples, so the panel lane's own language
# was the gap — `build/webui/panel-tests.sh` read
# `${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}`, a layout guess spelled in shell,
# and the audit did not see it. P6 exists because of that, and this case plants
# the exact old line in a scratch tree: the audit must name the file.
case_c02b_shell_layout_guess_reddens() {
  local D="$NEG_TMP/c02b-shell" out rc
  rm -rf "$D"
  mkdir -p "$D/build/webui"
  cp -r "$REPO_ROOT/tools" "$D/tools"
  rm -rf "$D/tools/__pycache__" "$D/tools/tests/__pycache__"
  cp "$REPO_ROOT/build/webui/panel-tests.sh" "$D/build/webui/panel-tests.sh"
  python3 - "$D/build/webui/panel-tests.sh" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
s = t.index('UI_CORE="${XR_CORE:-}"')
e = t.index('fi\n', s) + 3
p.write_text(t[:s] + 'UI_CORE="${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}"\n' + t[e:])
PY
  out="$("$PY" "$D/tools/sibling_pin_check.py" --repo "$D" --audit-only 2>&1)" && rc=0 || rc=$?
  rm -rf "$D"
  if [ "$rc" -eq 1 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "build/webui/panel-tests.sh"; }; then
    echo "ok: the SHELL layout guess is caught by name (P6), which the first sweep missed"
  else
    echo "NEGATIVE-FAIL: a shell layout guess must be caught by name (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c02b_shell_layout_guess_reddens
