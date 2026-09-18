# tools/checks/p12_gates.sh — the P12 gate sections of run_checks.sh.
#
# Same split-by-size-law reason as p11_gates.sh: run_checks.sh is the
# DISPATCHER and sits 4 lines under the 380-line touched-file ceiling, so new
# P12 gate bodies join here as functions called from the right point in the
# sequence. Sourced by tools/run_checks.sh; uses $PY and runs under the
# caller's `set -euo pipefail`, so an `exit 1` here ends the run.

p12_cosmetic_core_gates() {
  echo "== P12-T1: cosmetic core ↔ host ↔ fake parity (the living contract) =="
  # 200 golden vectors replayed byte-identically against BOTH the compiled
  # cosmetic_host and fakes/cosmetic.py. This is the check that stops the two
  # implementations from drifting, which is the failure a single-implementation
  # test cannot see.
  "$PY" tools/cosmetic_vectors_check.py --repo .

  echo "== P12-T1: scriptlet registry (admitted/refused, execution OFF) =="
  # The registry is the single source of truth for which scriptlets exist; the
  # checker also verifies the degrade corpus and the doc cover every admitted
  # name, so a registry row cannot be added without its degrade case and doc.
  "$PY" tools/scriptlet_registry_check.py --repo .

  echo "== P12-T3: generic hide set (budget + page-modifying count) =="
  "$PY" tools/cosmetic_generic_set_check.py --repo .
}

p12_cosmetic_seam_gates() {
  echo "== P12-T1: patch budget ledger (files declared == files touched) =="
  # The manifest caps how many upstream files each seam category may touch. It
  # is the only thing between a 12-file fork and a 900-file fork, and until P12
  # nothing verified it: a row could under-report its own diff and the cap
  # would never notice. Both directions are findings.
  "$PY" tools/patch_manifest_check.py --xr-core ../xr-core

  echo "== P12-T1: blink_seams guard lint (every hook behind #if defined(XR_…)) =="
  # An unguarded hook means the seam compiles into builds where the feature is
  # off, so the flag would gate the CALL but not the CODE. The lint reports the
  # counts because "hooks: 0, PASS" and "scanned nothing, PASS" must be
  # distinguishable.
  "$PY" tools/blink_guard_lint.py --repo . --xr-core ../xr-core

  echo "== P12-T1: cosmetic seam patch round-trip at the pin (real upstream fetch) =="
  # Fetches the pinned upstream files through build/upstream/fetch.py and
  # re-derives the patch: apply -> markers -> revert byte-exact -> a perturbed
  # anchor must FAIL to apply. This is also the only check that a hooked symbol
  # EXISTS at the pin; it is what caught patch 0300's first draft hooking
  # Document::ParseRootElementBeforeChildren, a function absent from Chromium
  # 152. It does NOT run gn, so no build is claimed by it.
  if "$PY" build/webui/cosmetic_seam_roundtrip.py --xr-core ../xr-core; then :
  elif [ $? -eq 77 ]; then
    echo "SKIP: cosmetic seam round-trip skipped (upstream fetch unavailable) — needed for: proving patch 0300 applies/reverts byte-exactly against the pinned Chromium bytes; local hint: re-run with network; the guard lint and the ledger check above still ran"
  else
    echo "FAIL: cosmetic seam round-trip gate failed"; die
  fi
}

p12_gates() {
  # The ONE call site run_checks.sh uses for every P12 feature gate. New P12
  # gates are added here, not to the dispatcher, because run_checks.sh is 4
  # lines under the 380-line touched-file ceiling and each dispatcher line is
  # permanent budget a later phase would have to find somewhere else.
  p12_cosmetic_core_gates
  p12_cosmetic_seam_gates
}
