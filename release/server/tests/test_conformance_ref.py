#!/usr/bin/env python3
"""release/server/tests/test_conformance_ref.py — the REFERENCE half of the
conformance gate (P10-T2): replays every corpus case against
refimpl/update_server_ref.py and demands the exact expected bytes, the
expected status, determinism (a second identical handle call yields
identical bytes — the statelessness law) and, for 200s, canonical-byte
identity + a stub-valid signature.

The deployable half (release/server/rust/tests/conformance.rs) replays the
SAME corpus on the hosted runner; a byte of divergence is a red gate.

Exit: 0 pass · 1 fail. Stdlib only.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".." / "refimpl"))

import update_server_ref as ref  # noqa: E402

CORPUS = HERE / "conformance.json"


def spec_for(spec0: dict, overlay: dict | None) -> dict:
    if not overlay:
        return spec0
    spec = copy.deepcopy(spec0)

    def merge(dst: dict, src: dict) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v
    for top, sub in overlay.items():
        merge(spec[top], sub)
    return spec


def main() -> int:
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = doc.get("cases") or []
    if not cases:
        print("FAIL: zero conformance cases — a runner that runs nothing "
              "certifies nothing")
        return 1
    spec0 = ref.load_spec()
    variants = doc.get("variants") or {}
    n200 = 0
    for c in cases:
        spec = spec_for(spec0, variants.get(c["spec_variant"]))
        got = ref.handle(c["request"].encode(), spec, c["content_length"])
        if got != (c["expect_status"], c["expect_response"]):
            print(f"FAIL: {c['id']}: status {got[0]} vs {c['expect_status']} "
                  f"or bytes diverge:\n  got  {got[1][:160]!r}\n"
                  f"  want {c['expect_response'][:160]!r}")
            return 1
        again = ref.handle(c["request"].encode(), spec, c["content_length"])
        if again != got:
            print(f"FAIL: {c['id']}: statefulness detected (second handle "
                  "differs)")
            return 1
        if c["expect_status"] == 200:
            body = got[1]
            env = json.loads(body[len(ref.PREFIX):])
            if ref.canonical(env) + "\n" != body[len(ref.PREFIX):]:
                print(f"FAIL: {c['id']}: response not canonical")
                return 1
            if env["signature"]["sig"] != ref.stub_sig(
                    ref.KEY_MATERIAL[env["signature"]["key_id"]],
                    ref.canonical(env["response"])):
                print(f"FAIL: {c['id']}: manifest signature not stub-valid")
                return 1
            if len(body) > 2048:
                print(f"FAIL: {c['id']}: response {len(body)} > 2048")
                return 1
            n200 += 1
    print(f"PASS: server conformance (reference): {len(cases)} cases "
          f"({n200} render-31 responses byte-exact, "
          f"{len(cases) - n200} typed refusals; stateless; canonical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
