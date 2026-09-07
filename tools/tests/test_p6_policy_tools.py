"""P6 policy tooling tests: mode_lint, cross-language parity matrix (fake ⇄
C++ policy_host ⇄ golden vectors — the phase's centerpiece gate), events
schema + absence laws, xrctl policy surface, mutation harness sanity.

Stdlib + pytest; runs on a clean clone (uses the real repo + ../xr-core).
C++-dependent tests SKIP VISIBLY when g++/policy_host are absent (skip-policy
law) — never a silent pass.
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
HOST = XR_CORE / "policy" / "tests" / "build" / "policy_host"
VECTORS = REPO / "docs" / "contracts" / "vectors" / "policy-resolver-v1.json"


def run(tool: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          cwd=cwd or REPO, capture_output=True, text=True)


def cpp_backend_available() -> bool:
    return HOST.is_file() and shutil.which("g++") is not None


# ---- mode_lint: baseline green, rogue fails with file:line, headers --------

def test_mode_lint_baseline_green_on_real_tree():
    r = run("mode_lint.py", "--root", str(XR_CORE))
    assert r.returncode == 0, r.stdout + r.stderr


def test_mode_lint_rogue_fixture_fails_citing_file_line(tmp_path):
    # A rogue mode check outside the exempted paths must fail the build.
    (tmp_path / "net").mkdir()
    (tmp_path / "net" / "rogue.cc").write_text(
        "// Copyright 2026 RRRTX Labs\n"
        "int ShouldBlock(const char* trust) {\n"
        "  return strcmp(trust, \"kShield\") == 0 ? 1 : 0;  // rogue mode check\n"
        "}\n", encoding="utf-8")
    r = run("mode_lint.py", "--root", str(tmp_path),
            "--config", str(XR_CORE / "policy" / "mode_lint.cfg"))
    assert r.returncode == 1
    assert "rogue.cc:3" in r.stdout, r.stdout  # file:line citation


def test_mode_lint_missing_intent_header_fails(tmp_path):
    # A policy/ file without the L13 '// Intent:' header must fail.
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy" / "no_header.cc").write_text(
        "// Copyright 2026 RRRTX Labs\nint f() { return 0; }\n", encoding="utf-8")
    r = run("mode_lint.py", "--root", str(tmp_path),
            "--config", str(XR_CORE / "policy" / "mode_lint.cfg"))
    assert r.returncode == 1
    assert "missing-intent-header" in r.stdout
    assert "no_header.cc" in r.stdout


def test_mode_lint_exemptions_are_scoped():
    cfg = (XR_CORE / "policy" / "mode_lint.cfg").read_text(encoding="utf-8")
    assert "exempt: /policy/" in cfg
    assert "exempt: /fakes/" in cfg
    assert "exempt: /mojom/" in cfg


# ---- THE PARITY MATRIX: vectors ⇄ fake ⇄ C++ on every vector ---------------

def test_parity_matrix_all_vectors_both_backends():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — needed for: the C++ "
                    "parity matrix; CI builds it with g++ present (P6 evidence "
                    "logs the full run).")
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    sys.path.insert(0, str(XR_CORE / "fakes"))
    import policy_resolver as fake  # noqa: PLC0415
    mismatches = []
    for v in data["vectors"]:
        want = json.dumps(v["expected"], sort_keys=True, separators=(",", ":"))
        got_fake = fake.canonical(fake.resolve(v["request"]))
        if got_fake != want:
            mismatches.append(f"{v['name']}: fake != vector")
            continue
        r = subprocess.run([str(HOST)], input=json.dumps(v["request"]),
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            mismatches.append(f"{v['name']}: cpp host rc={r.returncode}")
            continue
        got_cpp = r.stdout.strip()
        if got_cpp != want:
            mismatches.append(f"{v['name']}: cpp != vector\n  cpp: {got_cpp[:140]}\n"
                              f"  want:{want[:140]}")
    assert not mismatches, "\n".join(mismatches[:5])


def test_parity_matrix_swapped_identities_and_layers():
    """Beyond the frozen vectors: layer-bearing requests must agree too."""
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — parity matrix "
                    "extension for P6 layers.")
    sys.path.insert(0, str(XR_CORE / "fakes"))
    import policy_resolver as fake  # noqa: PLC0415
    probes = [
        {"identity": {"value": "xr:00000000-0000-4000-8000-0000000000ef"},
         "origin": {"scheme": "https", "registrable_domain": "x.io"},
         "request_class": "kScript", "trust_context": "kShield"},
        {"identity": {"value": "xr:00000000-0000-4000-8000-000000000002"},
         "origin": {"scheme": "http", "registrable_domain": "y.org"},
         "request_class": "kPermission"},
        {"identity": {"value": "xr:00000000-0000-4000-8000-000000000001"},
         "origin": {"scheme": "https", "registrable_domain": "a.com"},
         "request_class": "kNavigation", "contract_version": 999},
    ]
    for req in probes:
        want = fake.canonical(fake.resolve(req))
        r = subprocess.run([str(HOST)], input=json.dumps(req),
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0
        assert r.stdout.strip() == want


# ---- xrctl policy surface ---------------------------------------------------

def test_xrctl_policy_backends_agree():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — xrctl backend swap test.")
    req = json.dumps({"identity": {"value": "xr:00000000-0000-4000-8000-000000000001"},
                      "origin": {"scheme": "https", "registrable_domain": "example.com"},
                      "request_class": "kNavigation", "trust_context": "kFortress"})
    a = run("xrctl.py", "policy", "resolve", req)
    b = run("xrctl.py", "policy", "--backend", "cpp", "resolve", req)
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout.strip() == b.stdout.strip()


def test_xrctl_policy_snapshot_stats_within_budget():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — snapshot stats test.")
    r = run("xrctl.py", "policy", "snapshot-stats", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    stats = json.loads(r.stdout)
    assert stats["full_bytes"] <= stats["budget_bytes"]
    assert stats["diff_bytes"] <= stats["budget_bytes"]


def test_xrctl_policy_dump_json_and_human():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — dump parity test.")
    rj = run("xrctl.py", "policy", "--backend", "cpp", "dump", "--managed", "--json")
    rh = run("xrctl.py", "policy", "--backend", "cpp", "dump", "--managed")
    assert rj.returncode == 0 and rh.returncode == 0
    j = json.loads(rj.stdout)
    assert j["managed"]["status"] in ("kAbsent", "kVerified", "kIgnoredUnsigned",
                                      "kIgnoredBadSignature", "kIgnoredInvalid",
                                      "kIgnoredFutureVersion", "kSkippedNoTool")
    assert "cache" in j and "ledger" in j
    assert "managed: status=" in rh.stdout  # human output labeled


# ---- events schema + absence laws -------------------------------------------

def test_policy_change_event_schema_validates_golden():
    sys.path.insert(0, str(TOOLS))
    import xr_schema  # noqa: PLC0415
    golden = {
        "event": "policy_changed", "contract_version": 1,
        "identity": "xr:00000000-0000-4000-8000-000000000001",
        "site": "example.com", "previous_trust": "kStandard",
        "new_trust": "kFortress",
        "deltas": [{"path": "permissions.camera", "from": "kAsk", "to": "kDeny",
                    "change": "blocked", "human": "camera now blocked"}],
        "summary": "camera now blocked", "undo": True,
    }
    schema = json.loads((REPO / "docs" / "contracts" /
                         "policy-change-event-v1.schema.json").read_text(encoding="utf-8"))
    errs: list[str] = []
    xr_schema._validate(golden, schema, "$", errs)
    assert not errs, errs


def test_policy_change_event_absence_laws():
    text = (REPO / "docs" / "contracts" / "policy-change-event-v1.schema.json") \
        .read_text(encoding="utf-8")
    for banned in ("score", "risk", "grade", "auto_reload", "autoreload"):
        assert banned not in text.lower(), f"banned token in schema: {banned}"


# ---- vectors_to_md: regeneration is diff-clean ------------------------------

def test_policy_md_regeneration_clean():
    r = run("vectors_to_md.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


# ---- mutation harness sanity (tiny, seeded; full matrix = evidence/farm) ----

def test_mutation_harness_kills_injected_mutant():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — mutation harness test.")
    r = run("mutation_test.py", "--sample", "5", "--seed", "424242",
            "--timebox", "240", "--json")
    assert r.returncode in (0, 1), r.stdout + r.stderr
    report = json.loads(r.stdout)
    assert report["total_mutants"] == 5  # sampled exactly
    # The smoke invariant: no DENY-GUARD mutant survives (never-guess paths
    # are tested). The score gate itself is the CI lane's job (sampled) and
    # the evidence/farm full matrix.
    assert report["deny_guard_survivors"] == 0, r.stdout


def test_policy_fuzz_smoke_deterministic_and_deny_safe():
    if not cpp_backend_available():
        pytest.skip("SKIP (tool absent: g++/policy_host) — fuzz smoke test.")
    r = run("policy_fuzz.py", "--iterations", "150", "--timebox", "120",
            "--seed", "99", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    report = json.loads(r.stdout)
    assert report["crashes"] == 0
    assert report["violations"] == 0
