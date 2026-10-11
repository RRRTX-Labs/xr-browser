# shellcheck shell=bash
# tools/negatives/p15c_c8.sh — P15-CLOSE C8 negatives: the permission-overlay
# isolation cells (tools/permission_iso_cells.py, run by isolation_matrix.py).
# Fixtures live in a per-case mktemp -d (neg_case_dir); the sibling is only read.

case_p15c_perm_leak() {
  neg_expect_reject "C8: an overlay that ignores identity (planted leak) reddens the permission cells" \
    'FAIL: permissions-grant-scope .* standard/fortress: grant in A visible in B: True' \
    "$PY" tools/permission_iso_cells.py --xr-core ../xr-core --plant leak
}
neg_register p15c_perm_leak

case_p15c_perm_empty_run() {
  local W
  W="$(neg_case_dir p15c-c8-empty)"
  grep -v '^  - id: permissions-\(grant\|revoke\|deny\|audit\)' \
    ../xr-core/test/isolation/matrix.yaml >"$W/matrix.yaml"
  neg_expect_reject "C8: a matrix with no fake permission cells executes nothing and reddens (empty-run law)" \
    'executed 0 cells .empty-run law.' \
    "$PY" tools/permission_iso_cells.py --xr-core ../xr-core --matrix "$W/matrix.yaml"
}
neg_register p15c_perm_empty_run

case_p15c_perm_method_missing() {
  local W
  W="$(neg_case_dir p15c-c8-method)"
  sed 's|browser-harness.md#p15-t5-revoke-propagation|browser-harness.md#p15-no-such-method|' \
    ../xr-core/test/isolation/matrix.yaml >"$W/matrix.yaml"
  neg_expect_reject "C8: a browser cell whose method anchor does not exist reddens isolation_matrix" \
    'method anchor #p15-no-such-method not found' \
    "$PY" tools/isolation_matrix.py --repo . --matrix "$W/matrix.yaml" --check
}
neg_register p15c_perm_method_missing
