# tools/negatives/p11_t0d.sh — P11-T0-d negative cases: the evidence --strict
# tightening (hosted claims need ci-run rows; a stale BLOCKED fails) and the
# runner-capabilities ledger's citation law (a comment-claim is refused).

# minimal strict-checkable bundle skeleton under $1, phase dir $2
_p11d_bundle() {
  local ROOT="$1" PH="$2"
  mkdir -p "$ROOT/evidence/$PH/logs"
  printf 'human gates for the fixture\n' > "$ROOT/evidence/$PH/human-gates.md"
  printf 'transcript\n' > "$ROOT/evidence/$PH/logs/x.txt"
}

# --- 70. evidence --strict: an uncited hosted claim must redden (rule d) ---
case_evidence_hosted_claim_needs_ci_run() {
  local R="$NEG_TMP/hostedclaim"; _p11d_bundle "$R" P12
  cat > "$R/evidence/P12/evidence.json" <<'JSON'
{
 "phase": "P12 — fixture",
 "generated": "2026-09-11",
 "plan": "docs/plans/fixture.md",
 "dod_rows": [
  {"id": "F-1", "dod": "the widget compiles byte-exact on the hosted runner",
   "status": "VERIFIED", "source": "local-run", "evidence": ["logs/x.txt"]}
 ]
}
JSON
  neg_expect_reject "evidence --strict: uncited hosted claim reddens (rule d)" \
    'rule d' \
    "$PY" tools/evidence_check.py --repo "$R" --strict --only P12
  # Positive control: an APPENDED ci-run correction row (real green run
  # 34615191984 / job 103315238760, head recorded in repos) satisfies the
  # rule; offline the resolver SKIPs visibly and the bundle still passes —
  # deterministic either way, and the original row is never edited.
  cat > "$R/evidence/P12/evidence.json" <<'JSON'
{
 "phase": "P12 — fixture",
 "generated": "2026-09-11",
 "plan": "docs/plans/fixture.md",
 "repos": {"xr-browser": "fixture head 8fadb0ee4a7cab04762df5c111778c122e0da919"},
 "dod_rows": [
  {"id": "F-1", "dod": "the widget compiles byte-exact on the hosted runner",
   "status": "VERIFIED", "source": "local-run", "evidence": ["logs/x.txt"]},
  {"id": "F-1-C1", "corrects": "F-1",
   "dod": "Correction (appended): the hosted half, cited — server-conformance green with the Rust toolchain steps",
   "status": "VERIFIED", "source": "ci-run",
   "ci_run": 34615191984, "ci_job": 103315238760,
   "evidence": ["logs/x.txt"]}
 ]
}
JSON
  if "$PY" tools/evidence_check.py --repo "$R" --strict --only P12 >/dev/null 2>&1; then
    echo "ok: hosted-claim positive control (appended correction row resolves rule d)"
  else
    echo "NEGATIVE-FAIL: hosted-claim positive control must pass once the correction row is appended"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register evidence_hosted_claim_needs_ci_run

# --- 71. evidence --strict: stale BLOCKED (tool proven present) reddens ----
case_evidence_stale_blocked_fails() {
  local R="$NEG_TMP/staleblocked"; _p11d_bundle "$R" P13
  mkdir -p "$R/docs/state"
  cat > "$R/docs/state/runner-capabilities.json" <<'JSON'
{
 "capabilities": {
  "cargo": {"present": true, "version": "1.98.1",
            "proven_by": [{"ci_run": 34615191984, "ci_job": 103315238760,
                           "date": "2026-09-11"}]},
  "go": {"present": "UNOBSERVED", "note": "never printed by any lane"}
 }
}
JSON
  cat > "$R/evidence/P13/evidence.json" <<'JSON'
{
 "phase": "P13 — fixture",
 "generated": "2026-09-11",
 "plan": "docs/plans/fixture.md",
 "not_done_by_design": ["the deployable check is blocked on the sandbox toolchain"],
 "dod_rows": [
  {"id": "B-1", "dod": "Rust deployable replay — no cargo in the sandbox",
   "status": "BLOCKED-NET", "source": "local-run", "evidence": ["logs/x.txt"]},
  {"id": "B-2", "dod": "Go telemetry replay — no go in the sandbox",
   "status": "BLOCKED-NET", "source": "local-run", "evidence": ["logs/x.txt"]}
 ]
}
JSON
  # B-1 must be flagged stale (cargo proven present); B-2 must NOT (go is
  # UNOBSERVED — the ledger refuses to certify what no run ever printed).
  # Hermetic PATH (hosted-CI law; research-log D7 item 15): rule (e)'s LOCAL
  # arm is shutil.which() — hosted runners carry `go` on PATH, which fired
  # the arm for B-2 and reddened this canary for the wrong reason. Pin the
  # world: a stub `cargo` (B-1's arm MUST fire) and a PATH without `go`
  # (B-2's arm must NOT) — identical semantics in both worlds.
  local HBIN out rc
  HBIN="$(mktemp -d)"
  printf '#!/bin/sh\nexit 0\n' > "$HBIN/cargo" && chmod +x "$HBIN/cargo"
  out="$(env PATH="$HBIN:/usr/bin:/bin" "$PY" tools/evidence_check.py --repo "$R" --strict --only P13 2>&1)" && rc=0 || rc=$?
  rm -rf "$HBIN"

  if [ "$rc" -eq 0 ]; then
    echo "NEGATIVE-FAIL: stale BLOCKED (cargo proven present) passed strict — rule (e) inert"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif ! printf '%s' "$out" | grep -q 'STALE BLOCKED'; then
    echo "NEGATIVE-FAIL: rejected, but not as STALE BLOCKED"
    printf '%s\n' "$out" | sed 's/^/    | /'
    NEG_FAILURES=$((NEG_FAILURES + 1))
  elif printf '%s' "$out" | grep -q 'row B-2'; then
    echo "NEGATIVE-FAIL: rule (e) fired on the UNOBSERVED tool (go) — the ledger must not certify what no run printed"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  else
    echo "ok: evidence --strict: stale BLOCKED reddens (rule e), UNOBSERVED tool does not"
  fi
}
neg_register evidence_stale_blocked_fails

# --- 72. runner_caps --check: comment-claims are refused ------------------
case_runner_caps_citation_law() {
  local R="$NEG_TMP/caps"; mkdir -p "$R/docs/state"
  cat > "$R/docs/state/runner-capabilities.json" <<'JSON'
{
 "capabilities": {
  "rustc": {"present": true, "version": "1.98.1"},
  "go": {"present": "UNOBSERVED"}
 }
}
JSON
  neg_expect_reject "runner_caps --check: present without proven_by + UNOBSERVED without note reddens" \
    'proven_by' \
    "$PY" tools/runner_caps.py --repo "$R" --check
  # an empty ledger certifies nothing (zero-case law)
  printf '{"capabilities": {}}\n' > "$R/docs/state/runner-capabilities.json"
  neg_expect_reject "runner_caps --check: empty ledger reddens (zero-case law)" \
    'non-empty' \
    "$PY" tools/runner_caps.py --repo "$R" --check
}
neg_register runner_caps_citation_law
