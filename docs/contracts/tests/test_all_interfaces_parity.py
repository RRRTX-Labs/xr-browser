"""Fake-parity across ALL interfaces via xrctl stdio protocol (P9 inherits
this shape). Drives each fake through tools/xrctl.py and asserts the fake
returns a well-formed typed result (ok/error)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
XRCTL = REPO / "tools" / "xrctl.py"

CALLS = [
    ("policy_resolver", "Resolve", {"identity": {"value": "xr:00000000-0000-4000-8000-000000000001"}, "origin": {"scheme": "https", "registrable_domain": "example.com"}, "request_class": "kNavigation"}),
    ("identity", "Create", {"grade": "kStandard"}),
    ("shield", "Status", {"identity": {"value": "x"}, "origin": {"scheme": "https", "registrable_domain": "example.com"}}),
    ("route_manager", "LoseAllFailClosed", {}),
    ("vault", "Totp", {"item_id": "it-1"}),
    ("guard", "Dispatch", {"request": {"identity": {"value": "x"}, "extension_id": "e", "api_call": "storage.local.get", "request_class": "kScript"}}),
    ("downloads", "Scan", {"content_sha256": "safe123", "mime_type": "video/mp4"}),
    ("activity_log", "Query", {"max_rows": 3}),
]


def xrctl(iface, method, args):
    return subprocess.run([sys.executable, str(XRCTL), "call", iface, method, json.dumps(args)],
                          cwd=REPO, capture_output=True, text=True)


def test_every_interface_returns_typed_result():
    for iface, method, args in CALLS:
        r = xrctl(iface, method, args)
        assert r.returncode == 0, f"{iface}.{method}: {r.stderr}"
        out = json.loads(r.stdout)
        assert ("ok" in out) or ("error" in out), f"{iface}.{method}: {out}"


def test_route_manager_fail_closed_shape():
    r = xrctl("route_manager", "LoseAllFailClosed", {})
    out = json.loads(r.stdout)["ok"]
    assert out["state"] == "kFailClosed"
    assert out["user_ack_required"] is True


def test_vault_never_exports_seed():
    r = xrctl("vault", "GetField", {"item_id": "it-1", "field_name": "totp_seed"})
    out = json.loads(r.stdout)
    assert out.get("error") == "kNotPermitted"
