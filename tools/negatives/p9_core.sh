# tools/negatives/p9_core.sh — P9 T0 canaries: each new runner MUST be able
# to turn red, and every canary is a registered case (counted, never hidden).

# --- 32. parity completeness: zero pairs is a failure ------------------------
case_parity_completeness_empty() {
  local M="$NEG_TMP/manifest-empty.json"
  printf '{"schema_version":1,"pairs":[]}' > "$M"
  neg_expect_reject "parity_completeness: zero pairs (zero-case law)" \
    'no pairs|zero-case' \
    "$PY" tools/parity_completeness.py --manifest "$M"
}
neg_register parity_completeness_empty

# --- 33. differential fuzz: a mutated fake must turn the oracle red ---------
case_differential_fuzz_canary() {
  if ! command -v g++ >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    neg_skip "differential fuzz canary (g++ absent; CI runs it)"
    return 0
  fi
  if [ ! -x ../xr-core/themes/tests/build/themes_host ]; then
    ( cd ../xr-core && make -C themes/tests build ) >/dev/null 2>&1 || true
  fi
  local FD="$NEG_TMP/fakes"
  cp -r ../xr-core/fakes "$FD"
  # strip the (security-critical pair) annotation: the oracle must notice
  "$PY" - "$FD/themes.py" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace('f["required"] >= 7.0', "False")
open(p, "w").write(s)
PY
  neg_expect_reject "differential_fuzz: mutated fake detected (canary)" \
    'divergence|FAIL: differential_fuzz' \
    "$PY" tools/differential_fuzz.py --fake-dir "$FD" --pairs themes \
      --iters 150 --seed 20260910 --min-iters 1
}
neg_register differential_fuzz_canary

# --- 34. pseudo_locale: fixed-width break must be detected ------------------
case_pseudo_locale_fixed_width() {
  neg_expect_reject "pseudo_locale: fixed-width overflow detected" \
    'fixed-width' \
    "$PY" tools/pseudo_locale.py --in ../xr-core/l10n/xr_strings.grdp \
      --fixed-width 30
}
neg_register pseudo_locale_fixed_width

# --- 35. lane discovery: a drifted lane list must fail ----------------------
case_lane_discovery_drift() {
  local B="$NEG_TMP/lanebase"; mkdir -p "$B/xb/tools" "$B/xb/docs/state" "$B/xr-core/fake/tests"
  cp tools/ci_lane_discovery.py "$B/xb/tools/"
  printf '{"schema_version":1,"lanes":["ghost"]}' > "$B/xb/docs/state/ci-lanes.json"
  printf 'test:\n\t@echo ok\n' > "$B/xr-core/fake/tests/Makefile"
  neg_expect_reject "lane discovery: drifted lane list detected" \
    'drifted' \
    "$PY" tools/ci_lane_discovery.py --repo "$B/xb"
}
neg_register lane_discovery_drift
