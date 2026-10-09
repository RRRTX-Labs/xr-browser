# tools/negatives/p15_permissions.sh — P15 negative cases (ADR-0051). Each
# planted defect must redden its gate; a gate that passes a planted defect
# certifies nothing.

# --- P15-T4: a full origin in an audit row is refused (not truncated) --------
case_p15_origin() {
  neg_expect_inband "permission contract: a full origin in an audit row reddens" \
    'reddened \(origin' \
    "$PY" tools/permission_contract_check.py --fixture origin
}
neg_register p15_origin

# --- P15-T4: a usage field in the audit row is refused (no such field) -------
case_p15_usage() {
  neg_expect_inband "permission contract: a planted usage field reddens" \
    'reddened \(\$\.usage_active' \
    "$PY" tools/permission_contract_check.py --fixture usage
}
neg_register p15_usage

# --- P15-T9.2: a renderer-side mutator call is a second write path -----------
case_p15_write_path() {
  local R="$NEG_TMP/p15wp"
  rm -rf "$R"; mkdir -p "$R/xr-core/permissions/core" "$R/xr-core/renderer"
  printf '// stub owner: the write path has an owner\n' > "$R/xr-core/permissions/core/ops.cc"
  printf '// planted: a renderer-side write path\n#include "permissions/core/ops.h"\nvoid Evil() { GrantTemp(store, req, 1); }\n' \
    > "$R/xr-core/renderer/evil.cc"
  neg_expect_reject "write-path law: a renderer-side GrantTemp call reddens" \
    'second write path' \
    "$PY" tools/permission_write_path_check.py --root "$R"
}
neg_register p15_write_path

# --- P15-T7: a permission surface carrying escalation vocabulary reddens -----
case_p15_attention() {
  local F="$NEG_TMP/p15_planted_present.h"
  printf '// planted: a permission prompt that escalates\nvoid Show() { /* a modal dialog */ }\n' > "$F"
  neg_expect_inband "attention rule: a modal permission surface reddens" \
    'reddened \(p15_planted_present' \
    "$PY" tools/attention_check.py --fixture-permission "$F"
}
neg_register p15_attention
