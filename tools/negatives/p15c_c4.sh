# tools/negatives/p15c_c4.sh — P15-CLOSE C4 negative (the A4 anchor upgrade).
# A planted upstream rename of one A4 anchor must redden the row with the
# runner's own P0 line; a silent skip would certify nothing.

case_p15c_a4_drift() {
  neg_expect_reject "A4: a renamed upstream anchor reddens the row (P0 before promotion)" \
    'P0 to @xr/platform BEFORE promotion lands' \
    "$PY" tools/assumption_drift_check.py --row A4 \
      --rename "ResetPermission=ResetPermissionForOrigin"
}
neg_register p15c_a4_drift
