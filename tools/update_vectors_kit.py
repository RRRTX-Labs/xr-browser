#!/usr/bin/env python3
"""tools/update_vectors_kit.py — shared fixture builders for the update
golden-vector generator (P10-T1; split out of gen_update_vectors.py for
the 400-LOC law). The stub scheme (material-bound signatures) lives here
so the generator, the C++ fixture (env_helper.h), the host and the fake
all cite one definition of "stub signature".
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


KEY_MATERIAL = {"xr-root-1": "ROOT-PUB-KEY",
                "xr-signing-2026-09": "SIGNING-PUB-KEY"}


def stub_sig(response_obj, key_id="xr-root-1") -> str:
    material = KEY_MATERIAL.get(key_id, "")
    return "sig:" + hashlib.sha256(
        (material + "|" + canonical(response_obj)).encode()).hexdigest()[:16]


def envelope(response, epoch_id="epoch-2026-09", key_id="xr-root-1", seq=3,
             sig_value=None) -> str:
    body = dict(response)
    return canonical({
        "epoch": {"epoch_id": epoch_id, "key_id": key_id, "seq": seq},
        "schema": "xr-update-envelope",
        "schema_version": 1,
        "signature": {"alg": "minisign-ed25519", "key_id": key_id,
                      "sig": sig_value if sig_value is not None
                      else stub_sig(body, key_id)},
        "response": body,
    })


KEYS = [{"key_id": "xr-root-1", "public_key": "ROOT-PUB-KEY"},
        {"key_id": "xr-signing-2026-09", "public_key": "SIGNING-PUB-KEY"}]
# (stub signatures are computed under exactly these materials — see
# KEY_MATERIAL; key substitution therefore breaks verification in the
# vectors, as it does in the C++ fixture.)

EPOCH = {"epoch_id": "epoch-2026-09", "key_id": "xr-root-1", "seq": 3,
         "revoked": False, "manual_path": False}
