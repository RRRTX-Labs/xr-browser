# tools/checks/p5_gates.sh — the P5 contract-freeze gate bodies.
#
# P14-P0-2: these lanes moved out of tools/run_checks.sh VERBATIM (same echo
# lines, same commands, same order) by the touched-file size law — run_checks
# sits at the 380-line ceiling and the P14 parity lane must be added to it, so
# a responsibility block moves out the same way p9/p11/p12/p13 gates did.
# Nothing here is new in P14; the git history of this file's first commit is
# the move itself.
#
# Sourced by tools/run_checks.sh; nothing here runs unless called.

p5_contract_gates() {
  # ---------------------------------------------------------------------------
  # P5 contract-freeze gates (§1.11). mojom_lint/contracts_manifest/vectors/
  # freeze run offline; amend_guard is warn-only pre-stamp and enforcing post.
  # ---------------------------------------------------------------------------
  echo "== P5: mojom structural lint (banned surface, kVersion, budgets) =="
  "$PY" tools/mojom_lint.py --roundtrip ../xr-core/mojom

  echo "== P5: §1.11 contracts manifest (14 items) + §2.10 reserved surface =="
  "$PY" tools/contracts_manifest.py

  echo "== P5: golden-vector fake parity (byte-stable) =="
  "$PY" tools/vectors_check.py

  echo "== P5: contract freeze register (FROZEN.yaml, ratified=PENDING) =="
  "$PY" tools/freeze_check.py

  echo "== P5: contract-amendment RFC trailer gate (T10) =="
  if [ -n "$RANGE" ]; then
    "$PY" tools/amend_guard.py --range "$RANGE"
  else
    "$PY" tools/amend_guard.py --range HEAD~1..HEAD
  fi

  echo "== P5: isolation-card l10n well-formed + vocab-clean =="
  "$PY" -c "import json,sys; d=json.load(open('../xr-core/l10n/isolation_card.json')); assert d['legal']=='PENDING-HG-1'; assert d['strings']; print('isolation-card OK', len(d['strings']),'strings')"
}
