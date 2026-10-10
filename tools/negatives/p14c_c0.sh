# tools/negatives/p14c_c0.sh — P14-CLOSE C-0: closing P12/P13 is legal ONLY
# because of the appended `corrects` links.
#
# P13 carried seven BLOCKED-PENDING-* rows; P12 carried eight. Flipping a bundle
# to `state: final` is judged by tools/evidence_finality.py on EFFECTIVE status:
# a row named in a later row's `corrects` takes the correction's status. So the
# same final bundle must be:
#   1. GREEN with the links in place (every PENDING row superseded), and
#   2. RED on the PENDING law when the links are stripped (the flip alone is not
#      a closure: it would be a final bundle still carrying PENDING sentinels).
# Both runs use the REAL committed bundle, copied into a per-case scratch
# directory (never a shared /tmp path), offline (the finality law needs no
# network; ci-run resolution is evidence_ci's job and is not exercised here).
# Sourced by tools/run_negatives.sh.

_p14c_c0_fixture() {   # <dir> <phase> <strip:yes|no>
  local D="$1" P="$2" strip="$3" root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  mkdir -p "$D/docs/state" "$D/evidence"
  cp -r "$root/tools" "$D/tools"
  rm -rf "$D/tools/__pycache__" "$D/tools/tests"
  cp "$root/docs/state/phase-base.json" "$D/docs/state/phase-base.json"
  cp -r "$root/evidence/$P" "$D/evidence/$P"
  if [ "$strip" = yes ]; then
    "$PY" - "$D/evidence/$P/evidence.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
doc = json.load(open(p, encoding="utf-8"))
for r in doc["dod_rows"]:
    r.pop("corrects", None)
open(p, "w", encoding="utf-8").write(json.dumps(doc, indent=1))
PYEOF
  fi
}

neg_register p14c_c0_final_with_corrects_is_green_without_is_red
case_p14c_c0_final_with_corrects_is_green_without_is_red() {
  local P W out rc
  for P in P13 P12; do
    W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c0.XXXXXX")"
    _p14c_c0_fixture "$W/with" "$P" no
    out="$(cd "$W/with" && "$PY" tools/evidence_finality.py --repo . 2>&1)" && rc=0 || rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "NEGATIVE-FAIL: $P final WITH its corrects links did not pass (rc=$rc)"
      printf '%s\n' "$out" | sed 's/^/    | /'
      NEG_FAILURES=$((NEG_FAILURES + 1))
      rm -rf "$W"; continue
    fi
    _p14c_c0_fixture "$W/without" "$P" yes
    neg_expect_reject "$P final with the corrects links stripped reddens on the PENDING law" \
      "final bundle carries \*-PENDING-\* sentinels" \
      bash -c "cd '$W/without' && '$PY' tools/evidence_finality.py --repo ."
    rm -rf "$W"
  done
}
