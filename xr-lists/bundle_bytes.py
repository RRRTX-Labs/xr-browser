#!/usr/bin/env python3
"""xr-lists/bundle_bytes.py — the ONE pipeline-side definition of the
frozen canonical-bytes rules (P11-T3): the per-list canonical bytes a
manifest entry's sha256 covers, and the bundle digest. The authoritative
implementations are xr-core/shield/core/bundle.cc (C++) and
xr-core/fakes/shield.py (mirror); this module is the pipeline copy, and
drift is structurally impossible to keep hidden: tools/list_bundle_check
recomputes bindings through it AND xr-lists/tests/roundtrip.sh runs the
compiled host's bundle-check over the signed manifest — any disagreement
reddens a gate.

Frozen rule (docs/contracts/list-bundle-manifest-v1.md): a list entry's
sha256 covers canonical({"attribution":…,"name":…,"rules":[projected
rule objects]}) — rules projected to {action, filter, id, kind} plus
resource/domains/exclude_domains WHEN PRESENT — and the bundle digest is
sha256("[" + ",".join(per-list canonical bytes) + "]").
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

OPTIONAL_RULE_KEYS = ("domains", "exclude_domains", "resource")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def rule_projection(r: dict) -> dict:
    ro = {"action": r["action"], "filter": r["filter"], "id": r["id"],
          "kind": r["kind"]}
    for key in OPTIONAL_RULE_KEYS:
        if r.get(key):
            ro[key] = r[key]
    return ro


def list_canonical_bytes(lst: dict) -> str:
    return canonical({"attribution": lst["attribution"], "name": lst["name"],
                      "rules": [rule_projection(r) for r in lst["rules"]]})


def list_sha(lst: dict) -> str:
    return hashlib.sha256(
        list_canonical_bytes(lst).encode("utf-8")).hexdigest()


def bundle_digest(bundle: dict) -> str:
    joined = "[" + ",".join(list_canonical_bytes(l) for l in
                            bundle["lists"]) + "]"
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
