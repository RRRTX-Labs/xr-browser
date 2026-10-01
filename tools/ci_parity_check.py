#!/usr/bin/env python3
"""tools/ci_parity_check.py — is the local gate weaker than CI's? Print it.

P14-P0-2. The program's fifth local-green/hosted-red cause was a lint whose
strictness depended on which OS packages the host happened to have: actionlint
runs its shellcheck pass only when shellcheck is installed, this sandbox had
actionlint but not shellcheck, and the SC2251 finding rode every local run
green while the hosted governance lane was red (P14-P0-1 fixed the finding;
this tool is the mechanism that would have caught the *gap*).

What it does: diff the LOCAL host's capability against what the WORKFLOWS
actually demand, print one table with a verdict line, and exit 0 either way —
deliberately not a gate red, because a laptop legitimately lacks CI's tools.
The honesty mechanism is that a reader can see it: `run_checks.sh` echoes the
verdict line in its final tally, and evidence/P<n>/report.md section ⑨ must
quote it (a phase may not report "gate green" while the parity line says five
lanes were weaker locally).

Five probes (the host measurements live in tools/ci_parity_probes.py), each
re-proved at run time and never inherited from a note:

  1. optional tools — docs/dependencies/helper-tools.yaml + every workflow's
     install steps (apt names, pinned release URLs) + the runner-capabilities
     ledger (docs/state/runner-capabilities.json, every entry proven by a real
     run), reported present/ABSENT per tool with what a local absence means
     for the lane, including the COMPOSITE case (actionlint present but
     shellcheck absent => "the shellcheck pass will not run here");
  2. entry-point modes — tools/entrypoint_mode_check.py --json, reused, not
     re-implemented (P13-P0-A's law);
  3. sibling pin — tools/xr_sibling.py, the ONE sibling resolver (P13-C-P0.2);
  4. dev-dep installability — tools/dev_deps_closure_check.py (offline fixture
     path) + a live `pip --require-hashes --dry-run` probe when pip+network
     cooperate, so a pin CI cannot install is caught pre-push;
  5. network reachability — one GET per allowlisted host through the fetch
     chokepoint, under one deadline, with the api.github.com quota printed
     alongside (a 403 from an exhausted quota is not an access denial).

CLI: [--json] [--self-test] [--deadline SECONDS]. Exit 0 on PASS *and* on
PARTIAL (the verdict is a printed fact, not a gate); 2 usage; 1 only for the
--self-test's own failure. Stdlib + PyYAML (pinned dev dep) only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import ci_parity_probes as cpn

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
HELPER_TOOLS = "docs/dependencies/helper-tools.yaml"
RUNNER_CAPS = "docs/state/runner-capabilities.json"
DEFAULT_DEADLINE_S = 20.0

# What a LOCAL absence of each tool means for the lanes (the "stricter there"
# half of the row). Tools whose absence is normal on a Linux lane carry
# `counted=False` so they never inflate the verdict.
TOOL_LANES: dict[str, dict[str, Any]] = {
    "actionlint": {"lane": "workflow-lint deep pass (expressions+schema)",
                   "counted": True},
    "shellcheck": {"lane": "actionlint's shell-script pass (the SC2251 class)",
                   "counted": True},
    "faketime": {"lane": "date-invariance ambient probe (the scheduled "
                        "governance lane installs it and demands it)",
                 "counted": True},
    "minisign": {"lane": "P3 fast-lane TEST signing drill", "counted": True},
    "g++": {"lane": "the discovered C++ suite lanes + the differential oracle",
            "counted": True},
    "make": {"lane": "the discovered C++ suite lanes", "counted": True},
    "cargo": {"lane": "Rust conformance + shield vendor/shim lanes", "counted": True},
    "rustc": {"lane": "Rust conformance + shield vendor/shim lanes", "counted": True},
    "node": {"lane": "WebUI toolchain + panel lanes", "counted": True},
    "npm": {"lane": "WebUI toolchain + panel lanes (registry-dependent)",
            "counted": True},
    "codesign": {"lane": "macOS-only TEST signing passthrough — absent on "
                         "Linux lanes by design", "counted": False},
    "signtool": {"lane": "Windows-only TEST signing passthrough — absent on "
                         "Linux lanes by design", "counted": False},
}
APT_INSTALL_RE = re.compile(r"apt-get\s+install\s+([^\n|;&]+)", re.IGNORECASE)
RELEASE_URL_RE = re.compile(r"releases/download/v[^/\"']+/([A-Za-z0-9_-]+)_")


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # pinned dev dep (ADR-0001 set); tools/ may import it
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    return doc if isinstance(doc, dict) else {}


def demanded_tools(repo: Path) -> dict[str, str]:
    """The tool set CI's lanes demand: helper-tools.yaml + workflow install
    steps (apt names, pinned release URLs) + the runner-capabilities ledger.
    Returns name -> source description."""
    out: dict[str, str] = {}
    for t in _load_yaml(repo / HELPER_TOOLS).get("tools") or []:
        name = str(t.get("name") or "").strip()
        if name:
            out.setdefault(name, f"{HELPER_TOOLS} (helper tool entry)")
    wf_dir = repo / ".github" / "workflows"
    for wf in sorted(wf_dir.glob("*.yml")) if wf_dir.is_dir() else []:
        text = wf.read_text(encoding="utf-8", errors="replace")
        for m in APT_INSTALL_RE.finditer(text):
            for pkg in re.findall(r"[a-z0-9][a-z0-9.+-]*", m.group(1)):
                if pkg in ("sudo", "y", "qq", "update"):
                    continue
                out.setdefault(pkg, f"{wf.relative_to(repo)} (apt-get install)")
        for m in RELEASE_URL_RE.finditer(text):
            out.setdefault(m.group(1).lower(),
                           f"{wf.relative_to(repo)} (pinned release tarball)")
    try:
        caps = json.loads((repo / RUNNER_CAPS).read_text(encoding="utf-8"))
        for name, entry in (caps.get("capabilities") or {}).items():
            if isinstance(entry, dict) and entry.get("present") is True:
                out.setdefault(name, f"{RUNNER_CAPS} (proven on the runner)")
    except (OSError, json.JSONDecodeError):
        pass
    return out


def tool_rows(present: set[str], demanded: dict[str, str]) -> list[dict[str, Any]]:
    """One row per demanded tool: present/ABSENT + what it means locally."""
    import platform
    rows: list[dict[str, Any]] = []
    for name in sorted(demanded):
        # A runner-capabilities python entry ("python3.12") is a VERSION
        # comparison, not presence: the local interpreter exists under a
        # different minor. The difference is printed; it is not "stricter".
        if re.fullmatch(r"python3\.\d+", name) and shutil.which("python3"):
            rows.append({
                "tool": name, "present": False, "demanded_by": demanded[name],
                "lane": "the gate runs on python either way",
                "counts_stricter": False,
                "status": (f"differs (local interpreter "
                           f"{platform.python_version()} vs the runner's "
                           f"pinned {name}; a version gap is a printed note, "
                           "not a weaker lane)"),
            })
            continue
        info = TOOL_LANES.get(name, {"lane": "a lane demands it", "counted": True})
        on = name in present
        rows.append({
            "tool": name, "present": on, "demanded_by": demanded[name],
            "lane": info["lane"], "counts_stricter": bool(info["counted"]) and not on,
            "status": ("present" if on else
                       ("ABSENT (CI has this; the lane will be stricter there)"
                        if info["counted"] else
                        "absent (normal for a Linux lane; not stricter on CI)")),
        })
    # The composite case: actionlint's shellcheck pass needs BOTH.
    if "actionlint" in present and "shellcheck" not in present:
        rows.append({
            "tool": "actionlint+shellcheck", "present": False,
            "demanded_by": HELPER_TOOLS + " (composite)",
            "lane": "actionlint's shellcheck pass", "counts_stricter": True,
            "status": ("COMPOSITE GAP: actionlint present but shellcheck absent "
                       "=> the shellcheck pass will not run here — the exact "
                       "shape of the P13-CLOSE governance red"),
        })
    return rows


def verdict_of(rows: list[dict[str, Any]], entry: dict[str, Any],
               deps: dict[str, Any],
               net: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """PASS, or PARTIAL naming every lane that will be stricter on CI."""
    stricter: list[str] = [f"{r['tool']} ({r['lane']})"
                           for r in rows if r.get("counts_stricter")]
    stricter += [f"net:{r['host']} (network-dependent lanes)"
                 for r in net if r.get("counts_stricter")]
    if entry.get("status") == "FAIL":
        stricter.append("entry-point modes (the mode gate is red HERE and on CI)")
    if isinstance(deps.get("closure"), str) and deps["closure"].startswith("FAIL"):
        stricter.append("dev-dep closure (red here; CI installs the same pins)")
    return ("PARTIAL", stricter) if stricter else ("PASS", [])


def run_probes(repo: Path, deadline_s: float) -> dict[str, Any]:
    present = {name for name in set(TOOL_LANES) if shutil.which(name)}
    rows = tool_rows(present, demanded_tools(repo))
    entry = cpn.probe_entrypoints(repo)
    sib = cpn.probe_sibling(repo)
    deps = cpn.probe_devdeps(repo)
    net = cpn.probe_hosts(deadline_s)
    verdict, stricter = verdict_of(rows, entry, deps, net)
    return {"tools": rows, "entrypoints": entry, "sibling": sib,
            "devdeps": deps, "network": net,
            "rate_limit": cpn.rate_limit_note(net),
            "verdict": verdict, "stricter_lanes": stricter}


def _print(doc: dict[str, Any]) -> None:
    print("== ci-parity: local capability vs hosted lanes (P14-P0-2) ==")
    print("  optional tools (helper-tools.yaml + workflow installs + runner ledger):")
    for r in doc["tools"]:
        print(f"    {r['tool']:<18} {r['status']}")
    e = doc["entrypoints"]
    print(f"  entry-point modes: {e.get('status')} ({e.get('detail', '')})")
    s = doc["sibling"]
    print(f"  sibling pin: {s.get('status')} — {s.get('detail', '')}")
    d = doc["devdeps"]
    print(f"  dev-deps: closure check {d.get('closure')}; "
          f"pip dry-run: {d.get('pip_dry_run')}")
    print("  network (live probes through the fetch chokepoint, re-proved now,")
    print("           never inherited from any note):")
    for r in doc["network"]:
        print(f"    {r['host']:<36} {r['result']:<10} {r['detail']}")
    if doc.get("rate_limit"):
        print(f"    {doc['rate_limit']}")
    if doc["verdict"] == "PASS":
        print("ci-parity: PASS (no probed lane is stricter on CI than here)")
    else:
        n = len(doc["stricter_lanes"])
        print(f"ci-parity: PARTIAL ({n} lane(s) will be stricter on CI: "
              f"{'; '.join(doc['stricter_lanes'])}) — exit 0 by design: a "
              "printed fact, never a gate red; re-run to re-prove")


def _self_test() -> int:
    """Prove the verdict is a function of the host, not a constant. Offline."""
    import tempfile
    ok = True

    def check(label: str, cond: bool) -> None:
        nonlocal ok
        print(f"  {'ok' if cond else 'FAIL'}: {label}")
        ok = ok and cond

    print("ci_parity --self-test:")
    rows = tool_rows(present={"actionlint", "shellcheck"},
                     demanded={"actionlint": "x", "shellcheck": "x",
                               "faketime": "x", "signtool": "x"})
    absent = [r for r in rows if r["tool"] == "faketime"][0]
    win = [r for r in rows if r["tool"] == "signtool"][0]
    check("absent CI tool -> ABSENT row that counts",
          absent["counts_stricter"] and "ABSENT" in absent["status"])
    check("platform-optional absence does not count", not win["counts_stricter"])
    with_gap = [r for r in tool_rows({"actionlint"}, {"actionlint": "x",
                                                      "shellcheck": "x"})
                if r["tool"] == "actionlint+shellcheck"]
    without = [r for r in tool_rows({"actionlint", "shellcheck"},
                                    {"actionlint": "x", "shellcheck": "x"})
               if r["tool"] == "actionlint+shellcheck"]
    check("actionlint-without-shellcheck => composite row",
          len(with_gap) == 1 and with_gap[0]["counts_stricter"])
    check("both present => no composite row", not without)

    class Fake(Exception):
        pass
    k1, d1, c1 = cpn.classify(Fake("fetch failed for u after 3 attempts: "
                                   "HTTP Error 503: Service Unavailable"))
    k2, d2, c2 = cpn.classify(Fake("HTTP 403 fetching u"))
    k3, d3, c3 = cpn.classify(Fake("host 'x' not on the fetch allowlist "
                                   "(allowed: []); refusing 'u'"))
    check("retryable 5xx -> blocked, counted (the P13 shape)",
          k1 == "blocked" and "HTTP 503" in d1 and c1)
    check("4xx -> reachable (the host answered; not a stricter lane)",
          k2 == "reachable" and "HTTP 403" in d2 and not c2)
    check("chokepoint refusal -> refused, never a probe",
          k3 == "refused" and not c3)
    v_pass, _ = verdict_of(
        tool_rows({"actionlint", "shellcheck", "faketime"},
                  {"actionlint": "x", "shellcheck": "x", "faketime": "x"}),
        {"status": "PASS"}, {"closure": "PASS"}, [])
    v_part, s_part = verdict_of(rows, {"status": "PASS"}, {"closure": "PASS"},
                                [])
    check("all-present host => PASS", v_pass == "PASS")
    check("gap host => PARTIAL naming faketime",
          v_part == "PARTIAL" and any("faketime" in x for x in s_part))
    v2, s2 = verdict_of([], {"status": "FAIL", "detail": "2"},
                        {"closure": "FAIL (exit 1)"}, [])
    check("red mode/closure lanes are named", v2 == "PARTIAL" and len(s2) == 2)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".github" / "workflows").mkdir(parents=True)
        # The fixture carries the release-tarball PATH (no scheme/host: no
        # URL literal lives in this tool — the fetch_allowlist law; the
        # full-URL parsing fidelity is pinned in tools/tests/test_ci_parity.py
        # where URL fixture data is sanctioned).
        (root / ".github" / "workflows" / "g.yml").write_text(
            "run: |\n  sudo apt-get install -y -qq minisign faketime\n"
            "  curl -sSL -o /tmp/al.tgz \"/releases/download/v1.7.7/"
            "actionlint_1.7.7_linux_amd64.tar.gz\"\n", encoding="utf-8")
        dem = demanded_tools(root)
        check("apt names parsed", {"minisign", "faketime"} <= set(dem))
        check("release tarball tool parsed", "actionlint" in dem)
    print("PASS: ci_parity --self-test" if ok else "FAIL: ci_parity --self-test")
    return EXIT_PASS if ok else EXIT_FAIL


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="local-host capability vs workflow demand (P14-P0-2)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_S,
                    help="network probe deadline in seconds (default 20)")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    here = Path(__file__).resolve().parents[1]
    os.chdir(here)
    doc = run_probes(here, max(3.0, args.deadline))
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        _print(doc)
    return EXIT_PASS  # PASS and PARTIAL both exit 0 — by design


if __name__ == "__main__":
    sys.exit(main())
