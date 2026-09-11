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
