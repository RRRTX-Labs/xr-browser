#!/usr/bin/env python3
"""tools/permission_contract_check.py — the P15 contract lane.

Four jobs, all stdlib:
1. FROZEN bytes: docs/contracts/FROZEN.yaml and the 66 frozen resolver vectors
   (vectors/policy-resolver-v1.json) hash to their pinned values. P15 adds
   vectors in a NEW file and never edits the frozen ones.
2. permission-audit-event-v1 golden (docs/contracts/tests/golden-permission-
   audit-event.jsonl): each line is canonical JSON, validates against the
   schema through tools/xr_schema.py (the single validator), and its origin is
   a bare registrable domain or the empty string (identity-wide rows).
3. Overlay vectors (vectors/permission-overlay-v1.json): count == length,
   names unique, every expected state is a legal PermissionState name, and
   every vector names the four frozen capabilities.
4. Negative fixtures: --fixture origin|usage plants a bad row and must be
   REJECTED (exit 0 means the planted row reddened the gate, as designed).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import xr_schema  # noqa: E402  (the one validator; never a second copy)

FROZEN_YAML_SHA = "0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1"
FROZEN_VECTORS_SHA = "8d35c4c33adcc050743af664d69042cf507c9f5e04a3a10a10b4b5e1fdcc29bb"
FROZEN_VECTOR_COUNT = 66
CAPS = ("geolocation", "camera", "microphone", "notifications")
STATES = ("kDeny", "kAsk", "kAllow")
GOLDEN = REPO / "docs/contracts/tests/golden-permission-audit-event.jsonl"
SCHEMA = REPO / "docs/contracts/permission-audit-event-v1.schema.json"
OVERLAY = REPO / "docs/contracts/vectors/permission-overlay-v1.json"
FROZEN_VECTORS = REPO / "docs/contracts/vectors/policy-resolver-v1.json"
FROZEN_YAML = REPO / "docs/contracts/FROZEN.yaml"
# A bare registrable domain: labels of [a-z0-9-], no leading or trailing hyphen.
DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def check_frozen(fails: list[str]) -> None:
    if sha256(FROZEN_YAML) != FROZEN_YAML_SHA:
        fails.append("FROZEN.yaml bytes changed (the frozen list is never edited in P15)")
    if sha256(FROZEN_VECTORS) != FROZEN_VECTORS_SHA:
        fails.append("policy-resolver-v1.json changed (the 66 frozen vectors are byte-pinned)")
    doc = json.loads(FROZEN_VECTORS.read_text(encoding="utf-8"))
    if doc.get("count") != FROZEN_VECTOR_COUNT or len(doc.get("vectors", [])) != FROZEN_VECTOR_COUNT:
        fails.append(f"frozen vector count drifted (want {FROZEN_VECTOR_COUNT})")


def validate_row(line: str, schema: dict) -> list[str]:
    errs: list[str] = []
    try:
        row = json.loads(line)
    except json.JSONDecodeError as e:
        return [f"not JSON: {e}"]
    if canonical(row) != line:
        errs.append("line is not canonical JSON (sorted keys, no whitespace)")
    errs += xr_schema.validate_document(row, schema)
    origin = row.get("origin", "")
    if origin != "" and not DOMAIN_RE.match(origin):
        errs.append(f"origin {origin!r} is not a bare registrable domain")
    return errs


def check_golden(fails: list[str]) -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    lines = [ln for ln in GOLDEN.read_text(encoding="utf-8").split("\n") if ln]
    events = set()
    for i, line in enumerate(lines, 1):
        for e in validate_row(line, schema):
            fails.append(f"golden row {i}: {e}")
        try:
            events.add(json.loads(line).get("event"))
        except json.JSONDecodeError:
            pass
    if events != {"grant", "revoke", "expiry"}:
        fails.append(f"golden does not cover all three event classes: {sorted(events)}")
    return len(lines)


def check_overlay(fails: list[str]) -> int:
    doc = json.loads(OVERLAY.read_text(encoding="utf-8"))
    vectors = doc.get("vectors", [])
    if doc.get("count") != len(vectors):
        fails.append(f"overlay vectors: count {doc.get('count')} != length {len(vectors)}")
    names = [v.get("name") for v in vectors]
    if len(set(names)) != len(names):
        fails.append("overlay vectors: duplicate names")
    for v in vectors:
        name = v.get("name", "?")
        perms = v.get("expected", {}).get("permissions", {})
        if sorted(perms) != sorted(CAPS):
            fails.append(f"overlay vector {name}: expected must name exactly the four frozen capabilities")
        for cap, st in perms.items():
            if st not in STATES:
                fails.append(f"overlay vector {name}: {cap}={st!r} is not a PermissionState name")
        req = v.get("request", {})
        if not isinstance(req.get("identity", {}).get("value"), str):
            fails.append(f"overlay vector {name}: request.identity.value missing")
    return len(vectors)


def fixture_row(kind: str) -> str:
    base = {"contract": "permission-audit-event", "contract_version": 1,
            "event": "grant", "identity": "xr:00000000-0000-4000-8000-0000000000a1",
            "capability": "camera", "origin": "example.com", "scope": "once",
            "ts_millis": 1, "ttl_millis": 0, "reason": "user-grant",
            "deciding_layer": "identity_overlay",
            "determinism_note": ("ts_millis is caller-supplied; the core reads no clock; "
                                 "identical inputs give identical bytes")}
    if kind == "origin":
        base["origin"] = "https://example.com/private/path"  # a full origin
    elif kind == "usage":
        base["usage_active"] = True  # a usage field that must not exist
    return canonical(base)


def main() -> int:
    ap = argparse.ArgumentParser(prog="permission-contract", description=__doc__.splitlines()[0])
    ap.add_argument("--fixture", choices=["origin", "usage"], default=None,
                    help="negative fixture: a planted bad audit row that MUST be rejected")
    a = ap.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if a.fixture:
        errs = validate_row(fixture_row(a.fixture), schema)
        if errs:
            print(f"ok: negative fixture reddened ({errs[0]})")
            return 0
        print("FAIL: negative fixture did NOT redden (a contract check that cannot fail certifies nothing)")
        return 1
    fails: list[str] = []
    check_frozen(fails)
    rows = check_golden(fails)
    vecs = check_overlay(fails)
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: permission-contract ({len(fails)} gap(s))")
        return 1
    print(f"PASS: permission-contract (frozen 66 vectors + FROZEN.yaml byte-pinned; "
          f"{rows} audit golden row(s) schema-valid and canonical; {vecs} overlay vector(s) well-formed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
