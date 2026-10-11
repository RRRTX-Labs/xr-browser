# tools/negatives/p15c_c2.sh — P15-CLOSE C2 negatives (the permissions host).
# Each planted defect must redden its gate; a gate that passes a planted
# defect certifies nothing.

# --- C2: a clock read inside permissions/core/ reddens the clock-free row ----
case_p15c_core_clock() {
  local R
  R="$(mktemp -d "$NEG_TMP/p15c_clock.XXXXXX")"
  mkdir -p "$R/xr-core/permissions/core" "$R/xr-core/permissions/host"
  printf '// planted: the core reads the wall clock itself\n#include <chrono>\nlong Now() { return std::chrono::system_clock::now().time_since_epoch().count(); }\n' \
    > "$R/xr-core/permissions/core/ops.cc"
  # the host reading the clock is LEGAL (it owns the clock): only the core reddens
  printf '#include <chrono>\nlong HostNow() { return std::chrono::system_clock::now().time_since_epoch().count(); }\n' \
    > "$R/xr-core/permissions/host/permissions_host.cc"
  neg_expect_reject "clock-free law: a clock read inside permissions/core reddens" \
    'permissions/core/ops.cc:2 clock read inside core' \
    "$PY" tools/permission_write_path_check.py --root "$R"
}
neg_register p15c_core_clock

# --- C2: a host-vs-fake divergence reddens the parity replay ------------------
case_p15c_parity_divergence() {
  local R
  R="$(mktemp -d "$NEG_TMP/p15c_parity.XXXXXX")"
  sed 's/"bad-domain", s0, \[\]/"bad-origin", s0, []/' ../xr-core/fakes/permissions.py > "$R/permissions.py"
  neg_expect_reject "parity: a fake that drifts on one refusal token reddens" \
    'DIVERGE grant-url-refused' \
    "$PY" tools/permission_host_parity.py --fake "$R/permissions.py"
}
neg_register p15c_parity_divergence
