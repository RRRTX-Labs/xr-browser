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
# strict: auto-covers every bundle newer than the P2 legacy exemption (P3+);
# P1/P2 stay exempt per the HG-25 ruling. A new phase is covered automatically
# — no hardcoded list to forget (the P6/P7 debt closed by T0, XR-P7-T0).
"$PY" tools/evidence_check.py --strict

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

# ---------------------------------------------------------------------------
# P6 gates (policy resolver v1). All offline except the C++ suite, which
# requires g++ and SKIPs VISIBLY when absent (skip-policy law) — the hosted
# lane has g++ and runs it for real.
# ---------------------------------------------------------------------------
echo "== P6: mode_lint — L3 one-brain ban + L13 intent headers =="
"$PY" tools/mode_lint.py --root ../xr-core

echo "== P6: policy.md regeneration diff-clean (generated, no hand drift) =="
"$PY" tools/vectors_to_md.py --check

echo "== P6: policy-change-event-v1 schema validates (incl. absence laws) =="
"$PY" tools/xr_schema.py validate policy-change-event docs/contracts/tests/golden-policy-change-event.json

echo "== P6: C++ policy core — build + all suites (vectors parity incl.) =="
if command -v g++ >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  XR_BROWSER_ROOT="$(pwd)" make -C ../xr-core/policy/tests test
else
  echo "SKIP: SKIP (tool absent: g++/make) — needed for: the C++ policy core suites incl. the 66-vector byte-parity matrix (P6); CI runners have g++ and run them; local hint: apt-get install g++ make (build-essential)"
fi

# ---------------------------------------------------------------------------
# P7 gates (one command registry, four views, window-chrome skeleton). The C++
# commands core requires g++/make (SKIP-visibly when absent). The WebUI
# toolchain requires node/npm and SKIPs VISIBLY (exit 77) when the registry is
# unreachable — sources + config always ship (P7 #5 failure condition).
# ---------------------------------------------------------------------------
echo "== P7: C++ commands core — build + all 8 suites + bench + 31-case parity =="
if command -v g++ >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  XR_BROWSER_ROOT="$(pwd)" make -C ../xr-core/commands/tests test
else
  echo "SKIP: SKIP (tool absent: g++/make) — needed for: the C++ commands core suites (descriptor/registry/matcher/availability/dispatch/shortcuts/dial/host) + the in-sandbox bench; local hint: apt-get install g++ make"
fi

echo "== P7: ≤12 hook patch round-trip vs the pinned Chromium rev =="
"$PY" build/webui/patch_roundtrip.py --xr-core ../xr-core

echo "== P7: WebUI reproducible toolchain (tsc-strict + deterministic bundle + CSP) =="
if bash build/webui/toolchain.sh; then :; elif [ $? -eq 77 ]; then
  echo "SKIP: WebUI toolchain skipped (node/npm or npm registry unavailable) — sources+config shipped"
else
  echo "FAIL: WebUI toolchain gate failed"; exit 1
fi

echo "== P7: WebUI reproducibility — two builds byte-identical (R1 rung) =="
if bash build/webui/repro-check.sh; then :; elif [ $? -eq 77 ]; then
  echo "SKIP: WebUI repro skipped (node/npm or npm registry unavailable)"
else
  echo "FAIL: WebUI repro gate failed"; exit 1
fi

echo "== P7: CSP lint — no runtime network/eval in ui/** + commands/** =="
"$PY" tools/csp_lint.py

echo "== P7: a11y lint — ARIA APG combobox + aria-live + focus-visible =="
"$PY" tools/a11y_lint.py

echo "== P7: RTL lint — logical-properties-only CSS =="
"$PY" tools/rtl_lint.py

echo "== P7: commands.md regeneration diff-clean (roster → doc, no hand drift) =="
"$PY" tools/descriptors_to_docs.py --check

echo "== P7: menu model — Tier-1 ≤9 + tier separation + golden diff =="
"$PY" tools/menu_model_check.py --check

echo "== P7: §10 coverage ratchet (every future surface maps to a command) =="
"$PY" tools/coverage_check.py

echo "== ALL GOVERNANCE CHECKS PASSED =="
