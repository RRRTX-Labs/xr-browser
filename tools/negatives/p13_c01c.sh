# tools/negatives/p13_c01c.sh — P13-C-P0.1c negatives: the derived-count law.
#
# The defect (reproduced at e503f9e, tools/tests/test_p8_t5_l10n.py:48):
#
#     assert "OK (127 messages" in r.stdout  # P11-T6: +36; P12-T6: +14
#
# The tool was green at 136; the literal said 127; three phases had edited the
# number and P13 had not. `tools/l10n_count_law.py` replaces the literal with a
# comparison of two DERIVED quantities, and these cases prove the comparison can
# actually fail — an assertion that has never been observed failing is a
# comment with a stack trace.
#
#   1. the real pair in agreement => GREEN (control: the law is not "everything
#      reddens");
#   2. a `.grdp` that gained a message while the captured transcript still
#      reports the OLD count => RED. This is the brief's registered negative,
#      verbatim: without the transcript argument the case could not be written;
#   3. a transcript whose count is BELOW the grow-only ratchet => RED (decrease
#      detection is the ratchet's job, and the ratchet has to bite);
#   4. a transcript with no count line at all => RED. Absence is not agreement;
#      "the tool did not say" must never read as "the tool agreed" — the exact
#      vacuity class P13-P0-C removed from the evidence bundle.
#
# Deterministic, offline, stdlib-only. Sourced by tools/run_negatives.sh.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- 1: control — the real file and the real transcript agree ----------------
case_c01c_live_pair_is_green() {
  local T="$NEG_TMP/c01c" out rc
  mkdir -p "$T"
  out="$("$PY" tools/grdp_check.py --ids-from-schema 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NEGATIVE-FAIL: grdp_check is not green on the real tree (rc=$rc) — control unusable"
    NEG_FAILURES=$((NEG_FAILURES + 1))
    return 0
  fi
  neg_out_file "$out"
  local law out2 rc2
  out2="$("$PY" tools/l10n_count_law.py --grdp ../xr-core/l10n/xr_strings.grdp \
      --tool-stdout "$NEG_LAST_OUT_FILE" --check 2>&1)" && rc2=0 || rc2=$?
  if [ "$rc2" -eq 0 ]; then
    echo "ok: count law control (the tool's reported count and the file's own count agree)"
  else
    echo "NEGATIVE-FAIL: the count law must pass on the real pair (rc=$rc2)"
    neg_out_file "$out2"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c01c_live_pair_is_green

# --- 2: a grown .grdp + a STALE transcript => RED ---------------------------
case_c01c_stale_transcript_reddens() {
  local T="$NEG_TMP/c01c-stale"
  mkdir -p "$T"
  "$PY" - "$T" <<'PYEOF'
import sys
from pathlib import Path
src = Path("../xr-core/l10n/xr_strings.grdp").read_text(encoding="utf-8")
extra = '<message name="IDS_XR_T_EXTRA" desc="extra" xr-id="t.extra">X</message>\n'
Path(sys.argv[1], "grown.grdp").write_text(
    src.replace("</grit-part>", extra + "</grit-part>"), encoding="utf-8")
# the transcript the tool WOULD have printed for the smaller file
n = src.count("<message ")
Path(sys.argv[1], "stale.out").write_text(
    f"grdp_check: xr_strings.grdp OK ({n} messages, isolation-card cross-check clean)\n",
    encoding="utf-8")
PYEOF
  neg_expect_reject "count law: a .grdp that gained a message while the tool reports the old count reddens" \
    'but the tool reported' \
    "$PY" tools/l10n_count_law.py --grdp "$T/grown.grdp" \
      --tool-stdout "$T/stale.out" --check
}
neg_register c01c_stale_transcript_reddens

# --- 3: below the grow-only ratchet => RED ----------------------------------
case_c01c_below_ratchet_reddens() {
  local T="$NEG_TMP/c01c-ratchet"
  mkdir -p "$T"
  "$PY" - "$T" <<'PYEOF'
import json, sys
from pathlib import Path
src = Path("../xr-core/l10n/xr_strings.grdp").read_text(encoding="utf-8")
n = src.count("<message ")
# a ratchet one ABOVE the real count: the string source "dropped" a message
Path(sys.argv[1], "ratchet.json").write_text(
    json.dumps({"schema": "xr-l10n-ratchet", "schema_version": 1,
                "metric": "fixture", "messages": n + 1,
                "direction": "grow-only"}), encoding="utf-8")
Path(sys.argv[1], "fresh.out").write_text(
    f"grdp_check: xr_strings.grdp OK ({n} messages, isolation-card cross-check clean)\n",
    encoding="utf-8")
PYEOF
  neg_expect_reject "count law: a string source below the grow-only ratchet reddens (a drop is a finding)" \
    'below the grow-only ratchet' \
    "$PY" tools/l10n_count_law.py --grdp ../xr-core/l10n/xr_strings.grdp \
      --tool-stdout "$T/fresh.out" --ratchet "$T/ratchet.json" --check
}
neg_register c01c_below_ratchet_reddens

# --- 4: a transcript with no count line => RED (absence is not agreement) ---
case_c01c_missing_count_line_reddens() {
  local T="$NEG_TMP/c01c-noline"
  mkdir -p "$T"
  printf 'grdp_check: something else entirely\n' > "$T/noline.out"
  neg_expect_reject "count law: a transcript with no count line reddens (silence never reads as agreement)" \
    'carries no .OK .N messages. line|no .OK .N messages.' \
    "$PY" tools/l10n_count_law.py --grdp ../xr-core/l10n/xr_strings.grdp \
      --tool-stdout "$T/noline.out" --check
}
neg_register c01c_missing_count_line_reddens
