# tools/negatives/p14c_c5.sh — P14-CLOSE C-5: the docs-and-contracts laws
# must REDDEN on planted defects.
#
#   * papercut ledger (build/spike/census_lint.py): a census id with no
#     ledger row; an owner or budget that differs from the census row; a
#     closed-core row with no `yes: <log>` transcript; an open-browser row
#     with no `NOT-RUN: <method>`;
#   * Isolation Card identity rows (tools/isolation_matrix.py --check via
#     tools/identity_card.py): prose planted in the generated rows; the
#     generated block in docs/limitations.md hand-edited;
#   * the card's view (xr-core ui/panel/site-tab.ts identityCardView, run by
#     build/webui/panel-tests.sh): pointed at rows carrying prose, the suite
#     must fail — the card refuses prose instead of rendering it.
# Census plants reuse p14_t9.sh's _census_fixture (sourced earlier). Every
# other plant is an exact-anchor replacement in a mktemp -d scratch copy; a
# missing anchor fails the case rather than planting nothing.
# Sourced by tools/run_negatives.sh through NEG_FILES.

_p14c_c5_edit() {   # <file> <anchor> <repl>  (in place, anchor must exist)
  ANCHOR="$2" REPL="$3" "$PY" - "$1" <<'PYEOF'
import os, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
a, r = os.environ["ANCHOR"], os.environ["REPL"]
if a not in t:
    sys.exit("plant anchor missing: " + a[:80])
open(p, "w", encoding="utf-8").write(t.replace(a, r, 1))
PYEOF
}

_p14c_c5_census() {   # <name> <desc> <pattern> <anchor> <repl>
  local d
  d="$(_census_fixture "c5-$1")"
  if ! _p14c_c5_edit "$d" "$4" "$5"; then
    echo "NEGATIVE-FAIL: $2 — ledger anchor moved; update the negative"
    NEG_FAILURES=$((NEG_FAILURES + 1)); return
  fi
  neg_expect_reject "$2" "$3" \
    env PYTHONDONTWRITEBYTECODE=1 "$PY" "$REPO_ROOT/build/spike/census_lint.py" --doc "$d"
}

neg_register p14c_c5_papercut_ledger_reddens
case_p14c_c5_papercut_ledger_reddens() {
  _p14c_c5_census drop "papercut ledger: a census id with no ledger row reddens" \
    'ledger: census id C-07 has no ledger row' \
    '| C-07 | open-browser | docs/qa/browser-harness.md (mixed-identity walkthrough: PiP closes with its tab) | B | 3 files x ui | NOT-RUN: docs/qa/browser-harness.md |
' ''
  _p14c_c5_census owner "papercut ledger: an owner that differs from the census row reddens" \
    "ledger C-03: owner 'B' differs from the census row \('F'\)" \
    '(cell `devtools-attach`) | F |' '(cell `devtools-attach`) | B |'
  _p14c_c5_census budget "papercut ledger: a budget that differs from the census estimate reddens" \
    "ledger C-01: budget '2 files x ui' differs from the census estimate" \
    '(cell `downloads-metadata`) | B | 6 files x ui + 3 files x hook_points |' \
    '(cell `downloads-metadata`) | B | 2 files x ui |'
  _p14c_c5_census closed "papercut ledger: a closed-core row with no transcript reddens" \
    "ledger C-14: closed-core needs 'yes: <log>'" \
    '| A | 5 files x hook_points | yes: evidence/P14/logs/t8-identity-suite.txt; NOT-RUN: docs/qa/drill.md (real kill -9) |' \
    '| A | 5 files x hook_points | NOT-RUN: docs/qa/drill.md (real kill -9) |'
  _p14c_c5_census open "papercut ledger: an open-browser row with no NOT-RUN method reddens" \
    "ledger C-02: open-browser needs 'NOT-RUN: <method>'" \
    '(cell `print`) | B | 4 files x ui | NOT-RUN: docs/qa/browser-harness.md |' \
    '(cell `print`) | B | 4 files x ui | yes: evidence/P14/logs/t9-negatives.txt |'
}

neg_register p14c_c5_identity_card_refuses_prose
case_p14c_c5_identity_card_refuses_prose() {
  local W core
  W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c5.XXXXXX")"
  core="$(_p14c_c2_core)"
  cp "$core/test/isolation/identity-card-rows.json" "$W/rows.json"
  cp "$REPO_ROOT/docs/limitations.md" "$W/limitations.md"
  if _p14c_c5_edit "$W/rows.json" '"prop": "process-isolation"' \
       '"prop": "Identities never share a process"'; then
    neg_expect_reject "identity card: prose planted in the generated rows reddens isolation_matrix --check" \
      "prop is not a token \(the card refuses prose\)" \
      "$PY" "$REPO_ROOT/tools/isolation_matrix.py" --repo "$REPO_ROOT" --check --card "$W/rows.json"
    neg_expect_reject "identity card: the view refuses prose rows (panel-tests fails)" \
      "generated card refused: card-prose:5" \
      env XR_PANEL_IDENTITY_CARD="$W/rows.json" bash "$REPO_ROOT/build/webui/panel-tests.sh"
  else
    echo "NEGATIVE-FAIL: identity card prose — anchor moved"; NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
  if _p14c_c5_edit "$W/limitations.md" '| storage-scope | holds | 5/5 |' \
       '| storage-scope | holds everywhere | 5/5 |'; then
    neg_expect_reject "identity card: a hand-edited §1.13 block reddens isolation_matrix --check" \
      "the identity-card block drifted from the isolation-matrix record" \
      "$PY" "$REPO_ROOT/tools/isolation_matrix.py" --repo "$REPO_ROOT" --check --limitations "$W/limitations.md"
  else
    echo "NEGATIVE-FAIL: identity card block — anchor moved"; NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
  rm -rf "$W"
}
