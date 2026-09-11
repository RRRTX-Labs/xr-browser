# tools/negatives/p5_p6.sh — P5/P6 gate negatives (evidence bundles, mojom,
# contracts manifest, freeze check, vectors, mode_lint, mutation, fuzz,
# snapshot verify). P9-T0-d split.

# --- 14. evidence bundle: a VERIFIED row citing a missing artifact ----------
case_evidence_missing_artifact() {
  local EV="$NEG_TMP/ev"; mkdir -p "$EV/evidence/P7"
  printf '{"phase":"P7","generated":"2026-09-07","plan":"p","dod_rows":[{"id":"E1","dod":"d","status":"VERIFIED","evidence":["logs/nope.txt"]}]}' \
    > "$EV/evidence/P7/evidence.json"
  neg_expect_reject "evidence: VERIFIED row citing a missing artifact (strict)" \
    'cites missing artifact|missing or empty human-gates' \
    "$PY" tools/evidence_check.py --repo "$EV" --strict
}
neg_register evidence_missing_artifact

# --- 15/16. P5 mojom_lint fixtures ------------------------------------------
case_mojom_banned() {
  neg_expect_reject "mojom_lint: banned method (GetDatabase)" \
    'R4 BANNED method' \
    "$PY" tools/mojom_lint.py tools/tests/fixtures/mojom/banned_getdatabase.mojom
}
neg_register mojom_banned

case_mojom_stringly() {
  neg_expect_reject "mojom_lint: stringly-typed error field" \
    'R5 stringly-typed error' \
    "$PY" tools/mojom_lint.py tools/tests/fixtures/mojom/stringly_error.mojom
}
neg_register mojom_stringly

# --- 17. P5 contracts_manifest: a contract missing its fake -----------------
case_contracts_manifest_missing_fake() {
  local CM="$NEG_TMP/cm"; mkdir -p "$CM"
  cp -r docs "$CM/docs"
  mkdir -p "$CM/../xr-core-empty"
  neg_expect_reject "contracts_manifest: missing fake (no xr-core fakes)" \
    'not found|missing part' \
    "$PY" tools/contracts_manifest.py --repo "$CM"
}
neg_register contracts_manifest_missing_fake

# --- 18. P5 freeze_check: agent-written RATIFIED in FROZEN.yaml -------------
case_freeze_ratified() {
  local FZ="$NEG_TMP/fz"; mkdir -p "$FZ/docs/contracts/review"
  sed 's/ratified: PENDING/ratified: RATIFIED/' docs/contracts/FROZEN.yaml > "$FZ/docs/contracts/FROZEN.yaml"
  cp docs/contracts/review/*.md "$FZ/docs/contracts/review/"
  neg_expect_reject "freeze_check: agent-written RATIFIED (HG-26 human-only)" \
    'ratified verdict|must be PENDING' \
    "$PY" tools/freeze_check.py --repo "$FZ"
}
neg_register freeze_ratified

# --- 19. P5 vectors_check: drift between fake and vectors -------------------
case_vectors_drift() {
  local VD="$NEG_TMP/vd"; mkdir -p "$VD/docs/contracts/vectors"
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
  neg_expect_reject "vectors_check: fake-vs-vector drift (id cited)" \
    'fake output != vector' \
    "$PY" tools/vectors_check.py --repo "$VD" --fakes ../xr-core/fakes
}
neg_register vectors_drift

# --- 21/22. mode_lint -------------------------------------------------------
case_mode_lint_rogue() {
  local R="$NEG_TMP/rogue"; mkdir -p "$R/net"
  printf '// Copyright 2026 RRRTX Labs\nint f(const char* t) {\n  return t == "kShield" ? 1 : 0;\n}\n' > "$R/net/rogue.cc"
  neg_expect_reject "mode_lint: injected rogue mode check (file:line cited)" \
    'rogue\.cc:3.*\[mode-logic\]' \
    "$PY" tools/mode_lint.py --root "$R" --config ../xr-core/policy/mode_lint.cfg
}
neg_register mode_lint_rogue

case_mode_lint_no_header() {
  local H="$NEG_TMP/hdr"; mkdir -p "$H/policy"
  printf '// Copyright 2026 RRRTX Labs\nint g() { return 0; }\n' > "$H/policy/no_header.cc"
  neg_expect_reject "mode_lint: missing // Intent: header (L13)" \
    'missing-intent-header' \
    "$PY" tools/mode_lint.py --root "$H" --config ../xr-core/policy/mode_lint.cfg
}
neg_register mode_lint_no_header

# --- 23. mutation gate: hollowed tests => survivors => score gate fails -----
# P11-T0-c: hollows ALL policy suites, not just test_vectors.cc. Hollowing
# ONE suite was sampling-dependent: after T0-b shrank the policy mutant
# population (json*.cc moved to common/) and the store battery gained the
# required-int-field cases (xr-core 85289cd), the seeded sample no longer
# needed test_vectors to die — the negative PASSED on bad input. Hollowing
# every suite makes "score dips below gate" structural: whatever the
# population or the seed, nothing is left to kill anything.
case_mutation_hollowed() {
  if ! command -v g++ >/dev/null 2>&1; then
    neg_skip "mutation negative (g++ absent — CI runs it)"
    return 0
  fi
  local M="$NEG_TMP/mut"; cp -r ../xr-core "$M"
  local t
  for t in "$M"/policy/tests/test_*.cc; do
    printf '// hollowed for the negative fixture\nint main() { return 0; }\n' > "$t"
  done
  neg_expect_reject "mutation: hollowed test suite => score dips below gate" \
    '"gate": "FAIL"' \
    "$PY" tools/mutation_test.py --xr-core "$M" --sample 6 --seed 31337 --timebox 300 --json
}
neg_register mutation_hollowed

# --- 24. fuzz gate: a crashing host binary => violation detected ------------
case_policy_fuzz_crash() {
  local F="$NEG_TMP/crashhost"
  printf '#!/bin/sh\ncase "$1" in *identity*) kill -SEGV $$;; esac\nprintf \x27{"ok":{}}\x27\n' > "$F"
  chmod +x "$F"
  neg_expect_reject "policy_fuzz: crashing host detected (never a silent pass)" \
    'exit code|crashes' \
    "$PY" tools/policy_fuzz.py --host "$F" --iterations 40 --timebox 60 --seed 5
}
neg_register policy_fuzz_crash

# --- 25. snapshot verify: corrupt blob => typed error, exit 1 ---------------
case_snapshot_corrupt() {
  local HOST=../xr-core/policy/tests/build/policy_host
  if [ ! -x "$HOST" ]; then
    neg_skip "policy_host snapshot negative (host not built; CI has g++)"
    return 0
  fi
  neg_expect_reject "policy_host snapshot --verify: corrupt blob rejected" \
    'kMalformedInput|kHashMismatch' \
    "$HOST" snapshot --verify '{"schema":"xr-policy-snapshot","schema_version":1,"kind":"full","seq":1,"base_seq":1,"hash":"deadbeef","entries":[]}'
}
neg_register snapshot_corrupt
