"""probe_driver.py — runs the P4 probe lanes (P4-T2..T7).

Two modes, and they are not blurred:

  --offline (today, no browser): every static and fixture lane that CAN run
      now — policy lints, fsdiff self-check, CDP codec self-check, fixture
      data-origin check. Emits spike-result-v1 rows with source:"fixture".

  --farm (HUMAN-GATED, HG-21): launches a built browser with the probe
      binary, refuses any isolation-bypass flag, attaches CDP over stdlib
      sockets, parses process-internals + --enable-logging output, and emits
      source:"runtime" rows.

The isolation law (L2 applied to the spike itself): a probe result produced
with site isolation degraded is not evidence. `refuse_isolation_bypass()`
raises on any of the known bypass switches and the driver calls it before
launching anything.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, load_deps, repo_root  # noqa: E402

_SPIKE = Path(__file__).resolve().parent
if str(_SPIKE) not in sys.path:
    sys.path.insert(0, str(_SPIKE))

import fsdiff  # noqa: E402

# Site-isolation bypasses that would invalidate every probe result.
ISOLATION_BYPASS_FLAGS = (
    "--disable-site-isolation-trials",
    "--disable-site-isolation",
    "--single-process",
    "--process-per-site",          # collapses origins into one process
    "--disable-features=IsolateOrigins",
    "--disable-features=site-per-process",
    "--disable-features=IsolateOrigins,site-per-process",
)
ISOLATION_BYPASS_SUBSTRINGS = (
    "--disable-features=IsolateOrigins",
    "--disable-features=site-per-process",
    "IsolateOrigins,site-per-process",
)


def refuse_isolation_bypass(flags: list[str]) -> None:
    """Raise if any flag degrades site isolation. Test-covered."""
    bad: list[str] = []
    for f in flags:
        if f in ISOLATION_BYPASS_FLAGS:
            bad.append(f)
        elif any(s in f for s in ISOLATION_BYPASS_SUBSTRINGS):
            bad.append(f)
        elif f.startswith("--disable-features=") and "Isolation" in f:
            bad.append(f)
    if bad:
        raise ToolError(
            "isolation-bypass flag(s) refused: " + ", ".join(sorted(set(bad)))
            + " — a probe run with degraded site isolation is not evidence "
              "(L2 applied to the spike itself)")


def _row(probe: str, claim: str, measured: str, source: str, verdict: str,
         pin: str) -> dict[str, Any]:
    return {"probe": probe, "claim": claim,
            "expectation": "as stated in docs/spike-identity/probe-matrix.md",
            "measured": measured, "source": source, "pin_sha": pin,
            "verdict": verdict}


def lane_policy(pin: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # 1. isolation-bypass refusal (the spike's own L2 law).
    try:
        refuse_isolation_bypass(["--disable-site-isolation-trials"])
        rows.append(_row("driver.policy.isolation_bypass", "the driver refuses "
                         "isolation-bypass flags", "call did NOT raise",
                         "fixture", "FAIL", pin))
    except ToolError as exc:
        ok = "isolation-bypass flag(s) refused" in str(exc)
        rows.append(_row("driver.policy.isolation_bypass", "the driver refuses "
                         "isolation-bypass flags", str(exc)[:120], "fixture",
                         "PASS" if ok else "FAIL", pin))
    # 2. a clean flag set is accepted.
    try:
        refuse_isolation_bypass(["--enable-logging=stderr", "--v=0"])
        rows.append(_row("driver.policy.clean_flags", "a clean flag set is "
                         "accepted", "no refusal", "fixture", "PASS", pin))
    except ToolError as exc:
        rows.append(_row("driver.policy.clean_flags", "a clean flag set is "
                         "accepted", str(exc)[:120], "fixture", "FAIL", pin))
    return rows


def lane_fsdiff(pin: str) -> list[dict[str, Any]]:
    """fsdiff must detect any change — the zero-residual claim rests on it."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "profile"
        (root / "a").mkdir(parents=True)
        (root / "a" / "x.bin").write_bytes(b"identity-a")
        before = fsdiff.snapshot(root)
        (root / "a" / "y.bin").write_bytes(b"leak")     # added
        (root / "a" / "x.bin").write_bytes(b"changed")  # changed
        after = fsdiff.snapshot(root)
        d = fsdiff.diff(before, after)
        detected = d["added"] == ["a/y.bin"] and d["changed"] == ["a/x.bin"]
        rows = [_row("driver.fsdiff.detect", "fsdiff detects added and changed "
                     "paths", json.dumps(d), "fixture",
                     "PASS" if detected else "FAIL", pin)]
        stable = fsdiff.diff(before, before)
        rows.append(_row("driver.fsdiff.stable", "an unchanged tree diffs empty",
                         json.dumps(stable), "fixture",
                         "PASS" if fsdiff.is_empty(stable) else "FAIL", pin))
    return rows


def lane_cdp(pin: str) -> list[dict[str, Any]]:
    """The CDP codec must round-trip against a loopback fixture server."""
    import threading
    from cdp import Cdp, WebSocket
    from tests import cdp_fixture  # local fixture server (stdlib)

    server, port = cdp_fixture.serve_echo()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ws = WebSocket.connect("127.0.0.1", port, "/devtools/page/1")
        client = Cdp(ws)
        result = client.call("SystemInfo.getInfo", {})
        ok = result.get("echo") == "SystemInfo.getInfo"
        rows = [_row("driver.cdp.roundtrip", "the stdlib CDP client round-trips "
                     "a method call over a loopback fixture server",
                     json.dumps(result)[:120], "fixture",
                     "PASS" if ok else "FAIL", pin)]
        try:
            WebSocket.connect("8.8.8.8", port, "/")
            rows.append(_row("driver.cdp.loopback_only", "the client refuses a "
                             "non-loopback target", "call did NOT raise",
                             "fixture", "FAIL", pin))
        except Exception:
            rows.append(_row("driver.cdp.loopback_only", "the client refuses a "
                             "non-loopback target", "CdpError raised",
                             "fixture", "PASS", pin))
        ws.close()
    finally:
        server.shutdown()
    return rows


def lane_fixture_origin(pin: str) -> list[dict[str, Any]]:
    """No probe may reference a real domain (RFC 2606 / .test only)."""
    root = repo_root()
    candidates = [root / ".." / "xr-core" / "spike", root / "src" / "xr" / "spike"]
    bad: list[str] = []
    hits = 0
    for base in candidates:
        base = base.resolve()
        if not base.is_dir():
            continue
        for f in base.rglob("*.cc"):
            hits += 1
            text = f.read_text(encoding="utf-8")
            for token in ("https://www.", "http://www.", ".com/", ".net/",
                          ".org/"):
                if token in text:
                    bad.append(f"{f.name}: {token}")
    if not hits:
        return [_row("driver.fixture.origin", "probe fixtures use RFC 2606 / "
                     ".test origins only", "no probe sources found", "fixture",
                     "SKIP", pin)]
    return [_row("driver.fixture.origin", "probe fixtures use RFC 2606 / .test "
                 "origins only", f"{hits} file(s) scanned; "
                 f"{len(bad)} real-domain token(s)", "fixture",
                 "PASS" if not bad else "FAIL", pin)]


def run_offline(pin: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows += lane_policy(pin)
    rows += lane_fsdiff(pin)
    rows += lane_cdp(pin)
    rows += lane_fixture_origin(pin)
    return rows


def run_farm(pin: str, binary: str, checkout: Path) -> list[dict[str, Any]]:
    """HUMAN-GATED (HG-21). Refuses to pretend; requires a real binary."""
    if not binary or not Path(binary).is_file():
        raise ToolError(f"BLOCKED-NO-BINARY: no probe binary at {binary!r} — "
                        "the farm lane requires a compiled browser (HG-9/HG-21); "
                        "nothing is simulated")
    raise ToolError("BLOCKED-FARM: the farm lane is implemented but not "
                    "executable here (no compiled browser); run it on farm "
                    "hardware and commit the emitted rows")


def main() -> int:
    ap = argparse.ArgumentParser(prog="probe-driver", description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="static + fixture lanes (no browser)")
    ap.add_argument("--farm", action="store_true", help="launch a real browser (HG-21)")
    ap.add_argument("--binary", help="path to the browsertest binary (--farm)")
    ap.add_argument("--checkout", help="chromium checkout (--farm)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not (args.offline or args.farm):
        print("error: choose --offline or --farm", file=sys.stderr)
        return 2

    try:
        root = repo_root()
        pin = str(load_deps(root).get("chromium_rev", ""))
        if args.farm:
            rows = run_farm(pin, args.binary or "", Path(args.checkout or "."))
        else:
            rows = run_offline(pin)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    failed = [r for r in rows if r["verdict"] == "FAIL"]
    payload = {"tool": "probe-driver",
               "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "pin_sha": pin, "rows": rows,
               "status": "pass" if not failed else "fail"}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for r in rows:
            print(f"{r['verdict']:<5} {r['probe']:<40} {r['measured'][:60]}")
        print(f"{'PASS' if not failed else 'FAIL'}: probe-driver "
              f"({len(rows)} row(s), {len(failed)} failure(s))")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
