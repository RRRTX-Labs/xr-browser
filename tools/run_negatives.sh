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
EV="$TMP/ev"; mkdir -p "$EV/evidence/P7"
# Phase dir must be a numeric P<n> (>P2) so --strict auto-covers it; a bare
# "PX" is skipped by strict_default_phases and the gate never sees the row.
printf '{"phase":"P7","generated":"2026-09-07","plan":"p","dod_rows":[{"id":"E1","dod":"d","status":"VERIFIED","evidence":["logs/nope.txt"]}]}' \
  > "$EV/evidence/P7/evidence.json"
expect_reject "evidence: VERIFIED row citing a missing artifact (strict)" \
  'cites missing artifact|missing or empty human-gates' \
  "$PY" tools/evidence_check.py --repo "$EV" --strict

# --- 15. P5 mojom_lint: banned method name in a mojom fixture ----------------
expect_reject "mojom_lint: banned method (GetDatabase)" \
  'R4 BANNED method' \
  "$PY" tools/mojom_lint.py tools/tests/fixtures/mojom/banned_getdatabase.mojom

# --- 16. P5 mojom_lint: stringly-typed error field ---------------------------
expect_reject "mojom_lint: stringly-typed error field" \
  'R5 stringly-typed error' \
  "$PY" tools/mojom_lint.py tools/tests/fixtures/mojom/stringly_error.mojom

# --- 17. P5 contracts_manifest: a contract missing its fake ------------------
# Build a scratch repo view where one fake is absent -> manifest fails.
CM="$TMP/cm"; mkdir -p "$CM"
cp -r docs "$CM/docs"
# point --repo at a tree whose sibling xr-core lacks the fakes dir
mkdir -p "$CM/../xr-core-empty"
expect_reject "contracts_manifest: missing fake (no xr-core fakes)" \
  'not found|missing part' \
  "$PY" tools/contracts_manifest.py --repo "$CM"

# --- 18. P5 freeze_check: agent-written RATIFIED in FROZEN.yaml ---------------
FZ="$TMP/fz"; mkdir -p "$FZ/docs/contracts/review"
sed 's/ratified: PENDING/ratified: RATIFIED/' docs/contracts/FROZEN.yaml > "$FZ/docs/contracts/FROZEN.yaml"
cp docs/contracts/review/*.md "$FZ/docs/contracts/review/"
expect_reject "freeze_check: agent-written RATIFIED (HG-26 human-only)" \
  'ratified verdict|must be PENDING' \
  "$PY" tools/freeze_check.py --repo "$FZ"

# --- 19. P5 vectors_check: drift between fake and vectors ---------------------
VD="$TMP/vd"; mkdir -p "$VD/docs/contracts/vectors"
"$PY" - "$VD" <<'NEG'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
src = Path("docs/contracts/vectors/policy-resolver-v1.json")
doc = json.loads(src.read_text())
doc["vectors"][0]["expected"] = {"ok": {"tampered": True}}
(d / "docs/contracts/vectors/policy-resolver-v1.json").write_text(json.dumps(doc))
route = Path("docs/contracts/vectors/route-manager-v1.json")
(d / "docs/contracts/vectors/route-manager-v1.json").write_text(route.read_text())
NEG
expect_reject "vectors_check: fake-vs-vector drift (id cited)" \
  'fake output != vector' \
  "$PY" tools/vectors_check.py --repo "$VD" --fakes ../xr-core/fakes

# --- P6 negatives (policy resolver gates must have teeth) -------------------

# 21. mode_lint: injected rogue mode check outside the resolver => fail
#     citing file:line (the static half of the plan's Manual row).
R="$TMP/rogue"; mkdir -p "$R/net"
printf '// Copyright 2026 RRRTX Labs\nint f(const char* t) {\n  return t == "kShield" ? 1 : 0;\n}\n' > "$R/net/rogue.cc"
expect_reject "mode_lint: injected rogue mode check (file:line cited)" \
  'rogue\.cc:3.*\[mode-logic\]' \
  "$PY" tools/mode_lint.py --root "$R" --config ../xr-core/policy/mode_lint.cfg

# 22. mode_lint: policy file without L13 intent header => fail.
H="$TMP/hdr"; mkdir -p "$H/policy"
printf '// Copyright 2026 RRRTX Labs\nint g() { return 0; }\n' > "$H/policy/no_header.cc"
expect_reject "mode_lint: missing // Intent: header (L13)" \
  'missing-intent-header' \
  "$PY" tools/mode_lint.py --root "$H" --config ../xr-core/policy/mode_lint.cfg

# 23. mutation gate: hollowed tests => survivors => score gate fails.
#     (Copy the real tree, neuter test_vectors so mutants survive; the gate
#     must trip — a score gate that cannot fail is decoration.)
if command -v g++ >/dev/null 2>&1; then
  M="$TMP/mut"; cp -r ../xr-core "$M"
  printf '// hollowed for the negative fixture\nint main() { return 0; }\n' > "$M/policy/tests/test_vectors.cc"
  expect_reject "mutation: hollowed test suite => score dips below gate" \
  '"gate": "FAIL"' \
  "$PY" tools/mutation_test.py --xr-core "$M" --sample 6 --seed 31337 --timebox 300 --json
else
  echo "SKIP: SKIP (tool absent: g++) — needed for: mutation negative (hollowed suite); CI runners have g++ and run it"
fi

# 24. fuzz gate: a crashing host binary => violation detected (exit 1).
F="$TMP/crashhost"
printf '#!/bin/sh\ncase "$1" in *identity*) kill -SEGV $$;; esac\nprintf \x27{"ok":{}}\x27\n' > "$F"
chmod +x "$F"
expect_reject "policy_fuzz: crashing host detected (never a silent pass)" \
  'exit code|crashes' \
  "$PY" tools/policy_fuzz.py --host "$F" --iterations 40 --timebox 60 --seed 5

# 25. snapshot verify: corrupt blob => typed error, exit 1 (never a guess).
HOST=../xr-core/policy/tests/build/policy_host
if [ -x "$HOST" ]; then
  expect_reject "policy_host snapshot --verify: corrupt blob rejected" \
  'kMalformedInput|kHashMismatch' \
  "$HOST" snapshot --verify '{"schema":"xr-policy-snapshot","schema_version":1,"kind":"full","seq":1,"base_seq":1,"hash":"deadbeef","entries":[]}'
else
  echo "SKIP: SKIP (tool absent: policy_host not built) — needed for: corrupt-blob negative; build with g++ present"
fi

# --- P7 negatives (command-registry + WebUI gates must have teeth) ----------

# 26. csp_lint: a WebUI view that reaches the network at runtime => fail.
CU="$TMP/cspui"; mkdir -p "$CU"
printf '// Copyright 2026 RRRTX Labs\nexport async function load() {\n  return await fetch("https://example.com");\n}\n' > "$CU/rogue.ts"
expect_reject "csp_lint: runtime fetch( in ui/** (no runtime egress)" \
  'fetch\(' \
  "$PY" tools/csp_lint.py --ui-root "$CU" --commands-root "$TMP/does-not-exist"

# 27. a11y_lint: a palette missing the SR-critical aria-activedescendant => fail.
AP="$TMP/a11y"; mkdir -p "$AP/palette" "$AP/help-index"
printf 'export class X { render() { return `<div role="combobox"></div>`; } }\n' > "$AP/palette/palette.ts"
printf 'export class Y { render() { return `<div aria-live="polite"></div>`; } }\n' > "$AP/help-index/help-index.ts"
printf ':focus-visible { outline: 1px solid red; }\n' > "$AP/tokens.css"
expect_reject "a11y_lint: palette missing ARIA APG combobox token" \
  'aria-activedescendant' \
  "$PY" tools/a11y_lint.py --palette-dir "$AP/palette" --ui-dir "$AP"

# 28. rtl_lint: physical margin-left / text-align:left in the WebUI CSS => fail.
RT="$TMP/rtl"; mkdir -p "$RT"
printf '.x { margin-left: 8px; text-align: left; }\n' > "$RT/bad.css"
expect_reject "rtl_lint: physical left/right CSS (logical-only law)" \
  'margin-left/right' \
  "$PY" tools/rtl_lint.py --ui-dir "$RT"

# 29. menu_model_check: a 10-tier-1 roster => rejected (Tier-1 always-visible <=9).
MM="$TMP/tier1"; mkdir -p "$MM"
"$PY" - "$MM" <<'NEG'
import json, sys, pathlib
src = pathlib.Path("../xr-core/commands/core/roster_v1.json")
reg = json.loads(src.read_text())
n = 0
for c in reg["commands"]:
    c["descriptor"]["attention_tier"] = "tier1"
    n += 1
    if n >= 10:
        break
(pathlib.Path(sys.argv[1]) / "roster10.json").write_text(json.dumps(reg))
NEG
expect_reject "menu_model_check: 10-tier-1 roster breaches the Attention Budget" \
  'tier1|Tier-1' \
  "$PY" tools/menu_model_check.py --roster "$MM/roster10.json" --out "$MM/x.json"

# 30. coverage_check: a LANDED surface with no registered command => bite.
CV="$TMP/cov"; mkdir -p "$CV/ui/settings"
printf 'export class Rogue {}\n' > "$CV/ui/settings/rogue-section.ts"
expect_reject "coverage_check: landed settings surface maps to no command (§10)" \
  'has no command registered' \
  "$PY" tools/coverage_check.py --ui-root "$CV/ui"

# 31. commands_host: a PAGE-originated invoke => rejected + ledger (never a handler).
# The page-reject is IN-BAND: the host process succeeds (rc=0) and reports
# status:"rejected" inside the ok payload (the security gate is the dispatch,
# not a process failure). Assert the in-band rejection + the ledger row.
CH=../xr-core/commands/tests/build/commands_host
if [ -x "$CH" ]; then
  mkdir -p "$TMP/ch"   # the host persists the seeded registry into --store-dir
  OUT="$("$CH" --store-dir "$TMP/ch" --roster ../xr-core/commands/core/roster_v1.json \
        --flag xr_command_registry_v1=on \
        '{"method":"invoke","args":{"id":"tab.new","source":"page"}}' 2>&1)"
  if printf '%s' "$OUT" | grep -qE '"status":"rejected"' \
     && printf '%s' "$OUT" | grep -qE 'not whitelisted|page'; then
    echo "ok: commands_host: page-originated invoke rejected in-band (source-tag whitelist)"
  else
    echo "NEGATIVE-FAIL: commands_host page-reject — expected in-band \"status\":\"rejected\", got: $OUT"
    FAILURES=1
  fi
else
  echo "SKIP: SKIP (tool absent: commands_host not built) — needed for: page-reject negative; CI has g++"
fi

echo
echo
if [ "$FAILURES" -ne 0 ]; then
  echo "NEGATIVE GATE FAILED: at least one gate accepted bad input or failed for the wrong reason"
  exit 1
fi
echo "ALL NEGATIVE CASES REJECTED AS EXPECTED"
