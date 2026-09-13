# tools/negatives/p11_t10.sh — P11 DoD-10 negative cases: the shield
# network-seam round-trip must REFUSE a payload path outside
# services/network/** (never-list) and must REFUSE to grow past the
# <=8-file hook budget. Both refusals fire BEFORE any network fetch, so
# these cases stay hermetic.

_p11t10_fixture() {
  # $1 = fixture xr-core root; $2... = payload relative paths to create
  local root="$1"; shift
  mkdir -p "$root"
  local rel
  for rel in "$@"; do
    mkdir -p "$root/patches/network-seams/0200-shield-network-seam/payload/$(dirname "$rel")"
    echo "// fixture payload $rel" > "$root/patches/network-seams/0200-shield-network-seam/payload/$rel"
  done
}

neg_register p11_seam_neverlist
case_p11_seam_neverlist() {
  local fix; fix="$(mktemp -d)"
  # a payload file rooted in content/browser/** — the §12.7 never-list side
  _p11t10_fixture "$fix/xr-core" \
    "services/network/xr/xr_shield_gate.h" \
    "services/network/xr/xr_shield_gate.cc" \
    "content/browser/xr/evil_hook.cc"
  neg_expect_reject \
    "shield_seam_roundtrip: a payload path outside services/network/** (never-list) reddens" \
    "never-list refusal|payload path outside" \
    "$PY" build/webui/shield_seam_roundtrip.py --xr-core "$fix/xr-core"
  rm -rf "$fix"
}

neg_register p11_seam_hook_budget
case_p11_seam_hook_budget() {
  local fix; fix="$(mktemp -d)"
  # 3 upstream hooks + 7 payload files = 10 > the DoD-10 cap of 8
  _p11t10_fixture "$fix/xr-core" \
    "services/network/xr/xr_shield_gate.h" \
    "services/network/xr/xr_shield_gate.cc" \
    "services/network/xr/extra_a.cc" \
    "services/network/xr/extra_b.cc" \
    "services/network/xr/extra_c.cc" \
    "services/network/xr/extra_d.cc" \
    "services/network/xr/extra_e.cc"
  neg_expect_reject \
    "shield_seam_roundtrip: a seam growing past the <=8-file hook budget reddens" \
    "hook budget blown" \
    "$PY" build/webui/shield_seam_roundtrip.py --xr-core "$fix/xr-core"
  rm -rf "$fix"
}
