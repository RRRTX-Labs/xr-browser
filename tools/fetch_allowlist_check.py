"""tools/fetch_allowlist_check.py — enforce the network chokepoint (P3).

Law: ALL network access in this repository flows through
build/upstream/fetch.py, whose allowlist is: chromium.googlesource.com,
commondatastorage.googleapis.com, chromiumdash.appspot.com, api.github.com,
static.crates.io (P11-T1, ADR-0044 ceremony — pinned crate tarballs only).

This static check fails when any Python file OUTSIDE the chokepoint (or the
vendored-schema-free governance tools that must not talk to the network at
all) opens sockets, uses urllib, or embeds http(s) URLs in code (docstrings
and comments are exempt; every violation is printed with the line).

Usage:  python tools/fetch_allowlist_check.py [--json]
Exit 0 = clean; 1 = violations; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHOKEPOINT = "build/upstream/fetch.py"
# tools that legitimately reference URLs in checks (linters over docs data)
DOC_DATA_EXEMPT = re.compile(r"docs/(dependencies|state)/")

# DOCUMENTED pre-chokepoint exceptions (P2 tools that predate fetch.py).
# Each entry: file -> justification. A new entry needs an ADR or research-log
# row; undocumented network use fails this check (that is the point).
EXEMPT_FILES: dict[str, str] = {
    "build/toolchain/provenance.py":
        "P2 toolchain digest verification (urlopen over PINNED https URLs; "
        "pre-chokepoint). TODO(P4): migrate through fetch.py.",
    "build/sync.py":
        "P2 checkout tool: git-clone subprocess only (chromium + xr-core + "
        "depot_tools URLs feed `git clone`, not an HTTP client).",
    # P4 identity-seam spike kit (0c32c09, ADR-0042). These use a LOCAL CDP
    # loopback socket + example/scan-token URL data; NONE of them reaches the
    # external network, so the chokepoint (external network only) does not
    # apply. The raw `import socket` / URL-literal heuristic would otherwise
    # false-positive on the loopback client.
    "build/spike/cdp.py":
        "P4 identity-seam spike: local CDP WebSocket client — connect() REFUSES "
        "any host other than 127.0.0.1/localhost/::1, so it never reaches the "
        "external network (raw loopback socket, not an HTTP client).",
    "build/spike/probe_driver.py":
        "P4 identity-seam spike driver: the www/URL literals are scan TOKENS "
        "matched against probe output (data), never fetched; network use is "
        "cdp.py's local-only socket + a loopback fixture server.",
    "build/spike/tests/cdp_fixture.py":
        "P4 spike test fixture: a stdlib loopback socket SERVER (127.0.0.1) "
        "emulating CDP for tests; never the external network.",
    # P11-T1 rows (research-log-P11.md R7 records both, per this dict's law):
    "build/qa/leaktest/engine.py":
        "P9-T3 leaktest harness: a userspace TCP tap bound to 127.0.0.1 ONLY "
        "(docs/qa/leaktest.md; 'No network beyond 127.0.0.1 — zero new "
        "egress'). It OBSERVES probe egress and never itself reaches the "
        "external network — same class as build/spike/cdp.py above.",
    "build/signing/platform_argv.py":
        "P10 signing argv builder: the timestamp.digicert.com literal is "
        "ARGV DATA handed to the platform signer (signtool/codesign) at the "
        "HG-36/37 human ceremony; this Python never opens a socket or "
        "fetches it — same class as the probe_driver scan tokens.",
    # P11-T4 row (T2-era debt surfaced by the first full run_checks after
    # the targeted T2/T3 batteries; research-log-P11.md D6 records it):
    "tools/shield_vectors_kit.py":
        "P11-T2 golden-vector fixture kit: the MATCH_URLS literals are "
        "RFC 2606 reserved-namespace scan tokens (.example plus the "
        "port/bare-host/example.com boundary variants the match vectors "
        "must exercise) fed to the match-decision fixtures — DATA, never "
        "fetched; the file imports no HTTP client and opens no socket "
        "(same class as the probe_driver scan tokens above).",
}
# URL literals that are test/fixture DATA (never fetched): example namespaces
# RFC-2606 reserved domains never route — test DATA, not network use.
# The trailing class allows a port (".example:8443/"): a reserved domain
# with a port is exactly as unfetchable as without one (P11-T5 false
# positive on the shield vector families; research-log-P11.md D7 item 8).
EXAMPLE_URL = re.compile(r"\.(example|invalid|test)[:/]")
NET_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(urllib\.request|http\.client|socket|requests|httpx|aiohttp)\b",
    re.MULTILINE,
)
SOCKET_CALLS = re.compile(
    r"\b(socket\.socket|urlopen|urllib\.request\.urlopen|"
    r"requests\.(get|post|put)|httpx\.(get|post|Client)|"
    r"subprocess\.\w+\(\[[\"'](?:curl|wget|nc|telnet)[\"'])")
URL_IN_CODE = re.compile(r"[\"'](https?://[^\"']{4,})[\"']")


def python_files(root: Path) -> list[Path]:
    skip = {".git", "work", "node_modules", "__pycache__"}
    out = []
    for p in root.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def strip_comments_docstrings(text: str) -> str:
    """Crude but effective: drop triple-quoted blocks and # comments."""
    text = re.sub(r'"""[\s\S]*?"""', '""', text)
    text = re.sub(r"'''[\s\S]*?'''", "''", text)
    text = re.sub(r"#[^\n]*", "", text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="enforce the fetch.py network chokepoint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    violations: list[dict[str, str]] = []
    self_rel = Path(__file__).resolve().relative_to(root).as_posix()
    for f in python_files(root):
        rel = f.relative_to(root).as_posix()
        if rel == self_rel:
            continue
        is_chokepoint = rel == CHOKEPOINT
        is_exempt = rel in EXEMPT_FILES
        raw = f.read_text(encoding="utf-8", errors="replace")
        code = strip_comments_docstrings(raw)
        if not is_chokepoint and not is_exempt:
            m = NET_IMPORTS.search(code)
            if m:
                violations.append({"file": rel, "line": m.group(0).strip(),
                                   "why": "network import outside the chokepoint"})
            m = SOCKET_CALLS.search(code)
            if m:
                violations.append({"file": rel, "line": m.group(0).strip(),
                                   "why": "socket/HTTP call outside the chokepoint"})
        # URLs in live code: allowed only in the chokepoint and in
        # dependency-evaluation/doc tooling that never fetches them
        in_tests = "/tests/" in rel or rel.startswith("tools/tests/")
        if not is_chokepoint and not is_exempt and not DOC_DATA_EXEMPT.search(rel):
            for m in URL_IN_CODE.finditer(code):
                url = m.group(1)
                if EXAMPLE_URL.search(url):
                    continue  # test/fixture namespace, never fetched
                if in_tests:
                    # URL literals in tests are FIXTURE DATA (e.g. the
                    # endpoint-deny list asserts update.googleapis.com is
                    # DENIED — it is never fetched). Network imports and
                    # socket calls in tests still fail above.
                    continue
                violations.append({"file": rel, "line": url,
                                   "why": "URL literal in code outside the chokepoint "
                                          "(route through fetch.py)"})

    # the chokepoint itself must only talk to the allowlist
    fetch_code = (root / CHOKEPOINT).read_text(encoding="utf-8")
    # sync.py's three pinned clone URLs are its documented exception
    for host in re.findall(r"[\"']([a-z0-9.-]+\.[a-z]{2,})[\"']", fetch_code):
        if host not in {"chromium.googlesource.com", "commondatastorage.googleapis.com",
                        "chromiumdash.appspot.com", "api.github.com",
                        "static.crates.io"} and \
                not host.endswith(".chromium.googlesource.com"):
            violations.append({"file": CHOKEPOINT, "line": host,
                               "why": "host outside the committed allowlist"})

    if args.json:
        print(json.dumps({"violations": violations}, indent=2))
    else:
        for v in violations:
            print(f"FAIL: {v['file']}: {v['why']}: {v['line']}")
        print(f"{'PASS' if not violations else 'FAIL'}: fetch_allowlist_check "
              f"({len(python_files(root))} files scanned; chokepoint {CHOKEPOINT})")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
