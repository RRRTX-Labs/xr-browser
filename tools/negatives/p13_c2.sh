# tools/negatives/p13_c2.sh — P13-T3 negatives: the export's refusal classes.
#
# The Observatory's export is the phase's second data-leak surface, and the
# difference that matters is not "there is a redaction function" but "the refused
# bytes never reach the writer". These cases plant rows that TRY to carry
# something out and assert both halves: the typed refusal, and the absence of the
# secret in every byte the tool produced.
#
# Offline and deterministic: rows are written to scratch JSON, no network.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OBS="$REPO_ROOT/tools/observatory_export.py"

# --- 1: user:pass@ is REFUSED, never stripped, and the secret is nowhere -----
case_c2_credentials_refused_not_stripped() {
  local R="$NEG_TMP/c2-cred" out rc
  mkdir -p "$R"
  printf '[{"seq":1,"target":"https://user:sekret@tracker.example/ad.js"}]' > "$R/rows.json"
  out="$("$PY" "$OBS" --fixture "$R/rows.json" --json 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 1 ] && { neg_out_file "$out"; \
       neg_out_has_fixed "credentials" && ! neg_out_has_fixed "sekret"; }; then
    echo "ok: credentials are REFUSED (not stripped) and the secret is absent from every byte"
  else
    echo "NEGATIVE-FAIL: a credential-bearing row must be refused with the secret absent (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c2_credentials_refused_not_stripped

# --- 2: a field NAMED cookie is refused by name, whatever its value ---------
case_c2_cookie_field_refused_by_name() {
  local R="$NEG_TMP/c2-cookie"
  mkdir -p "$R"
  printf '[{"seq":2,"target":"https://t.example/a.js","cookie":"x"}]' > "$R/rows.json"
  neg_expect_reject "a field named cookie is refused by NAME (renaming a leak does not fix it)" \
    "cookie" \
    "$PY" "$OBS" --fixture "$R/rows.json" --json
}
neg_register c2_cookie_field_refused_by_name

# --- 3: the default drops query + fragment even from a hostile row ----------
case_c2_query_and_fragment_never_default() {
  local R="$NEG_TMP/c2-q" out rc
  mkdir -p "$R"
  printf '[{"seq":3,"target":"https://t.example/a.js?uid=42#track"}]' > "$R/rows.json"
  out="$("$PY" "$OBS" --fixture "$R/rows.json" --json 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && ! neg_out_has_fixed "uid=42" && ! neg_out_has_fixed "#track"; then
    echo "ok: the default export carries no query params and no fragments"
  else
    echo "NEGATIVE-FAIL: the default must drop query and fragment (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c2_query_and_fragment_never_default

# --- 4: a filter RULE that looks like a fragment survives -------------------
case_c2_rule_that_looks_like_a_fragment_survives() {
  local R="$NEG_TMP/c2-rule" out rc
  mkdir -p "$R"
  printf '[{"seq":4,"target":"https://t.example/a.js","rule":"###tracker-ad"}]' > "$R/rows.json"
  out="$("$PY" "$OBS" --fixture "$R/rows.json" --json 2>&1)" && rc=0 || rc=$?
  neg_out_file "$out"
  if [ "$rc" -eq 0 ] && neg_out_has_fixed "###tracker-ad"; then
    echo "ok: a refusal class that would eat the product's own data was narrowed, and says so"
  else
    echo "NEGATIVE-FAIL: a filter rule that starts with # must survive the export (rc=$rc)"
    neg_out_file "$out"; sed 's/^/    | /' "$NEG_LAST_OUT_FILE"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register c2_rule_that_looks_like_a_fragment_survives
