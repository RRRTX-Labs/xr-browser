#!/usr/bin/env python3
"""tools/gen_update_vectors.py — generate the update golden vectors
(P10-T1): >=60 typed cases across every verify axis + epoch-apply/cohort/
backoff/about-state, deterministic, --check regenerates byte-identical.
Fixture builders live in tools/update_vectors_kit.py (the stub-signature
law's single definition); the case FAMILIES live in
tools/update_vectors_families.py (P11-T0-e split by responsibility — this
file keeps the CLI, the closures and the document assembly)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

OUT = "docs/contracts/vectors/update-v1.json"

from update_vectors_families import (  # noqa: E402  (P11-T0-e split)
    BASE_RESPONSE, build_about_state_family, build_cohort_backoff_family,
    build_epoch_apply_family, build_verify_family,
)

from update_vectors_kit import EPOCH, KEYS, envelope  # kit (stub-sig law)

def verify_args(env_str, current="1.0.0.0", channel="dev", epoch=None,
                seen=None, transport=None):
    a = {"channel": channel, "current_version": current, "envelope": env_str,
         "epoch": epoch if epoch is not None else EPOCH, "keys": KEYS}
    if seen:
        a["seen"] = seen
    if transport is not None:
        a["transport"] = transport
    return a

def main() -> int:
    ap = argparse.ArgumentParser(prog="gen-update-vectors")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo)
    cases: list[dict] = []

    def add(cid, method, args_v, expect):
        cases.append({"args": args_v, "expect": expect, "id": cid,
                      "method": method})

    good = envelope(BASE_RESPONSE)

    def V(cid, env_str, expect_reason, current="1.0.0.0", channel="dev",
          epoch=None, seen=None, transport=None, verdict=None):
        v = "accept" if expect_reason == "ok" else (verdict or "deny")
        manual = (epoch or {}).get("manual_path", False) \
            if expect_reason == "epoch-revoked" else False
        add(cid, "verify",
            verify_args(env_str, current, channel, epoch, seen, transport),
            {"manual_path": manual, "reason": expect_reason, "verdict": v})

    build_verify_family(V, add, good, verify_args)
    build_epoch_apply_family(add)
    build_cohort_backoff_family(add)
    build_about_state_family(add)

    doc = {"cases": cases, "schema": "xr-update-vectors",
           "schema_version": 1,
           "note": "Golden vectors for the update surface (P10-T1): typed "
                   "verdict + reason per case; signatures are the TEST-ONLY "
                   "fixture value; byte-parity runs across update_host (C++) "
                   "and fakes/update.py via tools/update_vectors_check.py."}
    blob = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out = repo / OUT
    if a.check:
        if not out.exists() or out.read_text(encoding="utf-8") != blob:
            print(f"DRIFT: {OUT} does not match regeneration; "
                  "run tools/gen_update_vectors.py")
            return 1
        print(f"PASS: {OUT} regenerates byte-identical ({len(cases)} cases)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    print(f"wrote {len(cases)} cases -> {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
