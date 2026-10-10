# tools/negatives/p14c_c3.sh — P14-CLOSE C-3 (P14-T7): the xr://identities dev
# page's laws must REDDEN on planted defects.
#
# Every plant is an exact-anchor replacement in a per-case scratch copy
# (mktemp -d under NEG_TMP; never the sibling checkout itself; a missing
# anchor fails the case rather than planting nothing):
#   * view: a host page state with no stateText arm  -> shield_state_check
#   * view: a host page state dropped from the union -> shield_state_check
#   * view: resetAllAllowed() no longer demands dev  -> shield_state_check
#   * host: a reset-all branch reachable before the gate (the bypass)
#                                                    -> shield_state_check
#   * host: --build-channel defaulting to dev        -> shield_state_check
#   * view: modal vocabulary on the page             -> attention_check
#   * C++ core: DevChannel() admitting every channel -> test_manager_page
#   * C++ core: an unverified purge not raising the state -> test_manager_page
# The TS-core drift negative is the lane's own --plant-drift
# (tools/checks/p14_gates.sh). C++ cases SKIP VISIBLY without g++/make.
# Sourced by tools/run_negatives.sh (after p14c_c2.sh, whose
# _p14c_c2_cpp_plant helper the C++ cases reuse).

_p14c_c3_plant() {   # <src-abs> <dst> <anchor> <repl>
  ANCHOR="$3" REPL="$4" "$PY" - "$1" "$2" <<'PYEOF'
import os, sys
t = open(sys.argv[1], encoding="utf-8").read()
a, r = os.environ["ANCHOR"], os.environ["REPL"]
if a not in t:
    sys.exit("plant anchor missing: " + a)
open(sys.argv[2], "w", encoding="utf-8").write(t.replace(a, r, 1))
PYEOF
}

_p14c_c3_case() {   # <desc> <rel-src> <tool> <flag> <anchor> <repl> <pattern>
  local desc="$1" rel="$2" tool="$3" flag="$4" anchor="$5" repl="$6" pat="$7" W
  W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c3.XXXXXX")"
  if ! _p14c_c3_plant "$(_p14c_c2_core)/$rel" "$W/$(basename "$rel")" "$anchor" "$repl"; then
    echo "NEGATIVE-FAIL: $desc — plant anchor missing in $rel"
    NEG_FAILURES=$((NEG_FAILURES + 1)); rm -rf "$W"; return
  fi
  neg_expect_inband "$desc" "$pat" "$PY" "tools/$tool" "$flag" "$W/$(basename "$rel")"
  rm -rf "$W"
}

neg_register p14c_c3_identities_page_state_law_reddens
case_p14c_c3_identities_page_state_law_reddens() {
  local V=ui/identities/identities-core.ts
  _p14c_c3_case "identities page: planted missing stateText arm reddens shield_state_check" \
    "$V" shield_state_check.py --fixture-identities-view \
    "    case 'empty':
      return { msg: 'IDS_XR_IDENTITIES_STATE_EMPTY' };
" "" "reddened \(identities stateText missing an arm for empty\)"
  _p14c_c3_case "identities page: planted union drop reddens shield_state_check" \
    "$V" shield_state_check.py --fixture-identities-view \
    "  'purge-unverified',
" "" "reddened \(identities view union missing host state purge-unverified\)"
  _p14c_c3_case "identities page: view-side reset-all lock without the dev demand reddens" \
    "$V" shield_state_check.py --fixture-identities-view \
    "  return channel === 'dev' && typed === RESET_ALL_PHRASE;" \
    "  return channel !== '' && typed === RESET_ALL_PHRASE;" \
    "reddened \(identities resetAllAllowed\(\) does not demand channel === 'dev'\)"
}

neg_register p14c_c3_reset_all_bypass_reddens
case_p14c_c3_reset_all_bypass_reddens() {
  local H=identity/host/identity_host.cc
  _p14c_c3_case "identities page: planted reset-all branch before the gate reddens shield_state_check" \
    "$H" shield_state_check.py --fixture-identity-host \
    '  if (cmd == "manager-page" || cmd == "reset-all") {' \
    '  if (cmd == "reset-all" && args.find("fast")) {  // PLANTED BYPASS
    return Emit(JsonValue("reset"));
  }
  if (cmd == "manager-page" || cmd == "reset-all") {' \
    'reddened \(identity_host.cc: the branch naming "reset-all" does not call DevChannel'
  _p14c_c3_case "identities page: planted --build-channel default of dev reddens shield_state_check" \
    "$H" shield_state_check.py --fixture-identity-host \
    '  std::string channel = "release";' '  std::string channel = "dev";' \
    "reddened \(identity_host.cc: --build-channel does not default to release"
}

neg_register p14c_c3_identities_modal_vocabulary_reddens
case_p14c_c3_identities_modal_vocabulary_reddens() {
  _p14c_c3_case "identities page: planted modal confirmation reddens attention_check" \
    ui/identities/identities.ts attention_check.py --fixture-identity \
    "  private renderResetAll() {" \
    "  private renderResetAll() {  // confirm in a modal dialog" \
    "reddened \(identities.ts:[0-9]+ identity surface carries attention-escalation vocabulary"
}

neg_register p14c_c3_cpp_dev_channel_admits_all_reddens
case_p14c_c3_cpp_dev_channel_admits_all_reddens() {
  _p14c_c2_cpp_plant "C++ planted DevChannel() admitting every channel reddens test_manager_page" \
    identity/core/manager_page.cc '  if (channel == "dev") return true;' \
    '  if (!channel.empty() || channel.empty()) return true;  // PLANTED' \
    test_manager_page "refused: 'release'"
  _p14c_c2_cpp_plant "C++ planted silent unverified purge reddens test_manager_page" \
    identity/core/manager_page.cc '    unverified = unverified || !p.verified;' \
    '    (void)p;  // PLANTED: an unverified purge no longer raises the state' \
    test_manager_page "FAIL"
}
