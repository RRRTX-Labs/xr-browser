# tools/checks/p13_gates.sh — the P13 gate sections of run_checks.sh.
#
# Same split-by-size-law reason as p9_gates.sh / p11_gates.sh / p12_gates.sh:
# the dispatcher sits at the <=380-line touched-file ceiling, so P13's gates
# live here as functions called from the right point in the sequence. Sourced
# by tools/run_checks.sh; uses $PY and $RANGE, and runs under the caller's
# `set -euo pipefail` (an `exit 1` here ends the run, exactly as an inline
# block would).

p13_evidence_bundles() {
  # The bundle lane (P13-P0-C, moved out of run_checks.sh by the size law).
  # Contract: docs/contracts/evidence-bundle-v1.md. Two invocations, one law:
  #   * the DEFAULT run is what CI does on every push — strict over every phase
  #     newer than the P2 legacy exemption, with the declared in-flight phase
  #     allowed to be `state: "interim"`;
  #   * `run_checks.sh --phase-final` is the CLOSING run — the in-flight phase
  #     must be final too (report.md, a declared head, a same-head ci-run row
  #     per claimed workflow). That is the invocation the phase's final commit
  #     and the clean-clone gate record use, so "close the phase" cannot happen
  #     with sentinels still standing.
  echo "== evidence bundles (contract: docs/contracts/evidence-bundle-v1.md) =="
  "$PY" tools/evidence_check.py
  # strict: auto-covers every bundle newer than the P2 legacy exemption (P3+);
  # P1/P2 stay exempt per the HG-25 ruling (no hardcoded list to forget, T0).
  # T0-U2: phase_head bundles print both heads compared (`head-match:` lines).
  if [ "${PHASE_FINAL:-0}" = "1" ]; then
    echo " (--phase-final: the declared in-flight phase must be final too)"
    "$PY" tools/evidence_check.py --strict --require-phase-final
  else
    "$PY" tools/evidence_check.py --strict
  fi
}

p13_p0_gates() {
  # P0-A: the index-mode law, in both of its forms.
  #   Law 1 — every workflow-invoked DIRECT entry point is 100755 in the index
  #           (`bash`/`python3 <path>` are exempt, and the tool says so in its
  #           own output rather than silently passing them);
  #   Law 2 — no commit in the pushed range drops an exec bit (--range). The
  #           5e3d1d4 class, caught at push time with the commit named.
  echo "== P13-P0-A: workflow entry-point modes (index 100755 for direct exec) + mode-drift law =="
  if [ -n "$RANGE" ]; then
    "$PY" tools/entrypoint_mode_check.py --repo . --range "$RANGE"
  else
    "$PY" tools/entrypoint_mode_check.py --repo .
  fi
  echo "== P13-P0-A: in-place rewrites preserve the mode (the defect shape loses it) =="
  "$PY" tools/inplace.py --self-test

  # P0-B: the diagnosis path. The triage tool's self-test is offline and
  # fixture-backed, so this lane never needs the network; the live endpoint set
  # is exercised by the scheduled-lane checker and by the hosted call in the
  # phase report.
  echo "== P13-P0-B: CI triage reads the public check-run/annotation endpoints (offline self-test) =="
  "$PY" tools/ci_triage.py --self-test

  # P0-C: the phase-finality law. The self-test proves each rule bites offline
  # (final vocabulary + PENDING, append-only corrections, report.md, in-flight
  # interim, invented states, pre-law scoping); the live judgement runs in the
  # evidence-bundle section above via --require-phase-final, so a bundle that
  # regresses reddens on the bundle line, not here.
  echo "== P13-P0-C: phase-finality law (state interim|final; the 12-section report) =="
  "$PY" tools/evidence_finality.py --self-test
}

p13_exit_code_lane() {
  # The SKIP law, in ONE place, and testable (P13-C-P0.6).
  #
  # <label> <skip-reason> <cmd...>: run a node/toolchain lane whose exit code is
  # part of its contract — 0 pass, 77 "the environment is not here" (a visible
  # skip, never a silent pass), anything else FAIL. The shape it replaces was
  # `if cmd; then :; elif [ $? -eq 77 ]; then …` which is one deleted `else`
  # away from turning a broken lane into a green one, and it read `$?` out of a
  # `then :` branch to do it.
  #
  # The command is an ARGUMENT rather than a hardcoded path so
  # tools/negatives/p13_c06.sh can drive all three exit codes against scratch
  # scripts; a gate passes the real path, and no environment variable can move
  # it. Returns nonzero via `die` for the FAIL case, exactly as an inline
  # `else … die` did under the caller's `set -euo pipefail`.
  local label="$1" skip="$2" rc=0
  shift 2
  "$@" || rc=$?
  case "$rc" in
    0) return 0 ;;
    77) echo "SKIP: $label skipped ($skip)" ;;
    *) echo "FAIL: $label failed (exit $rc)"; die ;;
  esac
}

p13_t1_panel_gates() {
  # P13-T1: the panel frame. Two halves, and both are the point:
  #   * the focus-containment suite (node:test against the bundled core) — the
  #     positive laws AND a planted leak inside the same file;
  #   * `--plant-leak`, which deletes containment in a scratch copy and REQUIRES
  #     the suite to redden. A lane that cannot fail proves nothing, and a focus
  #     trap is the shape of code whose test passes while containing nothing.
  # The DOM-facing half is `tsc --strict` (ui/panel/*.ts is in the toolchain
  # include) + the farm; browser halves are NOT-RUN with methods in
  # docs/qa/browser-harness.md. Node/registry absent => visible SKIP (77).
  echo "== P13-T1: panel focus containment (real suite + planted leak must redden) =="
  p13_exit_code_lane "panel focus-containment lane" \
    "node/toolchain unavailable" bash build/webui/panel-tests.sh
  p13_exit_code_lane "panel planted-leak lane" \
    "node/toolchain unavailable" bash build/webui/panel-tests.sh --plant-leak
}

p13_t7_panel_perf_gates() {
  # P13-T7: the panel's perf lane, in the two halves the law allows.
  #   * the budget rows may come ONLY from build/qa/perf/gen_perf_budgets.py
  #     (transcribed from the pinned plan; --check is diff-clean or the gate
  #     fails — a hand-authored number is a falsification);
  #   * the measurable-in-sandbox half is the frame's pure core, measured by
  #     tools/panel_bench.py as a SURROGATE (`surrogate: true`, rig_class
  #     trend, never MET). Measuring is best-effort (node/toolchain absent =>
  #     visible SKIP); the committed trend rows are checked deterministically.
  # The browser halves (open ≤150 ms, ring ≤16 fps) are NOT-RUN with their
  # methods in docs/qa/browser-harness.md — no surrogate dresses as the rig.
  # (The budget rows themselves are checked by the P9-T5 lane above, which owns
  #  gen_perf_budgets --check; this lane owns the panel's own two halves.)
  echo "== P13-T7: panel frame bench (surrogate, trend rig — never MET) =="
  p13_exit_code_lane "panel bench" \
    "node/toolchain unavailable (sources shipped)" "$PY" tools/panel_bench.py
  "$PY" tools/panel_bench.py --check
}

p13_l10n_count_law() {
  # P13-C-P0.1c: the derived-count law. Two derived quantities, never a literal:
  #   1. the count tools/grdp_check.py REPORTS, parsed out of its own stdout;
  #   2. an INDEPENDENT count of <message> elements in the same .grdp;
  # and then (2) against the grow-only ratchet docs/qa/l10n-ratchet.json.
  #
  # The tool's stdout is CAPTURED to a file and handed to the checker, never
  # piped: a verdict may not ride a pipeline exit code (tools/negatives/lib.sh
  # was fixed for exactly this in f969499), and a captured transcript is what
  # makes the stale-count failure testable — feeding a STALE transcript is the
  # registered negative (tools/negatives/p13_c01c.sh).
  #
  # What this replaced, verbatim from tools/tests/test_p8_t5_l10n.py:48 at
  # e503f9e:  assert "OK (127 messages" in r.stdout  # P11-T6: +36; P12-T6: +14
  # The tool was green at 136 while the literal still said 127. The number is
  # not refreshed here; it does not exist any more. See docs/process/gate-law.md
  # ("a verdict-bearing assertion compares derived values, never an embedded
  # number") — this repo has now re-found that defect three times (P10's
  # perf-budgets hand-edit refusal, P13-P0-C's negatives count, here).
  local grdp="../xr-core/l10n/xr_strings.grdp" out
  out="$(mktemp)"
  if ! "$PY" tools/grdp_check.py --ids-from-schema >"$out"; then
    echo "FAIL: grdp_check (strict xr_strings.grdp gate) — see its stderr above"
    rm -f "$out"; die
  fi
  cat "$out"
  "$PY" tools/l10n_count_law.py --grdp "$grdp" --tool-stdout "$out" --check || {
    rm -f "$out"; die
  }
  rm -f "$out"
}

p13_sibling_pin() {
  # P13-C-P0.2: the cross-repo pin law, run BEFORE every lane that consumes the
  # sibling. A verdict computed from a sibling checkout is meaningless unless
  # the sibling is at the pin; this lane proves it (present, HEAD ==
  # DEPS.xr_core_rev, worktree clean) or refuses with BLOCKED-LAYOUT /
  # STALE-SIBLING / DIRTY-SIBLING and exit 2 — never an ImportError, and never
  # a vacuous pass. It also audits the register: every file that resolves a
  # sibling path must be routed through tools/xr_sibling.py or classified with
  # a reason, so the class cannot grow back silently.
  # Docs: docs/process/cross-repo-pin.md.
  echo "== P13-C-P0.2: cross-repo pin (sibling present, at DEPS.xr_core_rev, clean) + the resolver register =="
  "$PY" tools/sibling_pin_check.py --repo .
}

p13_c2_observatory_gates() {
  # P13-T3: the Observatory's export law — redaction is CONTRACT, and the point
  # of the lane is not "there is a redaction function" but "the refused bytes
  # never reach the writer". The tool's --check runs the smuggle corpus (query
  # params, fragments, user:pass@, cookies, UA strings, selector text), asserts
  # each refusal class by name, and byte-compares the exporter's output for the
  # committed golden block-event row — the row the C++ core emits and the Python
  # fake reproduces byte-for-byte.
  #
  # Python stdlib only and offline, so there is no SKIP path: this lane either
  # runs or the tree is broken.
  echo "== P13-T3: observatory export (redaction contract + smuggle corpus) =="
  "$PY" tools/observatory_export.py --check
}

p13_c3_breakage_gates() {
  # P13-T4: the breakage report. The lane runs the vector suite: two accepted
  # payloads that must validate, and eight refusals that must be refused WITH
  # their class named (an extra `html` field, a missing required block, an origin
  # carrying a path, a note carrying a URL/query, a cookie, a UA string, selector
  # text, and `queue: "live"`).
  #
  # Nothing here touches the network: the report path has no transport in this
  # repository, on purpose (docs/panel/breakage-report.md). Live filing is
  # HUMAN-GATED, the queue is a local fixture tree labelled `fixture` in its path
  # and in this tool's stdout, and no median is computed anywhere.
  echo "== P13-T4: breakage report vectors (refusals pre-send, queue: fixture only) =="
  "$PY" tools/breakage_report.py --check
}

p13_c5_registry_gates() {
  # P13-T6: the tab registry's gate half. The runtime half (ui/panel/
  # tab-registry.ts: unknown-tab-id / order-collision / order-mismatch /
  # duplicate-id, all typed) is proven by the node suite inside
  # build/webui/panel-tests.sh; this lane proves the contract half, which a
  # hand-edited JSON could otherwise walk past: the inventory validates against
  # panel-tab-registration-v1, the vector file is EXECUTED (an accept payload
  # the schema refuses reddens), every tab title msgid exists in the sibling's
  # grdp, every declared tab CLAIMS its implementation (`skip:` is not a claim),
  # and no frame names a tab id as a literal (the bypass law).
  #
  # Runs beside tools/coverage_check.py above: coverage_check owns the
  # inventory↔allowlist bijection and the roster half of §10, this lane owns the
  # claim, the schema, the grdp and the bypass. One law, one home.
  echo "== P13-T6: panel tab registry (inventory ↔ schema ↔ vectors ↔ grdp ↔ allowlist claim) =="
  "$PY" tools/panel_registry_check.py --repo .
}
