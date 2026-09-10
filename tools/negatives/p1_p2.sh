# tools/negatives/p1_p2.sh — P1/P2 gate negatives (license, DCO, registry,
# vocab, decision register, threat model, plan pin). P9-T0-d split.
#
# Each case is a function registered via neg_register; the dispatcher runs
# them and counts them (N is derived, never hard-coded). Fixtures build
# inside the function so SOURCING this file has no side effects.

# --- 1. license: injected GPL sample (Plan P1 DoD) -------------------------
case_license_gpl() {
  local L="$NEG_TMP/lic"; mkdir -p "$L/docs/state" "$L/src"
  cp LICENSE "$L/LICENSE"
  printf 'schema_version: 1\nallowlist: []\n' > "$L/docs/state/license-allowlist.yaml"
  cp tools/tests/fixtures/gpl-sample.py "$L/src/injected.py"
  neg_expect_reject "license: injected GPL sample in code" \
    'src/injected\.py.*General Public License' \
    "$PY" tools/license_audit.py --repo "$L"
}
neg_register license_gpl

# --- 2. DCO: unsigned commit (Plan P1 DoD) ----------------------------------
case_dco_unsigned() {
  local D="$NEG_TMP/dco"; mkdir -p "$D"
  ( cd "$D" && git init -q -b main . \
      && git config user.name "Nevil N" && git config user.email "nevil@example.invalid" \
      && echo 1 > f.txt && git add f.txt && git commit -q -m "chore: unsigned" )
  neg_expect_reject "dco: unsigned commit" \
    'missing Signed-off-by' \
    "$PY" tools/dco_check.py --repo "$D"
}
neg_register dco_unsigned

# --- 3. registry: hand-edited feature row -----------------------------------
case_registry_drift() {
  local R="$NEG_TMP/drift"
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
  neg_expect_reject "registry: hand-edited features.yaml" \
    'features\.yaml\[0\].*feature' \
    "$PY" tools/registry_lint.py --repo "$R"
}
neg_register registry_drift

# --- 4. vocab: new banned word in fresh doc ---------------------------------
case_vocab_banned() {
  local V="$NEG_TMP/vocab"; mkdir -p "$V/docs/state"
  cp docs/state/vocab-allowlist.yaml "$V/docs/state/"
  printf 'Our stealth mode is unbreakable.\n' > "$V/docs/marketing.md"
  neg_expect_reject "vocab: banned words in new doc" \
    'marketing\.md:1: banned pattern' \
    "$PY" tools/vocab_lint.py --repo "$V"
}
neg_register vocab_banned

# --- 5. register: bad status enum -------------------------------------------
case_register_enum() {
  local G="$NEG_TMP/reg"; mkdir -p "$G/docs/register"
  ( cd "$G" && git init -q -b main . \
      && git config user.name "Nevil N" && git config user.email "nevil@example.invalid" )
  "$PY" - <<EOF
import yaml
rows = [
    {"id": f"DR-{n:02d}", "title": f"t{n}", "status": "APPROVED",
     "rationale": "r", "linked_lg": [], "reopen_condition": "rc",
     "phase_anchor": "P1"}
    for n in range(1, 31)
]
yaml.safe_dump({"schema_version": 1, "plan_sha256": "a" * 64,
                "decisions": rows},
               open("$G/docs/register/decisions.yaml", "w"), sort_keys=False)
EOF
  neg_expect_reject "register: invalid status enum" \
    'status .APPROVED. not in' \
    "$PY" tools/dr_parse.py --repo "$G"
}
neg_register register_enum

# --- 6. threat model: emptied honesty cell ----------------------------------
case_threat_model_honesty() {
  local T="$NEG_TMP/tm"; mkdir -p "$T/docs"
  "$PY" - "$T" <<'EOF'
import sys, hashlib, re
root = sys.argv[1]
plan = "# plan (negative fixture)\n"
open(f"{root}/docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md", "w").write(plan)
sha = hashlib.sha256(plan.encode()).hexdigest()
src = open("docs/threat-model.md").read()
src = re.sub(r"[0-9a-f]{64}", sha, src, count=1)
def blank_last_cell(m):
    line = m.group(0)
    return line.rsplit("|", 2)[0] + "| — |"
src = re.sub(r"^\| T2 \|.*\|\n", blank_last_cell, src, count=1, flags=re.MULTILINE)
open(f"{root}/docs/threat-model.md", "w").write(src)
EOF
  neg_expect_reject "threat model: emptied honesty cell (T2)" \
    'adversary T2: .Does NOT protect against. cell is empty' \
    "$PY" tools/check_threat_model.py --repo "$T"
}
neg_register threat_model_honesty

# --- 7. plan pin: tampered plan copy -----------------------------------------
case_plan_pin_tamper() {
  local P="$NEG_TMP/pin"; mkdir -p "$P/docs"
  cp docs/master-plan.sha256 "$P/docs/"
  cp docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md "$P/docs/"
  printf 'tampered\n' >> "$P/docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
  neg_expect_reject "plan pin: tampered plan copy" \
    'plan pin mismatch' \
    "$PY" tools/plan_pin_check.py --repo "$P"
}
neg_register plan_pin_tamper
