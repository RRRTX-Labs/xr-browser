#!/usr/bin/env python3
"""tools/gen_shield_vectors.py — generate the shield golden vectors
(P11-T2): >=150 typed cases across every decision axis — frozen mojom
surface (Status/RecentEvents), posture truth table (all 16), the v1 filter
grammar battery, exception scopes incl. the coupling law, apply
monotonicity/LKG/pins, manifest binding, and the protocol error families.

Expectation model: each case is RUN through the Python reference
implementation (xr-core/fakes/shield.py — the independent second
implementation of shield/host_protocol.md) and its canonical stdout bytes
become the vector's `expect`. tools/shield_vectors_check.py then replays
every case against BOTH backends and requires byte-identity with the
vectors — so a drift in either implementation reddens the gate. The C++
suite (xr-core/shield/tests/test_golden_vectors.cc) pins the same file
from the compiled side.

Split by responsibility for the touched-file size law (the
gen_update_vectors.py pattern): this driver owns ONLY the CLI, the
assembly order and the byte law; the fixtures + Gen machinery live in
shield_vectors_kit.py and the case families in
shield_vector_families.py (P11-T4: the exception-surface family lives in
shield_vector_families_t4.py, P11-T5: the emitter family in
shield_vector_families_t5.py — same split law, same fixed assembly order).

Deterministic: no clock, no RNG. --check regenerates byte-identical.
Exit: 0 ok · 1 drift/error · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shield_vector_families import (  # noqa: E402
    fam_apply, fam_bundle, fam_flag_posture, fam_frozen, fam_match,
    fam_protocol,
)
from shield_vector_families_t4 import fam_exceptions  # noqa: E402
from shield_vector_families_t5 import fam_events  # noqa: E402
from shield_vectors_kit import Gen  # noqa: E402

OUT = "docs/contracts/vectors/shield-v1.json"
DEFAULT_XR_CORE = "../xr-core"


def main() -> int:
    ap = argparse.ArgumentParser(prog="gen-shield-vectors")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else \
        (repo / DEFAULT_XR_CORE).resolve()
    fake = xr_core / "fakes" / "shield.py"
    if not fake.exists():
        print(f"FAIL: fake not found at {fake}")
        return 2
    g = Gen(fake)
    fam_frozen(g)
    fam_flag_posture(g)
    fam_match(g)
    fam_exceptions(g)
    fam_bundle(g)
    fam_apply(g)
    fam_protocol(g)
    fam_events(g)
    ids = [c["id"] for c in g.cases]
    if len(ids) != len(set(ids)):
        print("FAIL: duplicate vector ids")
        return 1
    if len(g.cases) < 150:
        print(f"FAIL: only {len(g.cases)} cases (<150)")
        return 1
    doc = {"cases": g.cases, "schema": "xr-shield-vectors",
           "schema_version": 1,
           "note": "Golden vectors for the shield surface (P11-T2): every "
                   "case's expect is the canonical stdout of the Python "
                   "reference (xr-core/fakes/shield.py); "
                   "tools/shield_vectors_check.py replays them against BOTH "
                   "backends byte-for-byte, and xr-core/shield/tests/"
                   "test_golden_vectors.cc pins them from the compiled "
                   "side. Flags field carries host CLI flags; exit pins "
                   "codes the derivation rule would miss. P11-T4 adds the "
                   "exception surface (exception-add / exception-remove / "
                   "exception-sweep / site-toggle) as fam_exceptions; P11-T5 adds the "
                   "activity-ledger emitter (event-emit, the living "
                   "block-event-v1 rows) as fam_events."}
    blob = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out = repo / OUT
    if a.check:
        if not out.exists() or out.read_text(encoding="utf-8") != blob:
            print(f"DRIFT: {OUT} does not match regeneration; "
                  "run tools/gen_shield_vectors.py")
            return 1
        print(f"PASS: {OUT} regenerates byte-identical ({len(g.cases)} cases)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    print(f"wrote {len(g.cases)} cases -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
