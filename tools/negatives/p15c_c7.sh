# tools/negatives/p15c_c7.sh — P15-CLOSE C7 negative (the permission-prompt order patch).
# An upstream rename of the reordered call must stop the generator: the patch is
# bound to the pinned bytes, never fuzzily re-anchored.

case_p15c_patch_drift() {
  neg_expect_reject "C7: a planted anchor drift reddens permission_patch_roundtrip" \
    'anchor not found .upstream drift.' \
    "$PY" build/webui/permission_patch_roundtrip.py --xr-core ../xr-core --plant-drift
}
neg_register p15c_patch_drift
