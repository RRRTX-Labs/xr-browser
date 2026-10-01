#!/usr/bin/env python3
"""tools/ci_parity_probes.py — the host probes behind ci_parity_check.

P14-P0-2. Split from tools/ci_parity_check.py by responsibility (the
touched-file size law, same pattern as evidence_ci/evidence_check): the
capability table, verdict and CLI live there; the actual host measurements
live here. Four probes, each reused-not-reimplemented where a law already
exists:

  * probe_entrypoints — tools/entrypoint_mode_check.py (P13-P0-A's law);
  * probe_sibling    — tools/xr_sibling.py, the ONE sibling resolver
                       (P13-C-P0.2);
  * probe_devdeps    — tools/dev_deps_closure_check.py (the offline fixture
                       path) + a live `pip --require-hashes --dry-run`;
  * probe_hosts      — one GET per allowlisted host through the
                       build/upstream/fetch.py chokepoint (the only network
                       call in the tree), concurrently under one deadline,
                       with the api.github.com quota printed alongside.

Network law: every HTTP call goes through the chokepoint; a blocked row is
re-proved at every run and NEVER inherited from a note (the P13 lesson:
chromium.googlesource.com recorded 503 was 200 hours later, and api.github.com
403s were an exhausted unauthenticated quota, not an access denial —
RATE-LIMITED vs ADMIN-ONLY stays a data question).

Stdlib only; offline-safe (a failed probe is a row, never a crash).
"""
from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

EGRESS = "release/egress-allowlist.json"
PROBE_PATHS_DATA = "docs/state/parity-probe-paths.json"
HTTP_RE = re.compile(r"HTTP(?: Error)? (\d{3})")


def probe_entrypoints(repo: Path) -> dict[str, Any]:
    """Reuse P13's law-runner; never re-implement it."""
    tool = repo / "tools" / "entrypoint_mode_check.py"
    if not tool.is_file():
        return {"status": "BLOCKED-LAYOUT", "detail": f"{tool} absent"}
    try:
        proc = subprocess.run(
            [sys.executable, str(tool), "--json"], cwd=str(repo),
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "BLOCKED", "detail": f"{type(exc).__name__}: {exc}"}
    try:
        findings = json.loads(proc.stdout).get("findings") or []
    except json.JSONDecodeError:
        return {"status": "BLOCKED",
                "detail": f"unparseable output (exit {proc.returncode})"}
    return {"status": "PASS" if proc.returncode == 0 else "FAIL",
            "detail": f"{len(findings)} finding(s)", "counts_stricter": False}


def probe_sibling(repo: Path) -> dict[str, Any]:
    """The ONE sibling resolver (P13-C-P0.2)."""
    sys.path.insert(0, str(repo / "tools"))
    try:
        import xr_sibling  # noqa: PLC0415 — the documented resolver
        try:
            sib = xr_sibling.check(repo)
            return {"status": "PASS",
                    "detail": (f"../xr-core at DEPS.xr_core_rev "
                               f"{sib.head[:12]}… (clean)" if sib.head else "ok"),
                    "counts_stricter": False}
        except xr_sibling.SiblingError as err:
            return {"status": err.code, "detail": xr_sibling.format_error(err),
                    "counts_stricter": False}
    except ImportError as exc:
        return {"status": "BLOCKED-LAYOUT", "detail": f"resolver import: {exc}"}
    finally:
        sys.path.remove(str(repo / "tools"))


def probe_devdeps(repo: Path) -> dict[str, Any]:
    """The closure check (offline fixture path) + a live pip dry-run probe."""
    out: dict[str, Any] = {"closure": None, "pip_dry_run": None,
                           "counts_stricter": False}
    tool = repo / "tools" / "dev_deps_closure_check.py"
    if tool.is_file():
        try:
            proc = subprocess.run(
                [sys.executable, str(tool), "--repo", str(repo)],
                capture_output=True, text=True, timeout=180)
            out["closure"] = ("PASS" if proc.returncode == 0
                              else f"FAIL (exit {proc.returncode})")
        except (OSError, subprocess.TimeoutExpired) as exc:
            out["closure"] = f"BLOCKED ({type(exc).__name__})"
    req = repo / "tools" / "requirements-dev.txt"
    if req.is_file() and shutil.which("pip"):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--require-hashes",
                 "-r", str(req), "--dry-run", "--quiet"],
                capture_output=True, text=True, timeout=90)
            out["pip_dry_run"] = ("installable (require-hashes dry run ok)"
                                  if proc.returncode == 0
                                  else f"NOT installable here (exit "
                                       f"{proc.returncode}; network weather "
                                       f"counts — see the network rows)")
        except subprocess.TimeoutExpired:
            out["pip_dry_run"] = "no answer within 90 s (treated as blocked)"
        except OSError as exc:
            out["pip_dry_run"] = f"BLOCKED ({type(exc).__name__})"
    elif not shutil.which("pip"):
        out["pip_dry_run"] = "pip absent here (CI installs with pip)"
    return out


def fetch_module() -> Any:
    """Load build/upstream/fetch.py — the network chokepoint. The
    collision-safe _common preload pattern is tools/ci_triage.py's; identical
    reason (whichever _common lands in sys.modules first wins)."""
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    saved = sys.modules.get("_common")
    cspec = importlib.util.spec_from_file_location(
        "_common", root / "build" / "_common.py")
    cmod = importlib.util.module_from_spec(cspec)
    sys.modules["_common"] = cmod
    try:
        cspec.loader.exec_module(cmod)
        fspec = importlib.util.spec_from_file_location(
            "upstream_fetch", root / "build" / "upstream" / "fetch.py")
        fmod = importlib.util.module_from_spec(fspec)
        sys.modules["upstream_fetch"] = fmod
        fspec.loader.exec_module(fmod)
        return fmod
    finally:
        if saved is None:
            sys.modules.pop("_common", None)
        else:
            sys.modules["_common"] = saved


def classify(exc: Exception) -> tuple[str, str, bool]:
    """(kind, human, counts_stricter) for a fetch failure. A 4xx answer still
    proves the network path (DNS, routing, TLS) works — the host is reachable
    and the row does not count as a stricter-on-CI lane; only a 5xx, a
    timeout or a connection failure is 'blocked' (the P13 shape: a 503 from
    chromium.googlesource.com was a real lane blocker, re-proved later at
    200). The code is carried either way — a 429 is rate-limit, a 403 may be
    quota OR admin; ci_triage's job to say which, this row's job to carry the
    number."""
    msg = str(exc)
    m = HTTP_RE.search(msg)
    if m:
        code = int(m.group(1))
        if code < 500:
            return ("reachable", f"HTTP {code} (the host answered; the probe "
                                 "path is not a valid object there)", False)
        return ("blocked", f"HTTP {code} (server-side; re-proved next run)",
                True)
    if "not on the fetch allowlist" in msg:
        return "refused", ("chokepoint refuses (not a fetch surface — "
                           "release-client policy data, HG-38)"), False
    return "blocked", re.sub(r"\s+", " ", msg)[:100], True


def load_probe_paths(repo: Path) -> dict[str, str]:
    """host -> canonical read-only path, from the REVIEWABLE DATA file
    (docs/state/parity-probe-paths.json — same class as
    release/egress-allowlist.json). No URL literals live in code: the
    chokepoint (fetch.py ALLOWED_HOSTS + assert_url_allowed) stays the ONLY
    enforcement of which hosts may be fetched, and it runs on every http_get
    regardless of what the data says."""
    try:
        doc = json.loads((repo / PROBE_PATHS_DATA).read_text(encoding="utf-8"))
        return {str(r["host"]): str(r["path"])
                for r in doc.get("probe_paths") or []}
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return {}


def probe_hosts(deadline_s: float) -> list[dict[str, Any]]:
    """One GET per allowlisted host + egress-policy hosts, concurrently, under
    one deadline, each at its canonical path from the data file. Slow or
    silent hosts are reported blocked-with-deadline, never omitted."""
    repo = Path(__file__).resolve().parents[1]
    try:
        fetch = fetch_module()
    except Exception as exc:  # noqa: BLE001 — report, never crash the gate
        return [{"host": "(all)", "result": "blocked",
                 "detail": f"chokepoint load failed: {exc}",
                 "counts_stricter": False}]
    paths = load_probe_paths(repo)
    results: dict[str, dict[str, Any]] = {}
    for host in sorted(fetch.ALLOWED_HOSTS):
        url = paths.get(host)
        if url is None:
            # Completeness law: a host may join the fetch allowlist without a
            # canonical probe path only VISIBLY — the row names the gap, it
            # never silently skips the host.
            results[host] = {"result": "blocked",
                             "detail": (f"no canonical probe path in "
                                        f"{PROBE_PATHS_DATA} — add one there; "
                                        "not probed"),
                             "counts_stricter": True}
    # Egress-policy hosts (release client surface) are NOT on the fetch
    # allowlist by design: the chokepoint refuses them, so the row says so
    # without building or fetching anything (policy data for HG-38, not a
    # fetch surface).
    try:
        eg = json.loads((repo / EGRESS).read_text(encoding="utf-8"))
        for row in eg.get("client_egress") or []:
            h = str(row.get("host") or "")
            if h and h not in fetch.ALLOWED_HOSTS:
                results[h] = {"result": "refused",
                              "detail": ("chokepoint refuses (not a fetch "
                                         "surface — release-client policy "
                                         "data, HG-38)"),
                              "counts_stricter": False}
    except (OSError, json.JSONDecodeError):
        pass
    todo = {h: paths[h] for h in paths if h not in results}
    q: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue()

    def work(host: str, url: str) -> None:
        t0 = time.monotonic()
        try:
            fetch.http_get(url, timeout=max(3, int(deadline_s / 3)))
            q.put((host, {"result": "reachable",
                          "detail": f"{time.monotonic() - t0:.2f} s",
                          "counts_stricter": False}))
        except Exception as exc:  # noqa: BLE001 — classified, never fatal
            kind, detail, counts = classify(exc)
            q.put((host, {"result": kind, "detail": detail,
                          "counts_stricter": counts}))

    threads = [threading.Thread(target=work, args=(h, u), daemon=True)
               for h, u in todo.items()]
    for t in threads:
        t.start()
    deadline = time.monotonic() + deadline_s
    while any(h not in results for h in todo) and time.monotonic() < deadline:
        try:
            host, row = q.get(timeout=max(0.1, deadline - time.monotonic()))
            results[host] = row
        except queue.Empty:
            break
    for h in todo:
        if h not in results:
            results[h] = {"result": "blocked",
                          "detail": (f"no answer within the {deadline_s:.0f} s "
                                     "probe deadline (re-proved next run)"),
                          "counts_stricter": True}
    return [{"host": h, **results[h]} for h in sorted(results)]


def rate_limit_note(rows: list[dict[str, Any]]) -> str:
    """The api.github.com quota line, when it answered. /rate_limit is free
    (it does not consume quota) and is what separates RATE-LIMITED from
    ADMIN-ONLY (P13-CLOSE C-0.7)."""
    for r in rows:
        if r["host"] == "api.github.com" and r["result"] == "reachable":
            try:
                f = fetch_module()
                raw = f.http_get(load_probe_paths(
                    Path(__file__).resolve().parents[1])["api.github.com"],
                    timeout=6)
                core = json.loads(raw.decode("utf-8")).get(
                    "resources", {}).get("core", {})
                return (f"api.github.com quota: core "
                        f"{core.get('used')}/{core.get('limit')}, "
                        f"reset {core.get('reset')} (epoch)")
            except Exception:  # noqa: BLE001 — the note is best-effort
                return "api.github.com quota: unreachable on the second ask"
    return ""
