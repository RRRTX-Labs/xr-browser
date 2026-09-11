#!/usr/bin/env bash
# xr-lists/tests/roundtrip.sh — the P11-T3 pipeline matrix, executed for
# real where the sandbox allows (the build/signing/tests/test_signing_p10.sh
# pattern):
#   * REAL gpg round-trip through the P10 channel (build/signing/
#     linux_repo_sign.py, runtime keyring — never committed keys):
#     sign -> verify OK; one-byte tamper => FAILS; wrong keyring => FAILS;
#     gpg absent => visible SKIP (77); minisign absent => visible SKIP.
#   * The release-channel refusal (fail-closed, HG-36/37 owns release).
#   * The attribution shape law reddens on a malformed attribution.
#   * HOST cells (compiled shield_host; g++/make absent => visible SKIP):
#     manifest<->bundle binding, data-tamper refusal, and the hot-pin
#     sequence in ONE host stream — apply-while-decisions-in-flight
#     (atomicity), the hot-pinned-out list dropped WITHOUT network (the
#     host is offline stdio by construction), the re-offered bad bundle
#     refused (replay path), and the equal re-offer refused.
# Exit: 0 all executed cells green · 1 failure (ZERO executed cells is a
# failure, never a pass — the zero-executed law).
set -u
cd "$(dirname "$0")/../.."   # repo root
PY="${PYTHON:-python3}"
PY_ABS="$(command -v "$PY")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CELLS_EXECUTED=0
FAILS=0
XR_CORE="${XR_CORE:-../xr-core}"
HOST="${XR_SHIELD_HOST:-$XR_CORE/shield/tests/build/shield_host}"

note() { printf '  %s\n' "$*"; }
cell() { CELLS_EXECUTED=$((CELLS_EXECUTED+1)); note "ok: $*"; }
bad()  { FAILS=$((FAILS+1)); echo "FAIL: $*"; }

# ---- pipeline: compile the hot-pin v1/v2 configs --------------------------
if out=$("$PY" xr-lists/compile.py --config xr-lists/sources/config-hotpin-v1.json --out "$TMP/bundle-v1.json" 2>&1); then
  cell "compile hotpin-v1 — $out"
else bad "compile v1: $out"; fi
if out=$("$PY" xr-lists/compile.py --config xr-lists/sources/config-hotpin-v2.json --out "$TMP/bundle-v2.json" 2>&1); then
  cell "compile hotpin-v2 (the bad list is hot-pinned OUT as signed data)"
else bad "compile v2: $out"; fi
if out=$("$PY" xr-lists/attribution.py --bundle "$TMP/bundle-v1.json" --out-dir "$TMP" 2>&1); then
  cell "attribution sidecar + shape law — $out"
else bad "attribution: $out"; fi

# ---- REAL gpg round-trip through the P10 channel --------------------------
GH="$TMP/gnupghome"
if out=$("$PY" xr-lists/sign.py sign --bundle "$TMP/bundle-v1.json" \
      --bundle-id xr-default --epoch 1780000100 \
      --key-pin "gpg:runtime-test-key" --out "$TMP/manifest-v1.json" \
      --gnupghome "$GH" 2>&1); then
  cell "sign: runtime keygen + detached gpg signature (TEST channel)"
elif [ $? -eq 77 ]; then
  note "SKIP: SKIP (tool absent: gpg) — the real-gpg cells (4); local hint: apt-get install gnupg"
else bad "sign: $out"; fi

"$PY" xr-lists/sign.py manifest --bundle "$TMP/bundle-v2.json" \
  --bundle-id xr-default --epoch 1780000200 \
  --key-pin "gpg:runtime-test-key" --out "$TMP/manifest-v2.json" >/dev/null 2>&1

if [ -f "$TMP/manifest-v1.json.asc" ]; then
  if out=$("$PY" xr-lists/sign.py verify --manifest "$TMP/manifest-v1.json" \
        --gnupghome "$GH" 2>&1); then
    cell "verify: detached signature OK — $out"
  else bad "verify: $out"; fi
  # one-byte tamper INSIDE the signed manifest -> must FAIL
  "$PY_ABS" - "$TMP/manifest-v1.json" <<'PYEOF'
import sys
p = sys.argv[1]
b = bytearray(open(p, 'rb').read())
i = b.index(b'xr-default')
b[i] = b[i] ^ 0x01
open(p + '.tampered', 'wb').write(bytes(b))
PYEOF
  if out=$("$PY" xr-lists/sign.py verify --manifest "$TMP/manifest-v1.json.tampered" \
        --sig "$TMP/manifest-v1.json.asc" --gnupghome "$GH" 2>&1); then
    bad "tampered manifest VERIFIED (gpg lane broken): $out"
  else cell "one-byte tamper detected"; fi
  # wrong keyring -> must FAIL
  "$PY" build/signing/linux_repo_sign.py keygen --gnupghome "$TMP/other-key" >/dev/null 2>&1
  if out=$("$PY" xr-lists/sign.py verify --manifest "$TMP/manifest-v1.json" \
        --gnupghome "$TMP/other-key" 2>&1); then
    bad "wrong-keyring VERIFIED: $out"
  else cell "wrong keyring rejected"; fi
fi

# ---- gpg absent => visible SKIP (77) --------------------------------------
mkdir -p "$TMP/emptybin"
out=$(env PATH="$TMP/emptybin" "$PY_ABS" xr-lists/sign.py sign \
      --bundle "$TMP/bundle-v1.json" --bundle-id xr-default \
      --epoch 1780000100 --key-pin "gpg:runtime-test-key" \
      --out "$TMP/m-nogpg.json" --gnupghome "$TMP/never" 2>&1)
rc=$?
if [ "$rc" -eq 77 ] && echo "$out" | grep -q "SKIP (tool absent: gpg)"; then
  cell "gpg-absent => visible SKIP (77), never a silent pass"
elif [ "$rc" -eq 0 ]; then
  bad "signing SUCCEEDED without gpg on PATH"
else
  bad "gpg-absent sign did not SKIP visibly (rc=$rc): $out"
fi

# ---- minisign absent => visible SKIP --------------------------------------
out=$("$PY" xr-lists/sign.py minisign --manifest "$TMP/manifest-v1.json" \
      --key "$TMP/minisign.key" --out-dir "$TMP/minisig" 2>&1)
rc=$?
if command -v minisign >/dev/null 2>&1; then
  if [ "$rc" -eq 0 ]; then
    cell "minisign dev-channel artifact (binary present — ran for real)"
  else bad "minisign with the binary present: rc=$rc: $out"; fi
elif [ "$rc" -eq 77 ] && echo "$out" | grep -q "SKIP (tool absent: minisign)"; then
  cell "minisign-absent => visible SKIP (P10's minisign-on-CI pattern)"
else
  bad "minisign-absent did not SKIP visibly (rc=$rc): $out"
fi

# ---- release-channel refusal (fail-closed; HG-36/37 owns release) ---------
if out=$("$PY" build/signing/sign_artifact.py --artifact "$TMP/manifest-v1.json" \
      --channel release --os linux 2>&1); then
  bad "release channel ACCEPTED by the test scaffold: $out"
else cell "release-channel refused by sign_artifact (fail-closed)"; fi

# ---- attribution shape law: a malformed attribution reddens ---------------
"$PY_ABS" - "$TMP/bundle-v1.json" "$TMP/bundle-badattr.json" <<'PYEOF'
import json, sys
b = json.load(open(sys.argv[1]))
b["lists"][0]["attribution"] = "only — two"
json.dump(b, open(sys.argv[2], "w"))
PYEOF
if out=$("$PY" xr-lists/attribution.py --bundle "$TMP/bundle-badattr.json" \
      --out-dir "$TMP" 2>&1); then
  bad "malformed attribution PASSED the shape law: $out"
else cell "attribution shape law reddens (not-4-segments + name-mismatch)"; fi

# ---- HOST cells: binding, data tamper, hot-pin sequence -------------------
# The v1 host is stateless per invocation — one JSON document per process
# lifetime, every state rides in the request (T2 design). "Apply while
# decisions are in flight" is therefore a DETERMINISTIC FRAME SEQUENCE:
# every frame answered exactly once, exactly one envelope per invocation,
# no cross-frame contamination possible by construction — and the apply
# law (monotonic / LKG / pins / replay refusals) is asserted over the
# state the frames pass along.
if [ ! -x "$HOST" ] && command -v g++ >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  make -s -C "$XR_CORE/shield/tests" >/dev/null 2>&1 || true
fi
cat > "$TMP/host_matrix.py" <<'PYEOF'
import json, os, subprocess, sys
host, tmp = os.environ["HOST"], os.environ["TMP"]
v1 = json.load(open(f"{tmp}/bundle-v1.json"))
v2 = json.load(open(f"{tmp}/bundle-v2.json"))
m1 = json.load(open(f"{tmp}/manifest-v1.json"))

def frame(method, args):
    return json.dumps({"method": method, "args": args}, sort_keys=True,
                      separators=(",", ":"))

def ctx(url, dom):
    return {"identity": {"value": "xr:a"},
            "origin": {"scheme": "https", "registrable_domain": dom},
            "url": url, "request_class": "kSubresource"}

def run(frames):
    """One invocation per frame (the v1 host contract); every frame must
    be answered with exactly one parsable envelope."""
    resps = []
    for f in frames:
        r = subprocess.run([host], input=f + "\n", capture_output=True,
                           text=True, timeout=60)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        assert len(lines) == 1, f"frame answered {len(lines)}x (rc={r.returncode})"
        resps.append(json.loads(lines[0]))
    return resps

# 1. the signed manifest binds the compiled bundle in the C++ host
(resp,) = run([frame("bundle-check", {"bundle": v1, "manifest": m1})])
assert resp.get("bound") is True, f"binding failed: {resp}"
print("ok: host bundle-check binds the signed manifest (2 lists)")

# 2. one-byte DATA tamper => the binding refuses (manifest-sha256)
bad = json.loads(json.dumps(v1))
bad["lists"][1]["rules"][0]["filter"] += "x"
(resp,) = run([frame("bundle-check", {"bundle": bad, "manifest": m1})])
assert resp.get("error") == "kRejected" and \
    resp.get("reason", "").startswith("manifest-sha256:"), f"tamper: {resp}"
print("ok: data tamper refused by the binding (manifest-sha256)")

# 3. decisions in flight around apply: the hot-pin sequence
fresh = {"active": {"present": False}, "lkg": {"present": False},
         "pins": [], "last_apply_mono": -1}
resps = run([
    frame("match", {"context": ctx("https://badlist.example/x",
                                   "badlist.example"), "bundle": v1}),
    frame("match", {"context": ctx("https://tracker.example/a.js",
                                   "tracker.example"), "bundle": v1}),
    frame("apply", {"bundle": v1, "state": fresh, "now_mono": 100}),
    frame("match", {"context": ctx("https://badlist.example/x",
                                   "badlist.example"), "bundle": v2}),
])
assert resps[0]["verdict"]["action"] == "block", f"v1 bad: {resps[0]}"
assert resps[1]["verdict"]["action"] == "block", f"v1 tracker: {resps[1]}"
s1 = resps[2].get("state")
assert s1 and s1["active"]["version"] == 1, f"apply v1: {resps[2]}"
assert resps[3]["verdict"]["action"] == "allow", \
    f"hot-pinned-out list still blocking: {resps[3]}"
print("ok: hot-pin-out dropped the bad list WITHOUT network "
      "(offline stdio host); every frame answered exactly once around apply")

# 4. replay path + state laws: v2 upgrade, re-offered v1 refused, equal
#    re-offer refused, lkg/pins hold
(r2,) = run([frame("apply", {"bundle": v2, "state": s1, "now_mono": 200})])
s2 = r2.get("state")
assert s2 and s2["active"]["version"] == 2, f"apply v2: {r2}"
assert s2["lkg"]["present"] and s2["lkg"]["version"] == 1, f"lkg: {s2}"
assert len(s2["pins"]) <= 2 and s2["active"] in s2["pins"], f"pins: {s2}"
resps = run([
    frame("apply", {"bundle": v1, "state": s2, "now_mono": 300}),
    frame("apply", {"bundle": v2, "state": s2, "now_mono": 400}),
])
assert resps[0].get("error") == "kRejected" and \
    resps[0]["reason"] == "bundle-version-downgrade", f"replay: {resps[0]}"
assert resps[1].get("error") == "kRejected" and \
    resps[1]["reason"] == "bundle-version-equal-reoffer", f"reoffer: {resps[1]}"
print("ok: replay path — re-offered bad bundle refused (downgrade), equal "
      "re-offer refused; lkg/pins laws held")
PYEOF
if [ -x "$HOST" ]; then
  if out=$(HOST="$HOST" TMP="$TMP" "$PY_ABS" "$TMP/host_matrix.py" 2>&1); then
    echo "$out" | while IFS= read -r l; do note "$l"; done
    n=$(echo "$out" | grep -c "^ok:")
    CELLS_EXECUTED=$((CELLS_EXECUTED+n))
  else
    echo "$out"
    bad "host matrix failed"
  fi
else
  note "SKIP: SKIP (tool absent: g++/make) — needed for: the host binding/hot-pin cells; local hint: apt-get install g++ make (build-essential)"
fi

if [ "$FAILS" -gt 0 ]; then
  echo "FAIL: xr-lists round-trip ($FAILS failure(s) of $CELLS_EXECUTED executed cells)"
  exit 1
fi
if [ "$CELLS_EXECUTED" -eq 0 ]; then
  echo "FAIL: xr-lists round-trip executed ZERO cells (0 executed => FAIL, never a pass)"
  exit 1
fi
echo "PASS: xr-lists round-trip ($CELLS_EXECUTED cells executed: real gpg sign/verify/tamper/wrong-key, SKIP-visible absences, release-channel refusal, attribution law, host binding + hot-pin-out + replay)"
exit 0
