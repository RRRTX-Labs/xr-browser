#!/usr/bin/env bash
# run_checks.sh — the P1 governance gate (local + CI entry point).
#
# Usage: tools/run_checks.sh [git-range]
#   git-range: rev range for dco_check and the Register-Change trailer
#              check (CI passes the PR base branch; default: full history).
#
# Every check must pass (exit 0). Exit 1 = gate failed.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
RANGE="${1:-}"

echo "== plan pin =="
"$PY" tools/plan_pin_check.py

echo "== feature registry (plan §2 ↔ docs/registry/*) =="
"$PY" tools/registry_lint.py

echo "== decision register (schema) =="
"$PY" tools/dr_parse.py

echo "== decision register (Register-Change trailers) =="
if [ -n "$RANGE" ]; then
  "$PY" tools/dr_parse.py --check-trailers --range "$RANGE"
else
  "$PY" tools/dr_parse.py --check-trailers
fi

echo "== license audit (canonical MPL-2.0 + copyleft scan) =="
"$PY" tools/license_audit.py

echo "== DCO signoff =="
if [ -n "$RANGE" ]; then
  "$PY" tools/dco_check.py --range "$RANGE"
else
  "$PY" tools/dco_check.py
fi

echo "== threat model v0 structure =="
"$PY" tools/check_threat_model.py

echo "== banned-vocabulary lint =="
"$PY" tools/vocab_lint.py

echo "== CODEOWNERS / S0 path sync =="
"$PY" tools/owners_sync.py --check --repo .

echo "== test suites =="
"$PY" -m pytest tools/tests/ -q

echo "== ALL GOVERNANCE CHECKS PASSED =="
