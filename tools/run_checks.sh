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
# P11-T0-d: the runner-capabilities ledger rule (e) consumes must itself obey
# the citation law — present claims cite real runs (ci_run+ci_job) or
# transcripts, UNOBSERVED entries say why, comment-claims are refused — and
# the self-test proves those refusals offline.
"$PY" tools/runner_caps.py --check
"$PY" tools/runner_caps.py --self-test

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

echo "== P11-T0-c: scheduled-lane health (a red nightly is a red check within a day) =="
# Reads the newest schedule-event run of every scheduled workflow through the
# fetch.py chokepoint. Network absent/rate-limited => visible SKIP (exit 77,
# skip-policy); the offline self-test runs FIRST so a SKIP can never mask a
# broken checker. A lane red on its CURRENT definition is a hard failure;
# STALE-FAIL/NOT-RUN/DISABLED are visible and non-fatal BY RULE.
"$PY" tools/scheduled_lane_check.py --self-test
if "$PY" tools/scheduled_lane_check.py; then :; elif [ $? -eq 77 ]; then
  echo "SKIP: SKIP (network unavailable for api.github.com) — needed for: scheduled-lane verdicts (silent-red-nightly visibility); local hint: re-run with network; the self-test above proved the checker itself"
else
  exit 1
fi

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
# P8-T5 gates (one l10n string source). xr_strings.grdp is the only place
# user-visible text may be authored; the extractor lint refuses raw literals
# in the views/payload and cross-checks every referenced id against the grdp.
# ---------------------------------------------------------------------------
echo "== P8-T5: l10n string source — xr_strings.grdp strict gate (schema ids, ph, desc, vocab, bidi, isolation-card) =="
"$PY" tools/grdp_check.py --ids-from-schema

echo "== P8-T5: raw-string lint — no user-visible literals outside ids (ui/ + payload), id cross-check =="
"$PY" tools/l10n_extract.py --check

# ---------------------------------------------------------------------------
# P9-T0-b (P8-T5 open item closed): deterministic qyy pseudo-locale render.
# Committed golden diff-check + self-test (canaries) + fixed-width law.
# ---------------------------------------------------------------------------
echo "== P9-T0-b: qyy pseudo-locale render (deterministic) + self-test =="
"$PY" tools/pseudo_locale.py --self-test
"$PY" tools/pseudo_locale.py --in ../xr-core/l10n/xr_strings.grdp \
  --out docs/qa/qyy/xr_strings.qyy.txt --as-of 2026-09-10 --check

# ---------------------------------------------------------------------------
# P8-T6 gate (attention-budget ledger v0 — local counters only). The policy
# doc is the statement of record that counters.h cites; the gate refuses a
# dangling citation or a drifted law (retention/granularity/no-upload).
# ---------------------------------------------------------------------------
echo "== P8-T6: attention-budget policy of record — local counters only, doc markers present =="
"$PY" -c "
import pathlib, re
p = pathlib.Path('docs/state/attention-budget.md')
t = re.sub(r'\s+', ' ', p.read_text(encoding='utf-8'))
need = ['no upload', 'LOCAL COUNTERS ONLY', '90', 'day', 'deny-preserve', 'zero bytes']
missing = [m for m in need if m not in t]
assert p.exists() and not missing, f'attention-budget.md missing or drifted: {missing}'
print('attention-budget OK (markers:', ', '.join(need) + ')')
"

# ---------------------------------------------------------------------------
# P8-T7 gate (help <-> settings deep-link contract). Schema sections and the
# registry must agree in both directions; the contract doc must keep citing
# both schemes (it is what the gate enforces).
# ---------------------------------------------------------------------------
echo "== P8-T7: help<->settings deep-link contract lint (schema <-> registry, both directions) =="
"$PY" tools/help_deep_link.py


# ---------------------------------------------------------------------------
# P6 gates (policy resolver v1). All offline except the C++ suite, which
# requires g++ and SKIPs VISIBLY when absent (skip-policy law) — the hosted
# lane has g++ and runs it for real.
# ---------------------------------------------------------------------------
echo "== P11-T0-b: no-new-crypto gate (ONE copy of a public algorithm, never a new one — ADR-0043) =="
"$PY" tools/no_new_crypto_check.py
"$PY" tools/no_new_crypto_check.py --self-test

echo "== P6: mode_lint — L3 one-brain ban + L13 intent headers =="
"$PY" tools/mode_lint.py --root ../xr-core

echo "== P6: policy.md regeneration diff-clean (generated, no hand drift) =="
"$PY" tools/vectors_to_md.py --check

echo "== P6: policy-change-event-v1 schema validates (incl. absence laws) =="
"$PY" tools/xr_schema.py validate policy-change-event docs/contracts/tests/golden-policy-change-event.json

echo "== P6/P7/P8/P9-T0-c: discovered C++ suite lanes (every xr-core/*/tests/Makefile) =="
# T0-c: the discovered set is the source of truth — no hand-written lanes
# (a hand-written list is exactly how settings/themes suites escaped the
# governance gate before). ci_lane_discovery runs every Makefile, fails on
# drift from docs/state/ci-lanes.json, and SKIPs visibly without g++/make.
"$PY" tools/ci_lane_discovery.py

# ---------------------------------------------------------------------------
# P7 gates (one command registry, four views, window-chrome skeleton). The C++
# commands core requires g++/make (SKIP-visibly when absent). The WebUI
# toolchain requires node/npm and SKIPs VISIBLY (exit 77) when the registry is
# unreachable — sources + config always ship (P7 #5 failure condition).
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# P8-T0 gates (added-file upstream debt). The canary that used to die at the
# 02:00 UTC nightly: a manifest entry that ADDS files (absent at the pin) was
# an unhandled 404. This lane runs the EXACT code path every push — real
# fetch.py classification from the pin to the pin (--to <chromium_rev>): a
# regression turns the governance gate red instead of a nightly.
# ---------------------------------------------------------------------------
echo "== T0: upstream added-file canary — live pin->pin classification (fetch.py) =="
CHROMIUM_REV="$(sed -n 's/^chromium_rev: \"\([0-9a-f]\{40\}\)\".*/\1/p' DEPS)"
if [ -n "$CHROMIUM_REV" ] && [ -d ../xr-core/patches ]; then
  "$PY" build/upstream/rebase_bot.py rebase --to "$CHROMIUM_REV" --dry-run --explain \
    --out "$(mktemp -d)/xr-t0-canary"
else
  echo "SKIP: SKIP (tool absent: ../xr-core sibling or DEPS chromium_rev) — needed for: the T0 live added-file canary (real fetch.py pin->pin classification); fixture coverage runs in pytest regardless"
fi

# ---------------------------------------------------------------------------
# P9-T0-a gates (byte-parity anti-drift). The parity-completeness gate fails
# when a host_protocol.md method has zero corpus cases (auto-discovered from
# the protocol table); the differential oracle runs BOTH backends on a seeded
# request stream and fails on any byte difference (g++ only; SKIPs visibly
# otherwise). Evidence runs use XR_DIFF_FUZZ_SECONDS=600.
# ---------------------------------------------------------------------------
echo "== P11-T0-a: host protocol doc gate (every method-dispatching host documented, both directions) =="
"$PY" tools/host_protocol_check.py

echo "== P9-T0-a: parity completeness (every protocol method has corpus cases) =="
"$PY" tools/parity_completeness.py

echo "== P9-T0-a: byte-differential fuzz (C++ host vs fake, seeded) =="
DIFF_FUZZ_SECONDS="${XR_DIFF_FUZZ_SECONDS:-120}"
if command -v g++ >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  "$PY" tools/differential_fuzz.py --timebox "$DIFF_FUZZ_SECONDS" \
    --min-iters 200 --seed 20260910
else
  echo "SKIP: SKIP (tool absent: g++/make) — needed for: the byte-differential oracle (compiled C++ hosts vs Python fakes); local hint: apt-get install g++ make (build-essential)"
fi

# ---------------------------------------------------------------------------
# P9-T1..T12 gates (Test & Benchmarking Infrastructure v1). Every runner's
# gate mode: canary + empty-input law. The fuzz fleet is wall-clock under the
# timebox law (>=60 s gate / >=600 s evidence via XR_FUZZ_SECONDS).
# ---------------------------------------------------------------------------
echo "== P9-T1: browser-test fixture lint (fixtures are the spec) =="
"$PY" tools/browser_test_lint.py --repo .

echo "== P9-T2: isolation-matrix fake cells (identity x mechanism) =="
"$PY" tools/isolation_matrix.py --repo . --check

echo "== P9-T3: leaktest self-test + loopback canary (0 leaks) =="
"$PY" tools/leaktest.py --repo . --self-test
"$PY" tools/leaktest.py --repo . --mode loopback

echo "== P9-T4: compat corpus validate + offline replay =="
"$PY" tools/compat.py --repo . validate
"$PY" tools/compat.py --repo . replay

echo "== P9-T5: perf budgets (plan-transcribed, diff-clean) + gate =="
"$PY" build/qa/perf/gen_perf_budgets.py --repo . --check
"$PY" tools/perf_gate.py --repo . --bench docs/state/bench-trend.json \
  --check --as-of 2026-09-10

echo "== P9-T6: visual-diff stdlib engine self-test =="
"$PY" tools/visual_diff.py --self-test

echo "== P9-T7: npm allowlist + copy lint + AXTree snapshot + keyboard tasks =="
"$PY" tools/npm_allowlist_check.py --repo .
"$PY" tools/copy_lint.py --repo .
"$PY" tools/a11y_tree.py --repo . --check
"$PY" tools/keyboard_tasks_check.py --repo .

echo "== P9-T8: fuzz corpus seeds + contract generator + fleet (timebox law) =="
"$PY" tools/seed_corpus.py --repo . --check
"$PY" tools/mojom_fuzz_gen.py --repo . --count 1000 --seed 20260910
if command -v g++ >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  "$PY" tools/fuzz_fleet.py --repo . --timebox 60
else
  echo "SKIP: SKIP (tool absent: g++/make) — needed for: the four in-house fuzz targets; local hint: apt-get install g++ make (build-essential)"
fi

echo "== P9-T9: SAST rule registry (canary + real-tree clean) =="
"$PY" tools/sast_check.py --repo .

echo "== P9-T10/T11: drill matrices (kill matrix + update drill, complete) =="
"$PY" tools/drill_check.py --repo .

echo "== P10-T0-c: mutation freshness (a stale score is a FAIL, not a note) =="
"$PY" tools/mutation_freshness.py --repo .

echo "== P10-T1: update golden vectors, cross-backend BYTE parity (73 cases) =="
"$PY" tools/update_vectors_check.py --repo .

echo "== P10-T1: std-only core import hygiene (no Chromium includes in core/**) =="
"$PY" tools/core_hygiene_check.py --xr-core ../xr-core

echo "== P10-T2: update-server spec + conformance (reference) + fuzz + size =="
for contract in server-version-graph:version-graph server-channels:channels server-cohorts:cohorts server-epochs:epochs; do
  "$PY" tools/xr_schema.py validate "${contract%%:*}" "release/server/spec/${contract##*:}.yaml"
done
"$PY" release/server/refimpl/update_server_ref.py --self-check
"$PY" release/server/refimpl/update_server_ref.py --gen-spec-readme --check
"$PY" tools/gen_server_spec_rs.py --check
"$PY" release/server/tests/gen_conformance.py
"$PY" release/server/tests/test_conformance_ref.py
XR_FUZZ_SECONDS="${XR_FUZZ_SECONDS:-30}" "$PY" release/server/tests/test_server_fuzz.py
"$PY" tools/server_size_check.py

echo "== P10-T5/T7/T8: rollout drill + claims/notes + about-state coverage =="
"$PY" tools/rollout_drill.py
"$PY" tools/release_notes.py --train 152 --out release/notes/train-152.md --check
"$PY" tools/claims_lint.py
"$PY" tools/about_state_check.py

echo "== P10-T3: key-ceremony docs + the both-repos secret absence proof =="
"$PY" tools/secret_scan.py --all
"$PY" tools/ceremony_check.py

echo "== P10-T4: signing matrix (gpg REAL in sandbox; argv-exact mac/win) =="
if bash build/signing/tests/test_signing_p10.sh; then :; elif [ $? -eq 77 ]; then
  echo "SKIP: signing matrix skipped (gpg absent)"
else
  echo "FAIL: signing matrix gate failed"; exit 1
fi
"$PY" tools/packaging_matrix_check.py

echo "== P10-T7: license report + unknown-license-fails-build law =="
"$PY" build/sbom/license_report.py

echo "== P10-T9: release gate (dev green on synthetic; beta/stable MUST fail closed) =="
"$PY" tools/release_gate.py check --channel dev --artifact work/release-check/synthetic-artifact.bin
if "$PY" tools/release_gate.py check --channel beta >/dev/null 2>&1; then
  echo "FAIL: release check --channel beta PASSED without credentials — the gate is broken"; exit 1
else
  echo "ok: release check --channel beta exits non-zero (fail-closed, missing items enumerated)"
fi
if "$PY" tools/release_gate.py check --channel stable >/dev/null 2>&1; then
  echo "FAIL: release check --channel stable PASSED without credentials — the gate is broken"; exit 1
else
  echo "ok: release check --channel stable exits non-zero (fail-closed, missing items enumerated)"
fi

echo "== P10-T0-b: kill matrix, hosts-local EXECUTION (the P9 deferral closed) =="
if bash build/qa/drill/drill_run.sh hosts-local; then :; elif [ $? -eq 77 ]; then
  echo "SKIP: kill matrix hosts-local skipped (g++/make absent) — needed for: executing the kill matrix against the discovered //xr host binaries"
else
  echo "FAIL: kill matrix hosts-local gate failed"; exit 1
fi

echo "== P9-T12: §11 surface completeness (every surface homed) =="
"$PY" tools/surfaces_check.py --repo .

echo "== P9 meta: mutation-check the checker (3 runners, defect must escape) =="
"$PY" build/qa/tools/test_checker_mutation.py --repo .

echo "== ALL GOVERNANCE CHECKS PASSED =="
