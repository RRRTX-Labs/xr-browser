# tools/negatives/p11_t1.sh — P11-T1 negative cases: the vendored-Rust pin
# must redden on tamper, on an advisory hit, and the allowlist ceremony must
# never widen past static.crates.io (index/API hosts stay refused).

# mini vendor tree builder (mirrors tools/tests/test_p11_vendor.py's fixture;
# kept self-contained so the negative suite stays stdlib-shell+python)
_p11t1_tree() {
  "$PY" - "$1" <<'PYEOF'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "rust"
mini_sha = hashlib.sha256(b"mini-tarball").hexdigest()
lock_text = (
    'version = 4\n\n[[package]]\nname = "adblock"\nversion = "0.13.3"\n'
    'dependencies = [\n "mini 1.0.0",\n]\n\n[[package]]\nname = "mini"\n'
    'version = "1.0.0"\nsource = "registry+https://github.com/rust-lang/'
    'crates.io-index"\nchecksum = "%s"\n' % mini_sha)
lock_sha = hashlib.sha256(lock_text.encode()).hexdigest()
pin = root / "adblock" / "0.13.3"
def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t)
w(pin / "Cargo.toml", '[package]\nname = "adblock"\nversion = "0.13.3"\nlicense = "MPL-2.0"\n\n[dependencies]\nmini = "1.0"\n')
w(pin / "Cargo.lock", lock_text)
w(pin / "src" / "lib.rs", "// upstream bytes\n")
w(pin / "README.xr.md", "# xr\n")
w(pin / "UPDATING.md", "# updating\n")
for mname, rels in (("MANIFEST.sha256", ["Cargo.toml", "Cargo.lock", "src/lib.rs"]),
                    ("MANIFEST.xr.sha256", ["README.xr.md", "UPDATING.md"])):
    w(pin / mname, "".join(
        hashlib.sha256((pin / r).read_bytes()).hexdigest() + "  " + r + "\n"
        for r in sorted(rels)))
w(root / "Cargo.lock", lock_text)
w(root / ".cargo" / "config.toml",
  '[source.crates-io]\nreplace-with = "xr-vendored-sources"\n\n'
  '[source.xr-vendored-sources]\ndirectory = "vendor"\n')
vd = root / "vendor" / "mini-1.0.0"
w(vd / "Cargo.toml", '[package]\nname = "mini"\nversion = "1.0.0"\nlicense = "MIT"\n')
w(vd / "src" / "lib.rs", "// mini\n")
files = {r: hashlib.sha256((vd / r).read_bytes()).hexdigest()
         for r in ("Cargo.toml", "src/lib.rs")}
w(vd / ".cargo-checksum.json", json.dumps({"files": files, "package": mini_sha}))
w(root / "supply-chain" / "PROVENANCE.md", "# provenance\n")
w(root / "supply-chain" / "licenses.json", json.dumps(
    {"root": {"sha256_lock": lock_sha},
     "crates": {"mini 1.0.0": {"expression": "MIT", "chosen": "MIT"}}}))
w(root / "supply-chain" / "advisories.json", json.dumps(
    {"match": {"hits": [], "needs_review": [], "name_matches": []}}))
print(root)
PYEOF
}

# --- 74. vendor_check: a planted tamper reddens, naming the file ------------
case_vendor_tamper() {
  local T; T=$(_p11t1_tree "$NEG_TMP/t1-tamper")
  printf '// tamper\n' >> "$T/vendor/mini-1.0.0/src/lib.rs"
  neg_expect_reject "vendor_check: planted tamper in a vendored crate reddens" \
    'TAMPER|DRIFT' \
    "$PY" tools/vendor_check.py --root "$T"
  # positive control: the untampered twin passes
  local C; C=$(_p11t1_tree "$NEG_TMP/t1-clean")
  if "$PY" tools/vendor_check.py --root "$C" >/dev/null 2>&1; then
    echo "ok: vendor_check positive control (clean tree passes)"
  else
    echo "NEGATIVE-FAIL: vendor_check positive control must pass on a clean tree"
    NEG_FAILURES=$((NEG_FAILURES + 1))
  fi
}
neg_register vendor_tamper

# --- 75. vendor_check: an advisory HIT in the supply-chain record reddens ---
case_vendor_advisory_hit() {
  local T; T=$(_p11t1_tree "$NEG_TMP/t1-hit")
  "$PY" - "$T" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "supply-chain" / "advisories.json"
p.write_text(json.dumps({"match": {
    "hits": [{"crate": "mini", "vendored_version": "1.0.0",
              "ghsa_id": "GHSA-xxxx", "severity": "critical",
              "vulnerable_version_range": "< 2.0"}],
    "needs_review": [], "name_matches": []}}))
PYEOF
  neg_expect_reject "vendor_check: a GHSA hit in advisories.json reddens (stop-and-report)" \
    'HIT' \
    "$PY" tools/vendor_check.py --root "$T"
}
neg_register vendor_advisory_hit

# --- 76. the ceremony never widens: index/API hosts stay refused ------------
case_ceremony_index_refused() {
  neg_expect_reject "chokepoint: index.crates.io refused (only the CDN joined)" \
    'REFUSED|not on the fetch allowlist' \
    "$PY" build/upstream/fetch.py check-url "https://index.crates.io/ad/bl/adblock"
  neg_expect_reject "chokepoint: crates.io API refused" \
    'REFUSED|not on the fetch allowlist' \
    "$PY" build/upstream/fetch.py check-url "https://crates.io/api/v1/crates/adblock"
}
neg_register ceremony_index_refused
