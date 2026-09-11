#!/usr/bin/env python3
"""tools/list_bundle_check.py — the xr-lists pipeline gate (P11-T3).

Verifies, deterministically and offline:
  1. the FROZEN list-bundle-manifest-v1 contract files are UNTOUCHED —
     sha256 comparison against the pins below, reported (DoD 5: the
     frozen schema is consumed, never edited; a mismatch here is a
     STOP-and-report condition, not a fixable warning);
  2. the golden manifest validates against the frozen schema itself
     (parsed from disk — required fields, additionalProperties:false,
     declared types) plus the pipeline's STRICTER entry refinement
     ({name, sha256 64-hex, rules int>=0, attribution?} — stricter than
     frozen is the allowed direction; the schema leaves lists[] free-form
     and that is exactly where attribution rides);
  3. manifest <-> bundle binding: per list, name equal, sha256 == digest
     of the list's canonical bytes (frozen rule, xr-lists/bundle_bytes
     definition — cross-checked against the compiled C++ host in
     xr-lists/tests/roundtrip.sh), rules count equal, attribution equal;
  4. the apply-state laws over the golden state sidecar: pins keep the
     last TWO slots and contain the active slot, lkg != active with a
     LOWER version, monotonic per bundle_id, no wall clock anywhere
     (last_apply_mono is data);
  5. refusal-table coverage: every refusal reason in the golden bundle is
     inside the closed compiler vocabulary, the compile vectors carry
     >=30 refusal cases, and every REACHABLE refusal family has >=1
     vector case (the defensive mirror tokens — comment/options-in-
     filter/empty-segment/malformed-line — are vocabulary members the
     compiler refuses upstream of, so no vector can hit them; they are
     listed, not required);
  6. with --check: the WHOLE package regenerates byte-identical through
     the real tools (compile.py -> attribution.py -> sign.py manifest):
     bundle.json, LICENSE.attribution.txt, manifest.json.

House CLI: exit 0 ok · 1 violation/drift · 2 usage. No network, no
clock, no external binaries (the gpg round-trip lives in roundtrip.sh).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "xr-lists"))
from bundle_bytes import list_sha  # noqa: E402

SCHEMA_PINS = {
    "docs/contracts/list-bundle-manifest-v1.schema.json":
        "8f9e576b3ff7fc5cf879fb702e552ea0f88a89d646e15a6d6575c2df245a7bb4",
    "docs/contracts/list-bundle-manifest-v1.md":
        "d0d9e09f7492ed50b5a181168e1b732f3fca00860738795057b7527cca1caaf7",
}

REFUSAL_TOKENS = frozenset({
    "unsupported-directive:scriptlet",
    "unsupported-directive:procedural-cosmetic",
    "unsupported-directive:preprocessor",
    "unsupported-directive:regex",
    "unsupported-directive:cosmetic-hash",
    "unsupported-directive:at-syntax",
    "unsupported-directive:interior-pipe",
    # defensive mirrors of the bundle grammar — the compiler refuses
    # these upstream, so they are vocabulary members no vector can hit:
    "unsupported-directive:comment",
    "unsupported-directive:options-in-filter",
    "unsupported-directive:empty-segment",
    "malformed-line",
    # reachable non-family tokens:
    "unsupported-option-combination:redirect-on-exception",
    "malformed-option:domain",
    "malformed-option:redirect",
    "malformed-option:empty-name",
    "empty-filter",
})
REFUSAL_FAMILY = "unsupported-option:"
DEFENSIVE = frozenset({
    "unsupported-directive:comment",
    "unsupported-directive:options-in-filter",
    "unsupported-directive:empty-segment",
    "malformed-line",
})
MIN_REFUSAL_CASES = 30


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def reason_ok(reason) -> bool:
    if not isinstance(reason, str) or not reason:
        return False
    if reason in REFUSAL_TOKENS:
        return True
    return reason.startswith(REFUSAL_FAMILY) and len(reason) > len(
        REFUSAL_FAMILY)


def families() -> set:
    req = {t for t in REFUSAL_TOKENS if t not in DEFENSIVE}
    req.add(REFUSAL_FAMILY)
    return req


def fail(msgs: list, text: str) -> None:
    msgs.append(text)
    print(f"FAIL: {text}")


def check_frozen_pins(repo: Path, msgs: list) -> None:
    for rel, pin in sorted(SCHEMA_PINS.items()):
        p = repo / rel
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != pin:
            fail(msgs, f"FROZEN contract file CHANGED: {rel} sha256 {got} "
                       f"!= pin {pin} — STOP-and-report (the frozen "
                       "list-bundle-manifest-v1 is consumed, never edited)")
        else:
            print(f"ok: frozen {Path(rel).name} untouched (sha256 {got[:16]}… "
                  "== pin)")


def check_manifest_schema(repo: Path, man: dict, msgs: list) -> None:
    schema = json.loads(
        (repo / "docs/contracts/list-bundle-manifest-v1.schema.json")
        .read_text(encoding="utf-8"))
    allowed = set(schema["properties"])
    extra = set(man) - allowed
    missing = set(schema["required"]) - set(man)
    if extra:
        fail(msgs, f"manifest top-level additionalProperties:false "
                   f"violated: {sorted(extra)}")
    if missing:
        fail(msgs, f"manifest missing required: {sorted(missing)}")
    types = {"schema_version": int, "bundle_id": str, "created_epoch": int,
             "last_known_good_bundle_id": str, "lists": list,
             "key_pin": list}
    for key, ty in types.items():
        if key in man:
            v = man[key]
            ok = is_int(v) if ty is int else isinstance(v, ty)
            if not ok:
                fail(msgs, f"manifest {key}: wrong type (frozen schema)")
    if not isinstance(man.get("key_pin"), list) or \
            not all(isinstance(k, str) and k for k in man["key_pin"]):
        fail(msgs, "key_pin must be an array of non-empty strings "
                   "(frozen schema: array; element shape: pipeline law)")
    for i, e in enumerate(man.get("lists", [])):
        if not isinstance(e, dict) or \
                set(e) - {"name", "sha256", "rules", "attribution"}:
            fail(msgs, f"lists[{i}]: keys must be a subset of "
                       "name/sha256/rules/attribution")
            continue
        if not isinstance(e.get("name"), str) or not e["name"]:
            fail(msgs, f"lists[{i}].name: non-empty string required")
        sha = e.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or \
                any(c not in "0123456789abcdef" for c in sha):
            fail(msgs, f"lists[{i}].sha256: 64-char lowercase hex required")
        if not is_int(e.get("rules")) or e["rules"] < 0:
            fail(msgs, f"lists[{i}].rules: int >= 0 required")
        if "attribution" in e and (not isinstance(e["attribution"], str)
                                   or not e["attribution"]):
            fail(msgs, f"lists[{i}].attribution: non-empty string required")


def check_binding(bundle: dict, man: dict, msgs: list) -> None:
    bl, ml = bundle["lists"], man["lists"]
    if len(bl) != len(ml):
        fail(msgs, f"manifest-list-count: {len(ml)} entries vs "
                   f"{len(bl)} bundle lists")
        return
    for b, m in zip(bl, ml):
        if b["name"] != m.get("name"):
            fail(msgs, f"manifest-list-name: {m.get('name')} != {b['name']}")
        got = list_sha(b)
        if m.get("sha256") != got:
            fail(msgs, f"manifest-sha256:{b['name']}: {m.get('sha256')} "
                       f"!= recomputed {got}")
        if m.get("rules") != len(b["rules"]):
            fail(msgs, f"manifest-rule-count:{b['name']}")
        if m.get("attribution") != b["attribution"]:
            fail(msgs, f"manifest-attribution:{b['name']}: the manifest may "
                       "not claim attribution other than the pinned bytes")


def check_state(state: dict, msgs: list) -> None:
    def slot_ok(s, where):
        if not isinstance(s, dict) or "present" not in s:
            fail(msgs, f"state {where}: not a slot object")
            return False
        if not isinstance(s["present"], bool):
            fail(msgs, f"state {where}.present: bool required")
            return False
        if s["present"]:
            for k, ty in (("bundle_id", str), ("version", int),
                          ("digest", str)):
                v = s.get(k)
                ok = is_int(v) if ty is int else isinstance(v, str) and v
                if not ok:
                    fail(msgs, f"state {where}.{k}: bad slot field")
                    return False
        return True
    for where in ("active", "lkg"):
        if where not in state or not slot_ok(state[where], where):
            return
    pins = state.get("pins")
    if not isinstance(pins, list) or not all(slot_ok(p, f"pins[{i}]")
                                             for i, p in enumerate(pins)):
        fail(msgs, "state pins: array of slots required")
        return
    if len(pins) > 2:
        fail(msgs, f"too-many-pins: {len(pins)} > 2 (last-2 law)")
    act = state["active"]
    if act["present"] and act not in pins:
        fail(msgs, "pins-missing-active: the pins MUST contain the active "
                   "slot (hot-pin-out refusal, never a repair)")
    lkg = state["lkg"]
    if act["present"] and lkg["present"]:
        if lkg == act:
            fail(msgs, "lkg-duplicates-active")
        elif lkg["version"] >= act["version"] or \
                lkg["bundle_id"] != act["bundle_id"]:
            fail(msgs, "state monotonic law: lkg must be the SAME bundle_id "
                       "with a LOWER version")
    if not is_int(state.get("last_apply_mono")) or \
            state["last_apply_mono"] < -1:
        fail(msgs, "last_apply_mono: int >= -1 required (no wall clock)")


def check_refusals(bundle: dict, vectors: dict, msgs: list) -> None:
    for r in bundle.get("refusals", []):
        if not reason_ok(r.get("reason")):
            fail(msgs, f"refusal reason outside the closed vocabulary: "
                       f"{r.get('reason')!r}")
        if not isinstance(r.get("directive"), str) or not r["directive"]:
            fail(msgs, "refusal directive: non-empty string required")
        if not is_int(r.get("count")) or r["count"] < 1:
            fail(msgs, "refusal count: int >= 1 required")
    cases = vectors.get("cases", [])
    ref_cases = [c for c in cases if "refusals" in c.get("expect", {})]
    if len(ref_cases) < MIN_REFUSAL_CASES:
        fail(msgs, f"compile vectors: {len(ref_cases)} refusal cases "
                   f"(< {MIN_REFUSAL_CASES})")
    covered = set()
    for c in ref_cases:
        for r in c["expect"]["refusals"]:
            if not reason_ok(r.get("reason")):
                fail(msgs, f"vector {c['id']}: reason outside vocabulary: "
                           f"{r['reason']!r}")
            covered.add(r["reason"] if r["reason"] in REFUSAL_TOKENS
                        else REFUSAL_FAMILY)
    for fam in sorted(families()):
        if fam not in covered:
            fail(msgs, f"compile vectors: refusal family uncovered: {fam}")
    print(f"ok: refusal coverage ({len(ref_cases)} refusal cases, "
          f"{len(covered)} families covered, vocabulary closed)")


def regenerate(repo: Path, xr_lists: Path, tmp: Path, msgs: list) -> None:
    steps = [
        [sys.executable, str(xr_lists / "compile.py"), "--config",
         str(xr_lists / "sources" / "config.json"), "--out",
         str(tmp / "bundle.json")],
        [sys.executable, str(xr_lists / "attribution.py"), "--bundle",
         str(tmp / "bundle.json"), "--out-dir", str(tmp)],
        [sys.executable, str(xr_lists / "sign.py"), "manifest", "--bundle",
         str(tmp / "bundle.json"), "--bundle-id", "xr-default-testdata",
         "--epoch", "1780000000", "--key-pin", "gpg:XR-Lists-TEST-0000",
         "--out", str(tmp / "manifest.json")],
    ]
    for cmd in steps:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=repo)
        if r.returncode != 0:
            fail(msgs, f"regeneration step failed: {Path(cmd[1]).name}: "
                       f"{r.stdout.strip()}{r.stderr.strip()}")
            return
    for name in ("bundle.json", "LICENSE.attribution.txt", "manifest.json"):
        gold = xr_lists / "testdata" / name
        if gold.read_text(encoding="utf-8") != \
                (tmp / name).read_text(encoding="utf-8"):
            fail(msgs, f"DRIFT: testdata/{name} does not match the pipeline "
                       "regeneration — run the xr-lists tools")
        else:
            print(f"ok: testdata/{name} regenerates byte-identical")


def main() -> int:
    ap = argparse.ArgumentParser(prog="tools/list_bundle_check.py")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-lists", default=None)
    ap.add_argument("--vectors",
                    default="docs/contracts/vectors/xr-lists-compile-v1.json")
    ap.add_argument("--check", action="store_true",
                    help="also byte-compare the full pipeline regeneration")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_lists = Path(a.xr_lists).resolve() if a.xr_lists \
        else repo / "xr-lists"
    msgs: list = []
    check_frozen_pins(repo, msgs)
    td = xr_lists / "testdata"
    try:
        bundle = json.loads((td / "bundle.json").read_text(encoding="utf-8"))
        man = json.loads((td / "manifest.json").read_text(encoding="utf-8"))
        state = json.loads((td / "state.json").read_text(encoding="utf-8"))
        vectors = json.loads((repo / a.vectors).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot load artifacts: {e}")
        return 2
    check_manifest_schema(repo, man, msgs)
    check_binding(bundle, man, msgs)
    check_state(state, msgs)
    check_refusals(bundle, vectors, msgs)
    if a.check:
        with tempfile.TemporaryDirectory() as tmp:
            regenerate(repo, xr_lists, Path(tmp), msgs)
    if msgs:
        print(f"FAIL: list_bundle_check ({len(msgs)} violation(s))")
        return 1
    print("PASS: list_bundle_check (frozen schema untouched + manifest "
          "schema-valid + binding + state laws + refusal coverage"
          + (" + byte-identical regeneration)" if a.check else ")"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
