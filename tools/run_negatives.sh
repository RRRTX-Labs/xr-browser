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


# --- 8. budget: over-cap manifest must fail the gate (Plan P3 DoD) ----------
B="$TMP/budget"; mkdir -p "$B/inj"
"$PY" - "$B" <<'PYDONE'
import sys
from pathlib import Path
root = Path(sys.argv[1])
rows = []
for i in range(3):  # extension_chokepoint cap = 2
    d = root / "inj" / str(i)
    d.mkdir(parents=True, exist_ok=True)
    (d / "inj.patch").write_text("--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-x\n+y\n")
    rows += [f'  - id: "inj-{i}"', '    owner: "@xr/security"',
             "    category: extension_chokepoint", "    files:", '      - "x.txt"',
             f"    dir: inj/{i}"]
(root / "manifest.yaml").write_text(
    "schema_version: 1\ntotal_cap: 150\ncategories:\n"
    "  extension_chokepoint: { cap: 2 }\nallowed_roots:\n  - \"x.txt\"\n"
    "patches:\n" + "\n".join(rows) + "\n")
PYDONE
expect_reject "budget: over-cap manifest fails the gate" \
  'extension_chokepoint' \
  "$PY" build/farm/budget_meter.py budget --manifest "$B/manifest.yaml" --gate

# --- 9. retirement: manifest removal without a ledger entry -----------------
X="$TMP/xr-core"; mkdir -p "$X/patches/p/one"; cd "$X"
git init -q -b main .
git config user.name "Nevil N"; git config user.email "nevil@example.invalid"
printf 'schema_version: 1\ntotal_cap: 150\ncategories:\n  ui: { cap: 35 }\nallowed_roots:\n  - "a.txt"\npatches:\n  - id: "one"\n    owner: "@xr/platform"\n    category: ui\n    files:\n      - "a.txt"\n    dir: p/one\n' > patches/manifest.yaml
printf -- '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n' > patches/p/one/one.patch
git add -A; git commit -q -m "init"
printf 'patches:\n' > patches/manifest.yaml   # raw removal, NO xr-patch retire
git add -A; git commit -q -m "raw removal (negative)"
cd - >/dev/null
M="$TMP/meta"; mkdir -p "$M/build/upstream"
printf '{"schema_version": 1, "retirements": []}' > "$M/build/upstream/retirements.json"
expect_reject "retirement: removal without a ledger entry" \
  'without a ledger entry' \
  env XR_ROOT="$M" "$PY" build/upstream/retirements.py lint --xr-core "$X"

# --- 10. fetch chokepoint: direct network use outside fetch.py ---------------
F="$TMP/choke"; mkdir -p "$F/build/upstream" "$F/tools"
printf 'import urllib.request\nurllib.request.urlopen("https://evil.example.net/x")\n' \
  > "$F/build/upstream/evil_net.py"
cp tools/fetch_allowlist_check.py "$F/tools/"
cp build/upstream/fetch.py "$F/build/upstream/"   # the checker reads the chokepoint
expect_reject "fetch chokepoint: urlopen outside the chokepoint" \
  'network import outside the chokepoint' \
  "$PY" "$F/tools/fetch_allowlist_check.py"


# --- 11. spike candidate outside spike/ without the NOT-YET header -----------
S="$TMP/cand"; mkdir -p "$S/patches/branding/0009-sneaky" "$S/spike/patches/0001-bad"
cp ../xr-core/patches/manifest.yaml "$S/patches/manifest.yaml" 2>/dev/null \
  || cp docs/state/license-allowlist.yaml "$S/patches/manifest.yaml"
printf -- '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n' \
  > "$S/patches/branding/0009-sneaky/0009.patch"
printf '# 0009\n\n- **status:** candidate\n' > "$S/patches/branding/0009-sneaky/patchinfo.md"
printf -- '--- a/b.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-x\n+y\n' \
  > "$S/spike/patches/0001-bad/0001.patch"
printf '# 0001 candidate\n\n- **status:** CANDIDATE\n' \
  > "$S/spike/patches/0001-bad/patchinfo.md"
expect_reject "candidate: unmanifested patch dir outside spike/" \
  'unmanifested patch dir' \
  "$PY" build/patching/apply.py lint --manifest "$S/patches/manifest.yaml" --xr-core "$S"
expect_reject "candidate: spike patch without manifest-entry: NOT-YET" \
  'must carry .manifest-entry: NOT-YET' \
  "$PY" build/patching/apply.py lint --manifest "$S/patches/manifest.yaml" --xr-core "$S"

# --- 12. spike: census missing the Plan's named surfaces ---------------------
CN="$TMP/census"; mkdir -p "$CN"
printf '| id | surface | what breaks | repro | severity | owner | patch estimate (files x category) | landing phase | attacker-observable cross-identity |\n|---|---|---|---|---|---|---|---|---|\n| C-01 | downloads | x | y | S1 | B | 2 files x ui | P14 | yes |\n' > "$CN/census.md"
expect_reject "spike: census missing named surfaces" \
  'named surface missing' \
  "$PY" build/spike/census_lint.py --doc "$CN/census.md"

# --- 13. spike: genpatch refuses a patch that targets content/** -------------
# End-to-end, not a unit test: run the real genpatch against a spec whose
# targets include a content/ path. The tool must refuse before fetching.
GS="$TMP/spike"; mkdir -p "$GS"
cp build/_common.py build/spike/genpatch.py build/spike/seam_spec.py "$GS/"
"$PY" - "$GS" <<'NEG'
import sys
from pathlib import Path
d = Path(sys.argv[1])
s = (d / "seam_spec.py").read_text()
s = s.replace('NAVIGATOR = "chrome/browser/ui/navigator/browser_navigator.cc"',
              'NAVIGATOR = "content/browser/site_instance_impl.cc"')
(d / "seam_spec.py").write_text(s)
NEG
expect_reject "spike: genpatch refuses a content/** target (never-list)" \
  'never-list refusal' \
  "$PY" "$GS/genpatch.py" --xr-core ../xr-core --out "$GS/out"

# --- 14. evidence bundle: a VERIFIED row citing a missing artifact -----------
EV="$TMP/ev"; mkdir -p "$EV/evidence/PX"
printf '{"phase":"PX","generated":"2026-09-07","plan":"p","dod_rows":[{"id":"E1","dod":"d","status":"VERIFIED","evidence":["logs/nope.txt"]}]}' \
  > "$EV/evidence/PX/evidence.json"
expect_reject "evidence: VERIFIED row citing a missing artifact (strict)" \
  'cites missing artifact|missing or empty human-gates' \
  "$PY" tools/evidence_check.py --repo "$EV" --strict

echo
echo
if [ "$FAILURES" -ne 0 ]; then
  echo "NEGATIVE GATE FAILED: at least one gate accepted bad input or failed for the wrong reason"
  exit 1
fi
echo "ALL NEGATIVE CASES REJECTED AS EXPECTED"
