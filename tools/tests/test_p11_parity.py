"""P11 parity tests: derived-pair gates + update-corpus byte parity.

Laws exercised here (P11-T0-a's own tests):

1. tools/host_protocol_check.py discovers EVERY method-dispatching host in
   xr-core/*/host/*.cc and fails when a host ships methods with no
   host_protocol.md, when source and table disagree in EITHER direction, or
   when the doc omits the response law (canonical line / sorted keys /
   \\uXXXX / exit 0-1-2 / kUnknownMethod);
2. tools/parity_completeness.py's pair list is DERIVED from that discovery:
   a synthetic fifth host with methods and no protocol doc reddens BOTH
   gates (the negative fixture tools/negatives/p11_t0.sh asserts the same
   from the shell side);
3. tools/parity/corpus-update.json (the update pair's completeness corpus)
   runs BYTE-IDENTICAL between the compiled update_host and fakes/update.py,
   with the exit-class law: ok = exit 0 typed result (deny verdicts and
   kRejected included), reject = exit 1 typed error.

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"

sys.path.insert(0, str(TOOLS))
import host_protocol_check as hpc  # noqa: E402
from parity import _corpus as corpus  # noqa: E402

HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None

UPDATE_CORPUS = TOOLS / "parity" / "corpus-update.json"


# ---------------------------------------------------------------------------
# 1. host_protocol_check on the real tree
# ---------------------------------------------------------------------------

def test_discovery_finds_every_real_host() -> None:
    hosts = hpc.discover_method_hosts(XR_CORE)
    # commands/settings/themes/update all dispatch `method == "..."`; policy
    # is the recorded subcommand-host exception and must NOT be discovered.
    assert set(hosts) >= {"commands", "settings", "themes", "update"}
    assert "policy" not in hosts


def test_host_protocol_check_green_on_real_tree() -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "host_protocol_check.py"),
                        "--xr-core", str(XR_CORE)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_synthetic_undocumented_host_reddens_both_gates(tmp_path: Path) -> None:
    # The T0-a negative, in-process: a fifth host with method literals and
    # no host_protocol.md must redden host_protocol_check AND the derived
    # parity_completeness (unaccounted host).
    core = tmp_path / "xr-core"
    (core / "widget" / "host").mkdir(parents=True)
    (core / "widget" / "host" / "widget_host.cc").write_text(
        'if (method == "spin") { return 0; }\n'
        'if (method == "stop") { return 1; }\n', encoding="utf-8")
    # a documented host so discovery is non-empty on its own merits
    for name in ("commands", "settings", "themes", "update"):
        src = XR_CORE / name
        if src.is_dir():
            shutil.copytree(src / "host", core / name / "host")
            shutil.copy(src / "host_protocol.md", core / name / "host_protocol.md")
    (core / "policy" / "host").mkdir(parents=True)
    shutil.copy(XR_CORE / "policy" / "host" / "policy_host.cc",
                core / "policy" / "host" / "policy_host.cc")

    r1 = subprocess.run([sys.executable, str(TOOLS / "host_protocol_check.py"),
                         "--xr-core", str(core)], capture_output=True, text=True)
    assert r1.returncode == 1, "undocumented host must redden host_protocol_check"
    assert "widget" in r1.stdout and "does not exist" in r1.stdout

    r2 = subprocess.run([sys.executable,
                         str(TOOLS / "parity_completeness.py"),
                         "--repo", str(REPO), "--xr-core", str(core)],
                        capture_output=True, text=True)
    assert r2.returncode == 1, "unaccounted host must redden parity_completeness"
    assert "widget" in r2.stdout and "unaccounted" in r2.stdout.lower()


def test_table_entry_without_code_is_also_a_failure(tmp_path: Path) -> None:
    # (ii) is bidirectional: a doc-only method is a lie.
    core = tmp_path / "xr-core"
    (core / "gadget" / "host").mkdir(parents=True)
    (core / "gadget" / "host" / "gadget_host.cc").write_text(
        'if (method == "real") { return 0; }\n', encoding="utf-8")
    (core / "gadget" / "host_protocol.md").write_text(
        "# gadget\n\nONE canonical JSON line (sorted keys, non-ASCII "
        "`\\uXXXX`), exit `0` = typed result, `1` = typed error, `2` = "
        "usage; kUnknownMethod refusal.\n\n## Methods\n\n"
        "| method | args | result |\n| --- | --- | --- |\n"
        "| `real` | `{}` | ok |\n| `ghost` | `{}` | no code |\n",
        encoding="utf-8")
    fails = hpc.check_host(core, "gadget", ["real"])
    assert any("ghost" in f for f in fails), fails


def test_response_law_markers_are_required(tmp_path: Path) -> None:
    core = tmp_path / "xr-core"
    (core / "thin" / "host").mkdir(parents=True)
    (core / "thin" / "host" / "thin_host.cc").write_text(
        'if (method == "go") { return 0; }\n', encoding="utf-8")
    (core / "thin" / "host_protocol.md").write_text(
        "# thin\n\n## Methods\n\n| method | args | result |\n"
        "| --- | --- | --- |\n| `go` | `{}` | ok |\n", encoding="utf-8")
    fails = hpc.check_host(core, "thin", ["go"])
    joined = " ".join(fails)
    for marker in ("canonical", "sorted keys", "uXXXX", "kUnknownMethod"):
        assert marker in joined, f"missing-law marker not reported: {marker}"


# ---------------------------------------------------------------------------
# 2. parity_completeness on the real tree (derived list == manifest)
# ---------------------------------------------------------------------------

def test_completeness_gate_positive_with_update_pair() -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "parity_completeness.py"),
                        "--repo", str(REPO)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "update: methods covered by parity corpus" in r.stdout
    assert "5 pair(s), 0 failure(s)" in r.stdout


def test_phantom_pair_fails(tmp_path: Path) -> None:
    # A manifest row naming a protocol for a host that dispatches nothing.
    manifest = tmp_path / "manifest.json"
    real = json.loads((TOOLS / "parity" / "manifest.json").read_text())
    real["pairs"].append({"id": "ghosthost",
                          "protocol": "../xr-core/ghosthost/host_protocol.md",
                          "corpus": "tools/parity/corpus-update.json"})
    manifest.write_text(json.dumps(real))
    r = subprocess.run([sys.executable, str(TOOLS / "parity_completeness.py"),
                        "--repo", str(REPO), "--manifest", str(manifest)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "phantom" in r.stdout


# ---------------------------------------------------------------------------
# 3. corpus-update.json byte parity (both backends, exit-class law)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def update_host() -> str:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — C++ parity skipped (skip-policy)")
    r = subprocess.run(["make", "-C", str(XR_CORE / "update" / "tests"),
                        "build"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
    return str(XR_CORE / "update" / "tests" / "build" / "update_host")


def _run(argv: list[str], req: str) -> tuple[int, str]:
    p = subprocess.run(argv, input=req, capture_output=True, text=True,
                       cwd=str(XR_CORE), timeout=30)
    return p.returncode, p.stdout


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent (skip-policy)")
def test_update_corpus_byte_parity(update_host) -> None:
    doc = corpus.load_corpus(UPDATE_CORPUS)
    fake = [sys.executable, str(XR_CORE / "fakes" / "update.py")]
    methods = corpus.protocol_methods(XR_CORE / "update" / "host_protocol.md")
    counts = corpus.methods_in_corpus(doc)
    assert all(m in counts for m in methods), "corpus must cover every method"
    executed = 0
    for case in doc["cases"]:
        req = corpus.case_to_request(case["id"], case, {})
        rc_h, out_h = _run([update_host], req)
        rc_f, out_f = _run(fake, req)
        assert rc_h == rc_f, (case["id"], rc_h, rc_f, out_h, out_f)
        assert out_h == out_f, (case["id"], out_h, out_f)
        want = 0 if case["expect"] == "ok" else 1
        assert rc_h == want, (case["id"], rc_h, out_h)
        executed += 1
    assert executed == len(doc["cases"]) > 0
