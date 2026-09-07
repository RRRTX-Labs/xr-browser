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

# ---------------------------------------------------------------------------
# P4 gates. Network: citation-audit and check-pin-alive fetch read-only
# upstream/git bytes through the allowlisted choke points (build/upstream/
# fetch.py; unauthenticated git ls-remote). They fail closed on no network.
# ---------------------------------------------------------------------------
echo "== evidence bundles (contract: docs/contracts/evidence-bundle-v1.md) =="
"$PY" tools/evidence_check.py
# strict: P3+ bundles — cited artifact paths must resolve, source labels required
"$PY" tools/evidence_check.py --strict --only P3,P4,P5

echo "== spike: every file:line citation re-verified at the pin =="
"$PY" build/spike/citation_audit.py

echo "== spike: papercut census schema =="
"$PY" build/spike/census_lint.py

echo "== spike: probe driver static + fixture lanes =="
"$PY" build/spike/probe_driver.py --offline

echo "== cross-repo pin alive (DEPS xr_core_rev reachable from origin) =="
"$PY" build/sync.py check-pin-alive

echo "== patch ledger incl. candidate (spike/) dirs =="
"$PY" build/patching/apply.py lint --manifest ../xr-core/patches/manifest.yaml --xr-core ../xr-core

echo "== workflow files: expressions + schema (compile error = zero jobs) =="
"$PY" build/workflow_lint.py

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

echo "== ALL GOVERNANCE CHECKS PASSED =="
