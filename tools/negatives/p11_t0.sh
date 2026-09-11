# tools/negatives/p11_t0.sh — P11-T0 canaries: every new/extended gate must
# be able to turn red, and every canary is a registered case (counted, never
# hidden). Case numbers continue the derived count (P10 ended at 55).

# --- 56. host_protocol_check: a fifth host with methods and NO protocol doc --
case_host_protocol_undocumented_host() {
  local CORE="$NEG_TMP/core5"
  mkdir -p "$CORE/widget/host" "$CORE/policy/host"
  cat > "$CORE/widget/host/widget_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "spin") { return 0; }
  if (method == "stop") { return 1; }
  return 2;
}
CC
  cp ../xr-core/policy/host/policy_host.cc "$CORE/policy/host/" 2>/dev/null || true
  neg_expect_reject "host_protocol_check: undocumented host (no host_protocol.md)" \
    'widget.*does not exist|host_protocol.md does not exist' \
    "$PY" tools/host_protocol_check.py --xr-core "$CORE"
}
neg_register host_protocol_undocumented_host

# --- 57. parity_completeness: the same synthetic host is UNACCOUNTED --------
case_parity_completeness_unaccounted_host() {
  local CORE="$NEG_TMP/core5b"
  mkdir -p "$CORE/widget/host" "$CORE/policy/host"
  cat > "$CORE/widget/host/widget_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "spin") { return 0; }
  return 2;
}
CC
  cp ../xr-core/policy/host/policy_host.cc "$CORE/policy/host/" 2>/dev/null || true
  neg_expect_reject "parity_completeness: discovered host with no manifest pair" \
    'unaccounted host' \
    "$PY" tools/parity_completeness.py --repo . --xr-core "$CORE"
}
neg_register parity_completeness_unaccounted_host

# --- 58. host_protocol_check: source method missing from the table ----------
case_host_protocol_source_method_undocumented() {
  local CORE="$NEG_TMP/core5c"
  mkdir -p "$CORE/gadget/host"
  cat > "$CORE/gadget/host/gadget_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "real") { return 0; }
  if (method == "sneaked-in") { return 0; }
  return 2;
}
CC
  cat > "$CORE/gadget/host_protocol.md" <<'MD'
# gadget-host-protocol v1

ONE canonical JSON line (sorted keys, compact separators, non-ASCII
`\uXXXX`), exit `0` = typed result, `1` = typed error, `2` = usage.
Unknown methods are refused with `kUnknownMethod`.

## Methods

| method | args | result |
| --- | --- | --- |
| `real` | `{}` | ok |
MD
  neg_expect_reject "host_protocol_check: source literal absent from the table" \
    'sneaked-in' \
    "$PY" tools/host_protocol_check.py --xr-core "$CORE"
}
neg_register host_protocol_source_method_undocumented

# --- 59. host_protocol_check: table entry with no dispatching code ----------
case_host_protocol_phantom_table_row() {
  local CORE="$NEG_TMP/core5d"
  mkdir -p "$CORE/gadget2/host"
  cat > "$CORE/gadget2/host/gadget2_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "real") { return 0; }
  return 2;
}
CC
  cat > "$CORE/gadget2/host_protocol.md" <<'MD'
# gadget2-host-protocol v1

ONE canonical JSON line (sorted keys, compact separators, non-ASCII
`\uXXXX`), exit `0` = typed result, `1` = typed error, `2` = usage.
Unknown methods are refused with `kUnknownMethod`.

## Methods

| method | args | result |
| --- | --- | --- |
| `real` | `{}` | ok |
| `ghost` | `{}` | documented but never implemented |
MD
  neg_expect_reject "host_protocol_check: doc-only phantom method" \
    'ghost' \
    "$PY" tools/host_protocol_check.py --xr-core "$CORE"
}
neg_register host_protocol_phantom_table_row

# --- 60. host_protocol_check: response law not declared in the doc ----------
case_host_protocol_missing_response_law() {
  local CORE="$NEG_TMP/core5e"
  mkdir -p "$CORE/thin/host"
  cat > "$CORE/thin/host/thin_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "go") { return 0; }
  return 2;
}
CC
  cat > "$CORE/thin/host_protocol.md" <<'MD'
# thin-host-protocol v1

## Methods

| method | args | result |
| --- | --- | --- |
| `go` | `{}` | ok |
MD
  neg_expect_reject "host_protocol_check: response law undeclared" \
    'response law undeclared' \
    "$PY" tools/host_protocol_check.py --xr-core "$CORE"
}
neg_register host_protocol_missing_response_law

# --- 61. parity_completeness: phantom manifest pair (protocol, no host) -----
case_parity_completeness_phantom_pair() {
  local M="$NEG_TMP/manifest-phantom.json"
  "$PY" - "$M" <<'PY'
import json, sys
src = json.load(open("tools/parity/manifest.json"))
src["pairs"].append({"id": "ghosthost",
                     "protocol": "../xr-core/ghosthost/host_protocol.md",
                     "corpus": "tools/parity/corpus-update.json"})
json.dump(src, open(sys.argv[1], "w"))
PY
  neg_expect_reject "parity_completeness: manifest pair with no dispatching host" \
    'phantom pair' \
    "$PY" tools/parity_completeness.py --repo . --manifest "$M"
}
neg_register parity_completeness_phantom_pair

# --- 62. parity_completeness: a discovered host hiding behind covered_by ----
case_parity_completeness_exception_abuse() {
  local M="$NEG_TMP/manifest-excuse.json" CORE="$NEG_TMP/core5f"
  mkdir -p "$CORE/widget/host"
  cat > "$CORE/widget/host/widget_host.cc" <<'CC'
int Dispatch(const std::string& method) {
  if (method == "spin") { return 0; }
  return 2;
}
CC
  "$PY" - "$M" <<'PY'
import json, sys
src = json.load(open("tools/parity/manifest.json"))
src["pairs"] = [{"id": "widget", "protocol": None, "corpus": None,
                 "covered_by": "trust me"}]
json.dump(src, open(sys.argv[1], "w"))
PY
  neg_expect_reject "parity_completeness: method host may not claim covered_by" \
    'may not claim a covered_by exception' \
    "$PY" tools/parity_completeness.py --repo . --xr-core "$CORE" --manifest "$M"
}
neg_register parity_completeness_exception_abuse

# --- 63. no_new_crypto_check: a planted sixth copy of SHA-256 must redden ---
case_no_new_crypto_planted_copy() {
  local CORE="$NEG_TMP/core-crypto"
  mkdir -p "$CORE/common/core" "$CORE/evil/core"
  printf '// sanctioned\n' > "$CORE/common/core/sha256.cc"
  printf '// sanctioned\n' > "$CORE/common/core/sha256.h"
  printf '// sanctioned\n' > "$CORE/common/core/json.cc"
  printf '// sanctioned\n' > "$CORE/common/core/json_parse.cc"
  cat > "$CORE/evil/core/copy.cc" <<'CC'
#include <cstdint>
static const uint32_t H0 = 0x6a09e667u;  // a planted SHA-256 copy
CC
  neg_expect_reject "no_new_crypto_check: planted algorithm constants reddens" \
    'algorithm constant|single-copy law' \
    "$PY" tools/no_new_crypto_check.py --xr-core "$CORE"
}
neg_register no_new_crypto_planted_copy

# --- 64. no_new_crypto_check: undispositioned std::hash must redden ---------
case_no_new_crypto_std_hash() {
  local CORE="$NEG_TMP/core-hash"
  mkdir -p "$CORE/common/core" "$CORE/evil2/core"
  for f in sha256.cc sha256.h json.cc json_parse.cc; do
    printf '// sanctioned\n' > "$CORE/common/core/$f"
  done
  cat > "$CORE/evil2/core/h.cpp_hash.cc" <<'CC'
#include <functional>
#include <string>
size_t Fingerprint(const std::string& s) { return std::hash<std::string>{}(s); }
CC
  neg_expect_reject "no_new_crypto_check: std::hash without disposition reddens" \
    'std::hash without a recorded disposition' \
    "$PY" tools/no_new_crypto_check.py --xr-core "$CORE"
}
neg_register no_new_crypto_std_hash

# --- 65. workflow_grants: artifact '..' path must redden the lint ----------
# (T0-c: the PROVEN compat-beta-parity killer — run 34574063042, job
# 103182443929: "Invalid pattern '../xr-core/test/corpus/'. Relative pathing
# '.' and '..' is not allowed." — and NOT the brief's refuted actions:write
# hypothesis; the finding text must carry the run-id proof.)
case_workflow_grants_artifact_dotdot_path() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/dotdot.yml" <<'YML'
name: dotdot
on: workflow_dispatch
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 5
    steps:
      - uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5.0.0
        with:
          name: ev
          path: |
            ../xr-core/test/corpus/
YML
  neg_expect_reject "workflow_grants: artifact '..' path reddens (path law)" \
    'path law.*34574063042' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_grants_artifact_dotdot_path

# --- 66. workflow_grants: git push without contents:write must redden ------
case_workflow_grants_push_without_write() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/pushy.yml" <<'YML'
name: pushy
on: workflow_dispatch
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    timeout-minutes: 5
    steps:
      - run: |
          git push origin HEAD:refs/heads/scores
YML
  neg_expect_reject "workflow_grants: git push with contents:read reddens (rule B)" \
    'rule B' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_grants_push_without_write

# --- 67. workflow_grants: security-events over-grant must redden -----------
case_workflow_grants_overgrant_security_events() {
  local W="$NEG_TMP/.github/workflows"; mkdir -p "$W"
  cat > "$W/overgrant.yml" <<'YML'
name: overgrant
on: workflow_dispatch
jobs:
  j:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    timeout-minutes: 5
    steps:
      - run: echo hi
YML
  neg_expect_reject "workflow_grants: security-events:write with no codeql reddens (rule F)" \
    'rule F' \
    "$PY" build/workflow_lint.py --root "$NEG_TMP"
}
neg_register workflow_grants_overgrant_security_events

# --- 68. scheduled_lane_check: a red lane on its current definition must
#         redden (fixture mode — offline, deterministic, exit 1) ------------
case_scheduled_lane_check_red_lane() {
  cat > "$NEG_TMP/redlane.json" <<'JSON'
{
  "urls": {
    "https://api.github.com/repos/RRRTX-Labs/xr-browser/actions/workflows": {
      "workflows": [
        {"id": 9, "name": "redlane", "state": "active",
         "path": ".github/workflows/red.yml"}
      ]
    },
    "https://api.github.com/repos/RRRTX-Labs/xr-browser/actions/workflows/9/runs?per_page=30": {
      "workflow_runs": [
        {"id": 999, "event": "schedule", "status": "completed",
         "conclusion": "failure",
         "head_sha": "9999999999999999999999999999999999999999",
         "created_at": "2026-09-11T07:00:00Z"}
      ]
    }
  },
  "touches": {"red.yml": "2026-09-10T00:00:00+00:00"},
  "local": ["red.yml"]
}
JSON
  neg_expect_reject "scheduled_lane_check: red schedule run, no fix landed -> exit 1" \
    'FAIL: red.yml' \
    "$PY" tools/scheduled_lane_check.py --fixture "$NEG_TMP/redlane.json"
}
neg_register scheduled_lane_check_red_lane

# --- 69. scheduled_lane_check: discovering ZERO scheduled workflows must
#         redden (zero-case law — a discovery that finds nothing certifies
#         nothing; this repo has four scheduled lanes) ----------------------
case_scheduled_lane_check_zero_discovery() {
  mkdir -p "$NEG_TMP/emptyroot/.github/workflows"
  neg_expect_reject "scheduled_lane_check: zero scheduled workflows reddens" \
    'ZERO scheduled workflows' \
    "$PY" tools/scheduled_lane_check.py --repo "$NEG_TMP/emptyroot"
}
neg_register scheduled_lane_check_zero_discovery
