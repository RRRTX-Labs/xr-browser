# tools/negatives/p15c_c9.sh — P15-CLOSE C9 negative (invariant 7: no silent grant).
# The T7 usage-field and T4 full-origin negatives live in p15_permissions.sh
# (p15_usage, p15_origin); this adds the one the brief requires that was missing.

case_p15c_silent_grant() {
  neg_expect_reject "C9: a grant that lands in the store without its audit row reddens (count mismatch)" \
    'count mismatch' \
    "$PY" tools/permission_audit_count_check.py --xr-core ../xr-core --plant silent-grant
}
neg_register p15c_silent_grant
