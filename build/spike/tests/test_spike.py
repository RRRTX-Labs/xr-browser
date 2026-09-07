"""Unit tests for the P4 spike toolkit (stdlib, offline except where marked).

Covers the claims the phase makes about its own tooling:
  * genpatch never-list policy + transform determinism
  * fsdiff detects change at hash level (the zero-residual claim rests on it)
  * the stdlib WebSocket/CDP client speaks RFC 6455 against a loopback fixture
  * the probe driver refuses isolation-bypass flags (L2 applied to the spike)
  * census-lint and citation-audit reject bad input for the right reason
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import census_lint  # noqa: E402
import cdp  # noqa: E402
import fsdiff  # noqa: E402
import probe_driver  # noqa: E402
import seam_spec  # noqa: E402
from tests.cdp_fixture import serve_echo  # noqa: E402


def _fake_fetch_module(text: str):
    """A stand-in for build/upstream/fetch.py (no network in unit tests)."""
    import types

    class FetchError(Exception):
        pass

    class GitilesFetchSource:
        def __init__(self, *a, **k):
            pass

        def file_text(self, rev, path):
            return text

    mod = types.ModuleType("fetch")
    mod.FetchError = FetchError
    mod.GitilesFetchSource = GitilesFetchSource
    return mod


# ---------------------------------------------------------------- seam_spec / never-list

def test_never_list_refuses_content_and_third_party():
    refusals = seam_spec.check_paths(
        ["content/browser/site_instance_impl.cc", "third_party/blink/foo.cc",
         "v8/src/x.cc"])
    assert len(refusals) == 3
    assert "never-list" in refusals[0]


def test_never_list_allows_chrome_browser():
    assert seam_spec.check_paths(
        ["chrome/browser/ui/navigator/browser_navigator.cc"]) == []


def test_never_list_refuses_outside_embedder_layer():
    assert seam_spec.check_paths(["chrome/common/x.cc"])


def test_spec_targets_are_all_allowed():
    paths = [t["path"] for t in seam_spec.targets()]
    assert seam_spec.check_paths(paths) == []


def test_payloads_fail_closed_when_xr_core_missing(tmp_path):
    with pytest.raises(seam_spec.SpecError) as exc:
        seam_spec.payloads(tmp_path)
    assert "spike payload(s) missing" in str(exc.value)


# ---------------------------------------------------------------- fsdiff

def test_fsdiff_detects_added_removed_changed(tmp_path):
    root = tmp_path / "profile"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "keep.bin").write_bytes(b"same")
    (root / "sub" / "gone.bin").write_bytes(b"bye")
    before = fsdiff.snapshot(root)
    (root / "sub" / "gone.bin").unlink()
    (root / "sub" / "new.bin").write_bytes(b"hi")
    (root / "sub" / "keep.bin").write_bytes(b"same")          # identical bytes
    after = fsdiff.snapshot(root)
    d = fsdiff.diff(before, after)
    assert d["added"] == ["sub/new.bin"]
    assert d["removed"] == ["sub/gone.bin"]
    assert d["changed"] == []
    assert not fsdiff.is_empty(d)


def test_fsdiff_detects_single_byte_change(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"identity-a")
    before = fsdiff.snapshot(tmp_path)
    f.write_bytes(b"identity-b")
    d = fsdiff.diff(before, fsdiff.snapshot(tmp_path))
    assert d["changed"] == ["x.bin"], "a one-byte change must be detected"


def test_fsdiff_empty_tree_is_empty_snapshot(tmp_path):
    assert fsdiff.snapshot(tmp_path) == {}
    assert fsdiff.is_empty(fsdiff.diff({}, {}))


def test_fsdiff_records_symlinks_without_following(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "link").symlink_to(tmp_path / "a.txt")
    snap = fsdiff.snapshot(tmp_path)
    assert "link" in snap and "link" in snap["link"]


# ---------------------------------------------------------------- cdp client

@pytest.fixture()
def echo_server():
    server, port = serve_echo()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()


def test_cdp_handshake_and_roundtrip(echo_server):
    ws = cdp.WebSocket.connect("127.0.0.1", echo_server, "/devtools/page/1")
    try:
        client = cdp.Cdp(ws)
        result = client.call("SystemInfo.getInfo", {})
        assert result["echo"] == "SystemInfo.getInfo"
    finally:
        ws.close()


def test_cdp_accept_key_matches_rfc6455_example_vector():
    # RFC 6455 §1.3 example: key "dGhlIHNhbXBsZSBub25jZQ=="
    assert cdp._accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_cdp_client_frames_are_masked(echo_server):
    """A server must see the client's frames masked (RFC 6455 §5.3)."""
    seen = {}

    import socketserver
    from tests.cdp_fixture import (
        _Handler, _read_frame, _write_frame, _accept)

    class Spy(_Handler):
        def handle(self):
            buf = b""
            while b"\r\n\r\n" not in buf:
                buf += self.request.recv(4096)
            head, _, rest = buf.partition(b"\r\n\r\n")
            key = [l.split(":", 1)[1].strip() for l in
                   head.decode(errors="replace").split("\r\n")
                   if l.lower().startswith("sec-websocket-key:")][0]
            self.request.sendall(
                ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                 "Connection: Upgrade\r\n"
                 f"Sec-WebSocket-Accept: {_accept(key)}\r\n\r\n").encode())
            frame, _ = _read_frame(self.request, rest)
            seen["opcode"] = frame[0]
            seen["payload"] = frame[1]
            _write_frame(self.request, 0x1,
                         b'{"id": 1, "result": {"echo": "ok"}}')

    class Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = Srv(("127.0.0.1", 0), Spy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ws = cdp.WebSocket.connect("127.0.0.1", srv.server_address[1], "/")
        ws.send_text("hello-x-frame")
        cdp.WebSocket.recv_text(ws)
        ws.close()
    finally:
        srv.shutdown()
        srv.server_close()
    assert seen["opcode"] == 0x1, "text frame expected"
    assert seen["payload"] == b"hello-x-frame", "server must decode the mask"


def test_cdp_refuses_non_loopback():
    with pytest.raises(cdp.CdpError) as exc:
        cdp.WebSocket.connect("8.8.8.8", 80, "/")
    assert "non-loopback" in str(exc.value)


# ---------------------------------------------------------------- probe driver policy

@pytest.mark.parametrize("flag", [
    "--disable-site-isolation-trials",
    "--single-process",
    "--process-per-site",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-features=SomeSiteIsolationThing",
])
def test_driver_refuses_isolation_bypass(flag):
    with pytest.raises(Exception) as exc:
        probe_driver.refuse_isolation_bypass([flag])
    assert "isolation-bypass" in str(exc.value)


def test_driver_accepts_clean_flags():
    probe_driver.refuse_isolation_bypass(
        ["--enable-logging=stderr", "--v=0", "--no-sandbox"])


def test_driver_offline_lanes_all_pass():
    rows = probe_driver.run_offline("0" * 40)
    assert rows, "the offline lane must actually run something"
    failed = [r for r in rows if r["verdict"] == "FAIL"]
    assert not failed, f"offline lanes failed: {failed}"
    for r in rows:
        assert r["source"] in {"static", "fixture"}, r
        assert r["verdict"] != "PENDING-FARM" or r["source"] != "runtime"


def test_driver_farm_lane_refuses_to_simulate(tmp_path):
    with pytest.raises(Exception) as exc:
        probe_driver.run_farm("0" * 40, str(tmp_path / "nope"), tmp_path)
    assert "BLOCKED" in str(exc.value)


# ---------------------------------------------------------------- census lint

def _census_row(rid, surface="downloads", owner="B", sev="S1", phase="P14",
                est="3 files x ui"):
    return (f"| {rid} | {surface} | breaks | repro | {sev} | {owner} | {est} "
            f"| {phase} | yes |")


def _write_census(tmp_path, rows):
    header = "| " + " | ".join(census_lint.COLUMNS) + " |\n"
    sep = "|" + "---|" * len(census_lint.COLUMNS) + "\n"
    p = tmp_path / "census.md"
    p.write_text(header + sep + "\n".join(rows) + "\n")
    return p


def test_census_lint_rejects_missing_named_surfaces(tmp_path):
    p = _write_census(tmp_path, [_census_row("C-01")])
    _, failures = census_lint.lint(p)
    assert any("named surface missing" in f for f in failures)
    assert any("favicon" in f for f in failures)


def test_census_lint_rejects_bad_owner(tmp_path):
    rows = [_census_row(f"C-{i:02d}", surface=s) for i, s in enumerate(
        ["download", "print", "devtools", "omnibox", "drag-and-drop",
         "find-in-page", "pip", "notification", "chrome://", "autofill",
         "tab search", "favicon", "desktop drag"])]
    rows[0] = _census_row("C-01", owner="Z")
    p = _write_census(tmp_path, rows)
    _, failures = census_lint.lint(p)
    assert any("owner 'Z' not in" in f for f in failures)


def test_census_lint_rejects_bad_budget_category(tmp_path):
    rows = [_census_row(f"C-{i:02d}", surface=s) for i, s in enumerate(
        ["download", "print", "devtools", "omnibox", "drag-and-drop",
         "find-in-page", "pip", "notification", "chrome://", "autofill",
         "tab search", "favicon", "desktop drag"])]
    rows[0] = _census_row("C-01", est="3 files x made_up_category")
    p = _write_census(tmp_path, rows)
    _, failures = census_lint.lint(p)
    assert any("budget category" in f for f in failures)


def test_census_lint_rejects_placeholder(tmp_path):
    rows = [_census_row(f"C-{i:02d}", surface=s) for i, s in enumerate(
        ["download", "print", "devtools", "omnibox", "drag-and-drop",
         "find-in-page", "pip", "notification", "chrome://", "autofill",
         "tab search", "favicon", "desktop drag"])]
    rows[0] = _census_row("C-01", est="TBD")
    p = _write_census(tmp_path, rows)
    _, failures = census_lint.lint(p)
    assert any("placeholder" in f for f in failures)


def test_census_lint_accepts_the_shipped_census():
    doc = Path("docs/spike-identity/papercut-census.md")
    if not doc.is_file():
        pytest.skip("shipped census not present")
    rows, failures = census_lint.lint(doc)
    assert not failures, failures
    assert len(rows) >= 12


# ---------------------------------------------------------------- citation audit

def test_citation_audit_parses_the_measured_table():
    doc = Path("docs/spike-identity/measured-shared-state.md")
    if not doc.is_file():
        pytest.skip("measured table not present")
    rows = __import__("citation_audit").parse_rows(doc)
    assert len(rows) >= 20, f"only {len(rows)} citation rows parsed"
    for r in rows:
        assert r["file"] and r["line"] > 0 and r["quote"]



def test_citation_audit_log_is_reproducible():
    """A committed evidence artifact must not embed a wall clock.

    The audit log lives in evidence/P4/logs/, so if it carried a timestamp
    every gate run would dirty the tree and no two runs would be diffable.
    """
    import re
    repo = Path(__file__).resolve().parent.parent.parent.parent
    src = (repo / "build" / "spike" / "citation_audit.py").read_text(encoding="utf-8")
    assert "XR_CITATION_STAMP" in src, "the wall clock must be opt-in, not default"
    log = repo / "evidence" / "P4" / "logs" / "citation-audit.txt"
    if log.exists():
        text = log.read_text(encoding="utf-8")
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text), \
            "evidence artifact embeds a run timestamp"

def test_citation_audit_rejects_a_fabricated_quote(tmp_path, monkeypatch):
    import citation_audit
    doc = tmp_path / "cites.md"
    doc.write_text(
        "| id | state | claimed | measured | meaning | `content/public/browser/"
        "storage_partition_config.h:44` | `this text is not in the file` | "
        "PENDING-FARM |\n")
    rows = citation_audit.parse_rows(doc)
    assert len(rows) == 1

    monkeypatch.setitem(sys.modules, "fetch",
                        _fake_fetch_module(
                            "static StoragePartitionConfig Create("
                            "BrowserContext* browser_context,\n"))
    results, failures = citation_audit.audit(rows, "0" * 40)
    assert failures and "quote not found" in failures[0]


def test_citation_audit_rejects_a_runtime_claim(tmp_path, monkeypatch):
    import citation_audit
    doc = tmp_path / "cites.md"
    quote = "static StoragePartitionConfig Create(BrowserContext* browser_context,"
    doc.write_text(
        "| id | state | claimed | measured | meaning | "
        "`content/public/browser/storage_partition_config.h:1` | "
        f"`{quote}` | VERIFIED |\n")   # line 1 so drift passes; the runtime
                                       # claim is what must be rejected
    rows = citation_audit.parse_rows(doc)

    monkeypatch.setitem(sys.modules, "fetch", _fake_fetch_module(quote + "\n"))
    results, failures = citation_audit.audit(rows, "0" * 40)
    assert any("PENDING-FARM" in f for f in failures)
