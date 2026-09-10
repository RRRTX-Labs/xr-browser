# tools/negatives/p3_p4.sh — P3/P4 gate negatives (patch budget, retirement,
# fetch chokepoint, spike candidates/census/genpatch). P9-T0-d split.

# --- 8. budget: over-cap manifest must fail the gate (Plan P3 DoD) ----------
case_budget_overcap() {
  local B="$NEG_TMP/budget"; mkdir -p "$B/inj"
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
  neg_expect_reject "budget: over-cap manifest fails the gate" \
    'extension_chokepoint' \
    "$PY" build/farm/budget_meter.py budget --manifest "$B/manifest.yaml" --gate
}
neg_register budget_overcap

# --- 9. retirement: manifest removal without a ledger entry -----------------
case_retirement_no_ledger() {
  local X="$NEG_TMP/xr-core"; mkdir -p "$X/patches/p/one"
  ( cd "$X" && git init -q -b main . \
      && git config user.name "Nevil N" && git config user.email "nevil@example.invalid" )
  printf 'schema_version: 1\ntotal_cap: 150\ncategories:\n  ui: { cap: 35 }\nallowed_roots:\n  - "a.txt"\npatches:\n  - id: "one"\n    owner: "@xr/platform"\n    category: ui\n    files:\n      - "a.txt"\n    dir: p/one\n' > "$X/patches/manifest.yaml"
  printf -- '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n' > "$X/patches/p/one/one.patch"
  ( cd "$X" && git add -A && git commit -q -m "init" )
  printf 'patches:\n' > "$X/patches/manifest.yaml"
  ( cd "$X" && git add -A && git commit -q -m "raw removal (negative)" )
  local M="$NEG_TMP/meta"; mkdir -p "$M/build/upstream"
  printf '{"schema_version": 1, "retirements": []}' > "$M/build/upstream/retirements.json"
  neg_expect_reject "retirement: removal without a ledger entry" \
    'without a ledger entry' \
    env XR_ROOT="$M" "$PY" build/upstream/retirements.py lint --xr-core "$X"
}
neg_register retirement_no_ledger

# --- 10. fetch chokepoint: direct network use outside fetch.py --------------
case_fetch_chokepoint() {
  local F="$NEG_TMP/choke"; mkdir -p "$F/build/upstream" "$F/tools"
  printf 'import urllib.request\nurllib.request.urlopen("https://evil.example.net/x")\n' \
    > "$F/build/upstream/evil_net.py"
  cp tools/fetch_allowlist_check.py "$F/tools/"
  cp build/upstream/fetch.py "$F/build/upstream/"
  neg_expect_reject "fetch chokepoint: urlopen outside the chokepoint" \
    'network import outside the chokepoint' \
    "$PY" "$F/tools/fetch_allowlist_check.py"
}
neg_register fetch_chokepoint

# --- 11. spike candidate outside spike/ without the NOT-YET header ----------
case_spike_candidate_unmanifested() {
  local S="$NEG_TMP/cand"; mkdir -p "$S/patches/branding/0009-sneaky" "$S/spike/patches/0001-bad"
  cp ../xr-core/patches/manifest.yaml "$S/patches/manifest.yaml" 2>/dev/null \
    || cp docs/state/license-allowlist.yaml "$S/patches/manifest.yaml"
  printf -- '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n' \
    > "$S/patches/branding/0009-sneaky/0009.patch"
  printf '# 0009\n\n- **status:** candidate\n' > "$S/patches/branding/0009-sneaky/patchinfo.md"
  printf -- '--- a/b.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-x\n+y\n' \
    > "$S/spike/patches/0001-bad/0001.patch"
  printf '# 0001 candidate\n\n- **status:** CANDIDATE\n' \
    > "$S/spike/patches/0001-bad/patchinfo.md"
  neg_expect_reject "candidate: unmanifested patch dir outside spike/" \
    'unmanifested patch dir' \
    "$PY" build/patching/apply.py lint --manifest "$S/patches/manifest.yaml" --xr-core "$S"
}
neg_register spike_candidate_unmanifested

case_spike_candidate_notyet() {
  local S="$NEG_TMP/cand2"; mkdir -p "$S/patches/branding/0009-sneaky" "$S/spike/patches/0001-bad"
  cp ../xr-core/patches/manifest.yaml "$S/patches/manifest.yaml" 2>/dev/null \
    || cp docs/state/license-allowlist.yaml "$S/patches/manifest.yaml"
  printf -- '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n' \
    > "$S/patches/branding/0009-sneaky/0009.patch"
  printf '# 0009\n\n- **status:** candidate\n' > "$S/patches/branding/0009-sneaky/patchinfo.md"
  printf -- '--- a/b.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-x\n+y\n' \
    > "$S/spike/patches/0001-bad/0001.patch"
  printf '# 0001 candidate\n\n- **status:** CANDIDATE\n' \
    > "$S/spike/patches/0001-bad/patchinfo.md"
  neg_expect_reject "candidate: spike patch without manifest-entry: NOT-YET" \
    'must carry .manifest-entry: NOT-YET' \
    "$PY" build/patching/apply.py lint --manifest "$S/patches/manifest.yaml" --xr-core "$S"
}
neg_register spike_candidate_notyet

# --- 12. spike: census missing the Plan's named surfaces --------------------
case_census_missing() {
  local CN="$NEG_TMP/census"; mkdir -p "$CN"
  printf '| id | surface | what breaks | repro | severity | owner | patch estimate (files x category) | landing phase | attacker-observable cross-identity |\n|---|---|---|---|---|---|---|---|---|\n| C-01 | downloads | x | y | S1 | B | 2 files x ui | P14 | yes |\n' > "$CN/census.md"
  neg_expect_reject "spike: census missing named surfaces" \
    'named surface missing' \
    "$PY" build/spike/census_lint.py --doc "$CN/census.md"
}
neg_register census_missing

# --- 13. spike: genpatch refuses a patch that targets content/** ------------
case_genpatch_neverlist() {
  local GS="$NEG_TMP/spike"; mkdir -p "$GS"
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
  neg_expect_reject "spike: genpatch refuses a content/** target (never-list)" \
    'never-list refusal' \
    "$PY" "$GS/genpatch.py" --xr-core ../xr-core --out "$GS/out"
}
neg_register genpatch_neverlist
