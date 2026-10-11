# tools/checks/p15_gates.sh — the P15 permission-firewall gate lanes (ADR-0051).
#
# Same split-by-size-law reason as p9..p14_gates.sh: run_checks.sh is held at
# its 380-line touched-file ceiling, so the bodies live here. Sourced by
# tools/run_checks.sh; nothing here runs unless called.
#
# The C++ suite (xr-core/permissions/tests) is NOT listed here: ci_lane_discovery
# finds its Makefile and records the lane in docs/state/ci-lanes.json. The
# attention rule for permission prompts rides on the existing attention_check
# lane (P15-T7 markers and surface scan live in tools/attention_check.py).

p15_lanes() {
  echo "== P15-T4: permission contract (frozen bytes, audit golden, overlay vectors) =="
  "$PY" tools/permission_contract_check.py

  echo "== P15-T9.2: write-path law (overlay mutators confined to xr-core/permissions/) =="
  "$PY" tools/permission_write_path_check.py

  echo "== P15-CLOSE C4: A4 anchors — offline positive control (the live read is assumptions.py run) =="
  "$PY" tools/assumption_drift_check.py --row A4

  echo "== P15-CLOSE C6: permission-prompt keyboard tasks (own law; the 12-task law is untouched) =="
  "$PY" tools/keyboard_tasks_permissions_check.py --repo . --xr-core ../xr-core

  echo "== P15-CLOSE C7: permission-prompt order patch 0400 round-trips at the pin (regenerate + byte-compare) =="
  "$PY" build/webui/permission_patch_roundtrip.py --xr-core ../xr-core --check

  echo "== P15-CLOSE C9: invariant 7 — every overlay change leaves exactly one audit row (no silent grant) =="
  "$PY" tools/permission_audit_count_check.py --xr-core ../xr-core

}
