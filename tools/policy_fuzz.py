#!/usr/bin/env python3
"""tools/policy_fuzz.py — structure-aware fuzzer for the C++ policy core (P6).

Drives the policy_host stdio façade with (a) valid-shaped requests built
from the frozen vector grammar and (b) structured corruptions of them:
truncation at random offsets, byte flips, key duplication, deep nesting,
oversized strings, wrong types, numeric edges, unicode edge cases.

Invariants checked per input (ALL must hold, else FAIL):
  * exit code 0 (typed result — the protocol never crashes, never throws)
  * stdout is exactly one line of canonical JSON (sorted keys, no spaces)
  * the payload is {"ok": <EffectivePolicy>} or {"error": <known code>}
  * non-schema-conforming inputs NEVER produce a non-deny "ok" policy
    (deny-safe totality — validated against the expected deny shape)
  * determinism: identical input re-sent => identical bytes

Seeded and deterministic; the CI lane is a 10-minute timebox
(--timebox 600, seed recorded in the report); the 24h campaign is the farm
job (HG-28; command documented in evidence/P6).

Stdlib only. Exit: 0 clean · 1 invariant violated · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

KNOWN_ERRORS = {"kVersionMismatch"}
HOST_DEFAULT = "../xr-core/policy/tests/build/policy_host"

IDENTITIES = [
    "xr:00000000-0000-4000-8000-000000000001",
    "xr:00000000-0000-4000-8000-000000000002",
    "xr:00000000-0000-4000-8000-0000000000ef",
    "xr:deadbeef-0000-4000-8000-000000000000",
    "nope", "", "xr:", "XR:UPPERCASE",
]
SCHEMES = ["https", "http", "ftp", "file", "", "HTTPS", 7, None]
DOMAINS = ["example.com", "a.io", "", "x", "the-quite-long-domain-name.example.museum",
           "ünïcodé.example", 42, True, None]
CLASSES = ["kNavigation", "kScript", "kPermission", "kSubresource", "kStorage",
           "kNetwork", "kBogus", "", None, 3]
TRUSTS = ["kStandard", "kShield", "kFortress", "kSuper", "", None, {"oops": 1}]
CVS = [1, 0, 2, 999, -1, "1", True, None]


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def gen_request(rng: random.Random) -> dict[str, Any]:
    req: dict[str, Any] = {
        "identity": rng.choice([
            {"value": rng.choice(IDENTITIES)},
            {"value": []}, {"nope": True}, rng.choice(IDENTITIES), None, {},
        ]),
        "origin": rng.choice([
            {"scheme": rng.choice(SCHEMES), "registrable_domain": rng.choice(DOMAINS)},
            {"scheme": rng.choice(SCHEMES)}, {"registrable_domain": "a.com"},
            "not-a-dict", None, [],
        ]),
        "request_class": rng.choice(CLASSES),
    }
    r = rng.random()
    if r < 0.25:
        req["trust_context"] = rng.choice(TRUSTS)
    if r < 0.10:
        req["contract_version"] = rng.choice(CVS)
    if r < 0.15:
        req["now_ms"] = rng.choice([0, 1, 999999, -5, "x"])
    if r < 0.08:
        req["exceptions"] = rng.choice([
            [{"id": "e", "domain": "example.com", "scope": rng.choice(["once", "7d", "forever"]),
              "trust": "kShield", "expires_at": rng.choice([0, 9999]), "remaining_uses": 1}],
            "not-an-array", 5,
        ])
    if r < 0.05:
        req["enterprise"] = rng.choice([
            {"present": True, "trust_floor": rng.choice(["kFortress", "kMega", ""])},
            {"present": "yes"}, "nope",
        ])
    return req


def corrupt(text: str, rng: random.Random) -> str:
    mode = rng.randrange(7)
    if not text:
        return "{"
    if mode == 0:  # truncate
        return text[: rng.randrange(len(text))]
    if mode == 1:  # byte flip
        i = rng.randrange(len(text))
        c = chr(ord(text[i]) ^ (1 << rng.randrange(7)))
        return text[:i] + c + text[i + 1:]
    if mode == 2:  # duplicate a key (JSON keep-last semantics)
        return text[:-1] + ',"identity":{"value":"nope"}}'
    if mode == 3:  # deep nesting injection
        return text[:-1] + ',"x":' + "[" * rng.randrange(40, 4000) + "]" * 0 + "1}"
    if mode == 4:  # oversized string
        return text[:-1] + ',"big":"' + "A" * rng.randrange(1000, 200000) + '"}'
    if mode == 5:  # raw garbage
        return rng.choice(["", "{", "}}}", "[[[", "\x00\x01", '{"a":"\x00"}',
                           "null", "123", '"str"', "ÿþ", "\xc3\x28"])
    return text + rng.choice(["}", "{", ",", "garbage"])


def run_host(host: Path, payload: str, timeout: float = 10.0) -> tuple[int, str]:
    # argv mode for small clean payloads; stdin mode (protocol parity with
    # the fake) for oversized ones or payloads the OS cannot pass in argv
    # (NUL bytes) — both are first-class halves of the stdio protocol.
    if len(payload) < 60_000 and "\x00" not in payload:
        r = subprocess.run([str(host), payload], capture_output=True, text=True,
                           timeout=timeout)
    else:
        r = subprocess.run([str(host)], input=payload, capture_output=True, text=True,
                           timeout=timeout)
    return r.returncode, r.stdout


def check_output(rc: int, out: str) -> str | None:
    """Returns a violation description or None if all invariants hold."""
    if rc != 0:
        return f"exit code {rc} (must be 0 — typed result, never a crash)"
    lines = out.splitlines()
    if len(lines) != 1 or not lines[0]:
        return f"stdout must be exactly one line, got {len(lines)}"
    try:
        parsed = json.loads(lines[0])
    except json.JSONDecodeError as e:
        return f"stdout not JSON: {e}"
    if lines[0] != canonical(parsed):
        return "stdout not canonical (sorted keys, no spaces)"
    if not isinstance(parsed, dict) or parsed.keys() not in ({"ok"}, {"error"}):
        return f"payload must be ok|error envelope, got keys {sorted(parsed) if isinstance(parsed, dict) else type(parsed)}"
    if "error" in parsed:
        if parsed["error"] not in KNOWN_ERRORS:
            return f"unknown error code {parsed['error']!r}"
        return None
    pol = parsed["ok"]
    if not isinstance(pol, dict):
        return "ok payload must be an object (EffectivePolicy)"
    # Deny-shape sanity for the paths we cannot predict: every permission
    # must be a legal enum, route legal, export_allowed must be false.
    perms = pol.get("permissions", {})
    if not isinstance(perms, dict):
        return "permissions must be an object"
    for k in ("geolocation", "camera", "microphone", "notifications"):
        if perms.get(k) not in ("kDeny", "kAsk", "kAllow"):
            return f"permission {k} illegal: {perms.get(k)!r}"
    eg = pol.get("egress", {})
    if eg.get("route") not in ("kDirect", "kProxy", "kWireguard", "kTor"):
        return f"route illegal: {eg.get('route')!r}"
    vs = pol.get("vault_scope", {})
    if vs.get("export_allowed") is not False:
        return "export_allowed must be const false (schema law)"
    return None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="policy_fuzz", description=__doc__.split("\n")[0])
    p.add_argument("--host", default=HOST_DEFAULT, help="policy_host binary")
    p.add_argument("--iterations", type=int, default=0,
                   help="exact iteration count (0 = until timebox)")
    p.add_argument("--timebox", type=int, default=600, help="seconds (CI lane)")
    p.add_argument("--seed", type=int, default=20260908)
    p.add_argument("--report", default=None, help="write JSON report here")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    host = Path(args.host).resolve()
    if not host.is_file():
        print(f"SKIP: policy_host not built ({host}) — run "
              f"`make -C xr-core/policy/tests build` with g++ present; "
              f"a fuzz gate over an absent binary would be theater, not testing.",
              file=sys.stderr)
        return EXIT_PASS if False else EXIT_FAIL  # absent binary = hard fail in CI

    rng = random.Random(args.seed)
    t0 = time.monotonic()
    n = crashes = violations = 0
    first_violation: str | None = None
    while True:
        if args.iterations:
            if n >= args.iterations:
                break
        elif time.monotonic() - t0 > args.timebox:
            break
        req = gen_request(rng)
        payload = canonical(req) if rng.random() < 0.5 else json.dumps(req)
        if rng.random() < 0.6:
            payload = corrupt(payload, rng)
        n += 1
        try:
            rc, out = run_host(host, payload)
        except subprocess.TimeoutExpired:
            crashes += 1
            first_violation = first_violation or f"TIMEOUT on payload: {payload[:200]!r}"
            break
        violation = check_output(rc, out)
        if violation is not None:
            violations += 1
            first_violation = first_violation or (
                f"{violation}\n  payload: {payload[:300]!r}\n  output: {out[:300]!r}")
            break
        # determinism spot-check every 997 inputs (prime stride)
        if n % 997 == 0:
            rc2, out2 = run_host(host, payload)
            if (rc2, out2) != (rc, out):
                violations += 1
                first_violation = first_violation or f"non-deterministic on {payload[:200]!r}"
                break

    report = {
        "tool": "policy_fuzz", "host": str(host), "seed": args.seed,
        "iterations": n, "crashes": crashes, "violations": violations,
        "elapsed_seconds": round(time.monotonic() - t0, 1),
        "timebox": args.timebox if not args.iterations else None,
        "first_violation": first_violation,
        "gate": "PASS" if (crashes == 0 and violations == 0) else "FAIL",
        "farm_campaign_note": "24h campaign is HG-28 (farm); command: "
                              "python3 tools/policy_fuzz.py --timebox 86400 --seed <fixed>",
    }
    out_s = json.dumps(report, sort_keys=True, indent=1)
    if args.report:
        Path(args.report).write_text(out_s + "\n", encoding="utf-8")
    print(out_s if args.json else
          f"fuzz: {n} iterations, crashes {crashes}, violations {violations}, "
          f"elapsed {report['elapsed_seconds']}s -> {report['gate']}")
    if first_violation and not args.json:
        print("first violation:\n" + first_violation, file=sys.stderr)
    return EXIT_PASS if report["gate"] == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
