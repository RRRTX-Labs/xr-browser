# tools/negatives/p14c_c2.sh — P14-CLOSE C-2 + C-4: the ledger identity overlay
# and the cross-identity partition law must REDDEN on planted defects.
#
# Every plant is an exact-anchor replacement in a per-case scratch copy (mktemp -d under
# NEG_TMP; never a shared /tmp path, never the sibling checkout itself;
# a missing anchor fails the case rather than planting nothing):
#   * Python twin: omnibox filter ignores identity  -> replay FAILS (leak)
#   * Python twin: overlay writes identity_id INTO upstream history rows
#                  -> the oracle answers DELTA and the replay FAILS
#   * laws(): coverage hole / record without identity_id / frozen
#             ActivityKind drift / hand-edited vector -> each named FAIL
#   * C++ core: ledger_tag.cc omnibox leak -> test_ledger_tag FAILS
#   * C++ core: IdentityStore::Insert accepts a shared partition
#             -> test_derivation FAILS (the cross-identity process assertion)
# C++ cases SKIP VISIBLY without g++/make. Sourced by tools/run_negatives.sh.

_p14c_c2_core() { echo "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/../xr-core"; }

_p14c_c2_twin_plant() {   # <scratch-dir> <anchor> <replacement> -> planted path
  local W="$1" anchor="$2" repl="$3" src
  src="$(_p14c_c2_core)/fakes/ledger_identity.py"
  ANCHOR="$anchor" REPL="$repl" "$PY" - "$src" "$W/ledger_identity.py" <<'PYEOF'
import os, sys
text = open(sys.argv[1], encoding="utf-8").read()
a, r = os.environ["ANCHOR"], os.environ["REPL"]
if a not in text:
    sys.exit("plant anchor missing: " + a)
open(sys.argv[2], "w", encoding="utf-8").write(text.replace(a, r))
PYEOF
}

neg_register p14c_c2_omnibox_cross_identity_leak_reddens
case_p14c_c2_omnibox_cross_identity_leak_reddens() {
  local W; W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c2.XXXXXX")"
  _p14c_c2_twin_plant "$W" "        elif owner == current:" "        elif owner:  # PLANTED LEAK" || {
    echo "NEGATIVE-FAIL: omnibox leak plant could not be made"; NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$W"; return; }
  neg_expect_reject "planted cross-identity omnibox leak reddens the overlay replay" \
    "omnibox-a-sees-only-a: python twin" \
    "$PY" tools/ledger_identity_check.py --twin "$W/ledger_identity.py"
  rm -rf "$W"
}

neg_register p14c_c2_upstream_history_write_is_delta
case_p14c_c2_upstream_history_write_is_delta() {
  local W out rc; W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c2.XXXXXX")"
  _p14c_c2_twin_plant "$W" \
    "            upstream.append({k: row[k] for k in UPSTREAM_FIELDS if k in row})" \
    "            upstream.append({**{k: row[k] for k in UPSTREAM_FIELDS if k in row}, **({'identity_id': ident} if overlay is not None else {})})  # PLANTED WRITE" || {
    echo "NEGATIVE-FAIL: upstream-write plant could not be made"; NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$W"; return; }
  out="$("$PY" "$W/ledger_identity.py" history-oracle \
    '{"identity_id":"xr:00000000-0000-4000-8000-00000000000a","upstream_rows":[{"url_id":1,"url":"https://a.example/"}]}' 2>&1)" && rc=0 || rc=$?
  neg_out_file "$out"
  if ! neg_out_has_fixed '"verdict":"DELTA"'; then
    echo "NEGATIVE-FAIL: planted upstream write did not yield DELTA from the oracle"
    printf '%s\n' "$out" | sed 's/^/    | /'; NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: planted upstream history write -> oracle verdict DELTA"
  fi
  neg_expect_reject "planted upstream history write reddens the overlay replay" \
    "history-single-identity-zero-delta: python twin" \
    "$PY" tools/ledger_identity_check.py --twin "$W/ledger_identity.py"
  rm -rf "$W"
}

neg_register p14c_c2_laws_coverage_schema_drift_redden
case_p14c_c2_laws_coverage_schema_drift_redden() {
  local plant
  for plant in coverage schema drift generator; do
    neg_expect_reject "ledger overlay law '$plant' reddens on its planted defect" \
      "law-fail: $plant: .*(no vector|schema|drift|generator)" \
      env PLANT="$plant" CORE="$(_p14c_c2_core)" "$PY" - <<'PYEOF'
import json, os, sys
from pathlib import Path
sys.path.insert(0, "tools")
import ledger_identity_check as m
core, plant = Path(os.environ["CORE"]), os.environ["PLANT"]
vec = json.loads(m.VECTORS.read_text(encoding="utf-8"))["vectors"]
classes, kinds = m._classes(core / "fakes" / "ledger_identity.py"), m.frozen_kinds(core)
if plant == "coverage":
    vec = [v for v in vec if v["id"] != "tag-kVault-no-identity"]
elif plant == "schema":
    for v in vec:
        if v["id"] == "tag-kBlock":
            rec = json.loads(v["expect_stdout"]); rec.pop("identity_id")
            v["expect_stdout"] = json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n"
elif plant == "generator":
    vec[0]["args"]["identity_id"] = "xr:00000000-0000-4000-8000-0000000000ff"
else:
    kinds = kinds + ["kTelemetry"]
fails, _ = m.laws(vec, classes, kinds)
for f in fails:
    print(f"law-fail: {plant}: {f}")
sys.exit(1 if fails else 0)
PYEOF
  done
}

_p14c_c2_cpp_plant() {   # <case-desc> <rel-file> <anchor> <repl> <test-bin> <pattern>
  local desc="$1" rel="$2" anchor="$3" repl="$4" bin="$5" pat="$6" W
  if ! command -v g++ >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    neg_skip "$desc (g++/make absent — skip-policy)"; return
  fi
  W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c2cc.XXXXXX")"
  mkdir -p "$W/xr-core"
  cp -r "$(_p14c_c2_core)/identity" "$(_p14c_c2_core)/common" "$W/xr-core/"
  rm -rf "$W/xr-core/identity/tests/build"
  if ! ANCHOR="$anchor" REPL="$repl" "$PY" - "$W/xr-core/$rel" <<'PYEOF'
import os, sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
a, r = os.environ["ANCHOR"], os.environ["REPL"]
if a not in t:
    sys.exit("plant anchor missing: " + a)
open(p, "w", encoding="utf-8").write(t.replace(a, r))
PYEOF
  then echo "NEGATIVE-FAIL: $desc — plant anchor missing in $rel"; NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$W"; return; fi
  if ! make -s -C "$W/xr-core/identity/tests" BUILD="$W/build" "$W/build/$bin" >"$W/make.log" 2>&1; then
    echo "NEGATIVE-FAIL: $desc — scratch build failed"; sed 's/^/    | /' "$W/make.log" | tail -5
    NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$W"; return
  fi
  neg_expect_reject "$desc" "$pat" "$W/build/$bin"
  rm -rf "$W"
}

neg_register p14c_c2_cpp_omnibox_leak_reddens_test_ledger_tag
case_p14c_c2_cpp_omnibox_leak_reddens_test_ledger_tag() {
  _p14c_c2_cpp_plant "C++ planted omnibox leak (ledger_tag.cc) reddens test_ledger_tag" \
    identity/core/ledger_tag.cc "    } else if (owner == current) {" \
    "    } else if (!owner.empty()) {  // PLANTED LEAK" test_ledger_tag "FAIL"
}

neg_register p14c_c4_planted_partition_share_reddens_test_derivation
case_p14c_c4_planted_partition_share_reddens_test_derivation() {
  _p14c_c2_cpp_plant "C++ planted cross-identity partition share reddens test_derivation" \
    identity/core/identity.cc "  if (records_.count(rec.domain)) {" \
    "  if (false) {  // PLANTED SHARE" test_derivation "share one partition"
}
