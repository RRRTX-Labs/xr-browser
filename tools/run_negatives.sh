#!/usr/bin/env bash
# run_negatives.sh — proof that the P1 gates fail on bad input.
#
# Plan P1 "Tests": "license-scan fails on an injected GPL sample; DCO
# bot blocks unsigned PR." Extended: every gate gets a negative case.
# Each case builds a minimal fixture in a scratch area and asserts the
# tool exits 1 WITH the expected reason (a gate that rejects for the
# wrong reason still fails this script).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAILURES=0

# expect_reject <description> <expected-output-pattern> <cmd...>
expect_reject() {
  local desc="$1" pattern="$2"
  shift 2
  local out rc
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: $desc — gate PASSED on bad input (rc=0)"
    FAILURES=1
  elif ! printf '%s' "$out" | grep -qE "$pattern"; then
    echo "NEGATIVE-FAIL: $desc — rejected, but not for the expected reason"
    printf '%s\n' "$out" | sed 's/^/    | /'
    FAILURES=1
  else
    echo "ok: $desc (rejected with expected reason)"
  fi
}

# --- 1. license: injected GPL sample (Plan P1 DoD) -------------------------
L="$TMP/lic"; mkdir -p "$L/docs/state" "$L/src"
cp LICENSE "$L/LICENSE"
printf 'schema_version: 1\nallowlist: []\n' > "$L/docs/state/license-allowlist.yaml"
cp tools/tests/fixtures/gpl-sample.py "$L/src/injected.py"
expect_reject "license: injected GPL sample in code" \
  'src/injected\.py.*General Public License' \
  "$PY" tools/license_audit.py --repo "$L"

# --- 2. DCO: unsigned commit (Plan P1 DoD) ----------------------------------
D="$TMP/dco"; mkdir -p "$D"; cd "$D"
git init -q -b main .
git config user.name "Nevil N"
git config user.email "nevil@example.invalid"
echo 1 > f.txt
git add f.txt
git commit -q -m "chore: unsigned"
cd - >/dev/null
expect_reject "dco: unsigned commit" \
  'missing Signed-off-by' \
  "$PY" tools/dco_check.py --repo "$D"

# --- 3. registry: hand-edited feature row -----------------------------------
R="$TMP/drift"
cp -r . "$R"
rm -rf "$R/.git"
"$PY" - "$R" <<'EOF'
import sys, yaml
root = sys.argv[1]
p = f"{root}/docs/registry/features.yaml"
d = yaml.safe_load(open(p))
d["features"][0]["feature"] += " (hand edit)"
yaml.safe_dump(d, open(p, "w"), sort_keys=False, allow_unicode=True)
EOF
expect_reject "registry: hand-edited features.yaml" \
  'features\.yaml\[0\].*feature' \
  "$PY" tools/registry_lint.py --repo "$R"

# --- 4. vocab: new banned word in fresh doc ---------------------------------
V="$TMP/vocab"; mkdir -p "$V/docs/state"
cp docs/state/vocab-allowlist.yaml "$V/docs/state/"
printf 'Our stealth mode is unbreakable.\n' > "$V/docs/marketing.md"
expect_reject "vocab: banned words in new doc" \
  'marketing\.md:1: banned pattern' \
  "$PY" tools/vocab_lint.py --repo "$V"

# --- 5. register: bad status enum -------------------------------------------
G="$TMP/reg"; mkdir -p "$G/docs/register"; cd "$G"
git init -q -b main .
git config user.name "Nevil N"
git config user.email "nevil@example.invalid"
"$PY" - <<'EOF'
import yaml
rows = [
    {"id": f"DR-{n:02d}", "title": f"t{n}", "status": "APPROVED",
     "rationale": "r", "linked_lg": [], "reopen_condition": "rc",
     "phase_anchor": "P1"}
    for n in range(1, 31)
]
yaml.safe_dump({"schema_version": 1, "plan_sha256": "a" * 64,
                "decisions": rows},
               open("docs/register/decisions.yaml", "w"), sort_keys=False)
EOF
cd - >/dev/null
expect_reject "register: invalid status enum" \
  'status .APPROVED. not in' \
  "$PY" tools/dr_parse.py --repo "$G"

# --- 6. threat model: emptied honesty cell ----------------------------------
T="$TMP/tm"; mkdir -p "$T/docs"
"$PY" - "$T" <<'EOF'
import sys, hashlib, re
root = sys.argv[1]
plan = "# plan (negative fixture)\n"
open(f"{root}/docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md", "w").write(plan)
sha = hashlib.sha256(plan.encode()).hexdigest()
src = open("docs/threat-model.md").read()
# swap in this fixture's plan sha
src = re.sub(r"[0-9a-f]{64}", sha, src, count=1)
# empty the T2 row's honesty cell (last pipe-cell of the line starting "| T2 ")
def blank_last_cell(m):
    line = m.group(0)
    return line.rsplit("|", 2)[0] + "| — |"
src = re.sub(r"^\| T2 \|.*\|\n", blank_last_cell, src, count=1, flags=re.MULTILINE)
open(f"{root}/docs/threat-model.md", "w").write(src)
EOF
expect_reject "threat model: emptied honesty cell (T2)" \
  'adversary T2: .Does NOT protect against. cell is empty' \
  "$PY" tools/check_threat_model.py --repo "$T"

# --- 7. plan pin: tampered plan copy -----------------------------------------
P="$TMP/pin"; mkdir -p "$P/docs"
cp docs/master-plan.sha256 "$P/docs/"
cp docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md "$P/docs/"
printf 'tampered\n' >> "$P/docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
expect_reject "plan pin: tampered plan copy" \
  'plan pin mismatch' \
  "$PY" tools/plan_pin_check.py --repo "$P"

echo
if [ "$FAILURES" -ne 0 ]; then
  echo "NEGATIVE GATE FAILED: at least one gate accepted bad input or failed for the wrong reason"
  exit 1
fi
echo "ALL NEGATIVE CASES REJECTED AS EXPECTED"
