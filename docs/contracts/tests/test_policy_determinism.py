"""PolicyResolver purity/determinism contract test (SECURITY).

Monkeypatches time, random, and os.environ and asserts identical output — the
resolver reads no clock/RNG/env. Also asserts the determinism-pair vectors are
byte-identical.
"""
from __future__ import annotations

import importlib
import json
import os
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
VEC = REPO / "docs/contracts/vectors/policy-resolver-v1.json"


def canonical(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def test_resolver_is_env_time_random_independent(monkeypatch):
    import policy_resolver as pr
    req = {"identity": {"value": "xr:00000000-0000-4000-8000-000000000002"},
           "origin": {"scheme": "https", "registrable_domain": "bank.example"},
           "request_class": "kNavigation", "trust_context": "kFortress"}
    first = canonical(pr.resolve(req))
    # perturb the world
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    monkeypatch.setattr(time, "time", lambda: 999999999.0)
    import random
    monkeypatch.setattr(random, "random", lambda: 0.123456)
    importlib.reload(pr)
    second = canonical(pr.resolve(req))
    assert first == second


def test_determinism_pair_vectors_identical():
    doc = json.loads(VEC.read_text())
    pairs = {v["name"]: v for v in doc["vectors"] if v["name"].startswith("determinism-pair")}
    a, b = pairs["determinism-pair-a"], pairs["determinism-pair-b"]
    assert canonical(a["expected"]) == canonical(b["expected"])
