# tools/negatives/p13_c3.sh — P13-T4 negatives: the pre-send refusals.
#
# One case per smuggle class, because the brief asks for exactly that and
# because a single "it refused something" case would pass while five of the six
# classes leaked. Each case asserts BOTH halves: the class is NAMED in the error,
# and the offending bytes are absent from every byte the tool produced.
#
# Offline and deterministic: rows and notes are written to scratch, no network,
# no queue outside $NEG_TMP.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BR="$REPO_ROOT/tools/breakage_report.py"

case_c3_smuggle_classes_refused_pre_send() {
  local R="$NEG_TMP/c3-smuggle" ok=0 total=0
  mkdir -p "$R"
  printf '{"origin":{"scheme":"https","registrable_domain":"shop.example"},"rule_id":"r-1","list_id":"l-1","bundle_version":3,"action":"kBlocked"}' \
    > "$R/event.json"
  # class:note — the note TRYING to carry the class, and the bytes that must not survive
  while IFS='|' read -r want note secret; do
    [ -n "$want" ] || continue
    total=$((total + 1))
    out="$("$PY" "$BR" --from-event "$R/event.json" --note "$note" \
        --as-of 2026-09-30T00:00:00Z --validate-only 2>&1)"
    rc=$?
    neg_out_file "$out"
    if [ "$rc" -eq 1 ] && neg_out_has_fixed "$want" && ! neg_out_has_fixed "$secret"; then
      ok=$((ok + 1))
    else
      echo "NEGATIVE-FAIL: $want was not refused pre-send (or its bytes survived): $out"
      NEG_FAILURES=$((NEG_FAILURES + 1))
    fi
  done <<'CASES'
url|broken at https://shop.example/cart?session=abc|session=abc
cookie|cookie session=9f3a keeps coming back|9f3a
user_agent|Mozilla/5.0 (X11; Linux x86_64) fails here|Mozilla/5.0
selector|the .cart > .total element never renders|.cart >
html|there is a <div class=cart> that never renders|<div
credentials|broken at https://user:hunter2@shop.example/|hunter2
CASES
  if [ "$ok" -eq "$total" ] && [ "$total" -ge 6 ]; then
    echo "ok: every smuggle class ($total) refused pre-send, named, with its bytes absent"
  fi
}

neg_register c3_smuggle_classes_refused_pre_send

# --- the queue may not be able to claim it is live --------------------------
case_c3_queue_must_say_fixture() {
  local R="$NEG_TMP/c3-queue"
  mkdir -p "$R"
  printf '{"origin":{"scheme":"https","registrable_domain":"shop.example"},"rule_id":"r-1"}' \
    > "$R/event.json"
  out="$("$PY" "$BR" --from-event "$R/event.json" --as-of 2026-09-30T00:00:00Z \
      --queue "$R/live-queue" 2>&1)" && rc=0 || rc=$?
  neg_out_file "$out"
  if [ "$rc" -eq 2 ] && neg_out_has_fixed "fixture"; then
    echo "ok: a queue path without 'fixture' is refused — a fixture must not travel as production"
  else
    echo "NEGATIVE-FAIL: a non-fixture queue path must be refused (rc=$rc): $out"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}

neg_register c3_queue_must_say_fixture

# --- the schema refuses by STRUCTURE (an extra field), before any tool logic --
case_c3_schema_refuses_an_extra_field() {
  local R="$NEG_TMP/c3-schema"
  mkdir -p "$R"
  python3 - "$REPO_ROOT" "$R" <<'PY'
import json, sys
repo, R = sys.argv[1], sys.argv[2]
v = json.load(open(f"{repo}/docs/contracts/vectors/breakage-report-v1.json"))
p = dict(v["accept"][0]["payload"]); p["html"] = "<div>page</div>"
json.dump(p, open(f"{R}/payload.json", "w"))
PY
  neg_expect_reject "the schema refuses an extra field (additionalProperties:false is the first line)" \
    "additional property" \
    "$PY" "$REPO_ROOT/tools/xr_schema.py" --repo "$REPO_ROOT" validate breakage-report "$R/payload.json"
}

neg_register c3_schema_refuses_an_extra_field
