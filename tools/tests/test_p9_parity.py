"""P9-T0-a parity tests: corpus byte-parity, completeness gate, differential fuzz.

Three laws exercised here (the P9 anti-drift machinery's own tests):

1. the extended themes parity corpus (>=12 hostile/realistic import +
   validate-doc docs) runs BYTE-IDENTICAL between the C++ host and the fake
   — the T0-a canonicalization locked the refusal text, and this is the
   regression lock;
2. the parity-completeness gate turns RED when a method's cases are deleted
   from the corpus (auto-discovered from the host_protocol.md Methods table);
3. the differential oracle turns RED when the fake is mutated (canary) and
   GREEN on the real tree.

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
CORPUS = TOOLS / "parity" / "corpus-themes.json"
TOKENS = XR_CORE / "ui" / "themes" / "tokens.json"

sys.path.insert(0, str(TOOLS))
import differential_fuzz as df  # noqa: E402
from parity import _corpus as corpus  # noqa: E402

HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None

IMPORT_DOC_MIN = 12  # T0-a: >=12 realistic import/validate-doc docs


def _ensure_hosts() -> None:
    for d in ("themes", "settings", "commands"):
        make = ["make", "-C", str(XR_CORE / d / "tests"), "build"]
        r = subprocess.run(make, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"make failed for {d}:\n{r.stderr[-400:]}")


@pytest.fixture(scope="module")
def hosts() -> None:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — C++ parity skipped (skip-policy)")
    _ensure_hosts()


def _backend(pid: str, req: str) -> tuple[int, str]:
    cfg = df._pair_configs(XR_CORE, XR_CORE / "fakes")[pid]
    rc_h, out_h = df._run_backend(cfg["host"], req, XR_CORE, 30.0)
    rc_f, out_f = df._run_backend(cfg["fake"], req, XR_CORE, 30.0)
    assert rc_h == rc_f, (pid, req, rc_h, rc_f)
    return rc_h, out_h


def _code_of(out: str) -> str:
    try:
        return str(json.loads(out).get("error", ""))
    except json.JSONDecodeError:
        return out


def test_themes_corpus_covers_methods_and_hostile_families() -> None:
    doc = corpus.load_corpus(CORPUS, TOKENS)
    counts = corpus.methods_in_corpus(doc)
    md = XR_CORE / "themes" / "host_protocol.md"
    methods = corpus.protocol_methods(md)
    for m in methods:
        assert counts.get(m, 0) >= 1, f"method {m} has zero parity cases"
    import_docs = [c for c in doc["cases"]
                   if c["method"] in ("import", "validate-doc")]
    assert len(import_docs) >= IMPORT_DOC_MIN, (
        f"T0-a: corpus needs >= {IMPORT_DOC_MIN} import/validate-doc docs, "
        f"got {len(import_docs)}")


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent (skip-policy)")
def test_themes_corpus_byte_parity(hosts, tmp_path: Path) -> None:
    doc = corpus.load_corpus(CORPUS, TOKENS)
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    for case in doc["cases"]:
        req = corpus.case_to_request(case["id"], case, tokens)
        rc, out = _backend("themes", req)
        if case["expect"] == "ok":
            assert rc == 0, (case["id"], rc, out)
        else:
            assert rc == 1, (case["id"], rc, out)
            # byte-compare the refusal detail — the whole point of T0-a.
            # Parse-failure frames (compare:code) compare the error code only
            # (the two independent parsers' phrasing differs — P8-recorded).
            if case.get("compare") == "code":
                assert _code_of(out) == "kRejected", (case["id"], out)
                continue
            cfg = df._pair_configs(XR_CORE, XR_CORE / "fakes")["themes"]
            rc_c, out_c = df._run_backend(cfg["host"], req, XR_CORE, 30.0)
            rc_p, out_p = df._run_backend(cfg["fake"], req, XR_CORE, 30.0)
            assert out_c == out_p, (case["id"], out_c, out_p)


def test_completeness_gate_positive() -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "parity_completeness.py"),
                        "--repo", str(REPO)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_completeness_gate_negative(tmp_path: Path) -> None:
    # Deleting every import/validate-doc case must redden the gate (a method
    # whose cases are absent fails run_checks — the T0-a proof).
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    doc["cases"] = [c for c in doc["cases"]
                    if c["method"] not in ("import", "validate-doc")]
    broken = tmp_path / "corpus-broken.json"
    broken.write_text(json.dumps(doc))
    # manifest copy pointing at the broken corpus
    man = json.loads((TOOLS / "parity" / "manifest.json").read_text())
    for p in man["pairs"]:
        if p["id"] == "themes":
            p["corpus"] = "tools/parity/broken.json"
    shutil.copy(str(CORPUS), tmp_path / "x")
    # the gate resolves corpus paths relative to --repo; use a repo copy plus
    # a sibling xr-core holding only the protocol markdown the gate reads.
    repo2 = tmp_path / "repo"
    shutil.copytree(REPO, repo2, ignore=shutil.ignore_patterns(".git"))
    xr2 = tmp_path / "xr-core"
    for rel in ("themes/host_protocol.md", "settings/host_protocol.md",
                "commands/host_protocol.md"):
        (xr2 / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(XR_CORE / rel, xr2 / rel)
    (repo2 / "tools" / "parity" / "corpus-themes.json").write_text(
        json.dumps(doc))
    r = subprocess.run([sys.executable,
                        str(repo2 / "tools" / "parity_completeness.py"),
                        "--repo", str(repo2)],
                       capture_output=True, text=True)
    assert r.returncode == 1, "gate must go red when a method's cases vanish"
    assert "zero parity cases" in r.stdout or "ZERO" in r.stdout


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent (skip-policy)")
def test_differential_fuzz_smoke(hosts) -> None:
    r = subprocess.run([sys.executable, str(TOOLS / "differential_fuzz.py"),
                        "--repo", str(REPO), "--iters", "150",
                        "--seed", "20260910", "--min-iters", "1"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 divergences" in r.stdout


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent (skip-policy)")
def test_differential_fuzz_canary(hosts, tmp_path: Path) -> None:
    # Canary: a mutated fake (security-critical annotation stripped) MUST turn
    # the oracle red — the anti-drift machine proves it can see drift.
    fake_dir = tmp_path / "fakes"
    shutil.copytree(XR_CORE / "fakes", fake_dir)
    p = fake_dir / "themes.py"
    s = p.read_text(encoding="utf-8")
    s = s.replace('f["required"] >= 7.0', "False")
    p.write_text(s)
    r = subprocess.run([sys.executable, str(TOOLS / "differential_fuzz.py"),
                        "--repo", str(REPO), "--fake-dir", str(fake_dir),
                        "--pairs", "themes", "--iters", "150",
                        "--seed", "20260910", "--min-iters", "1"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 1, "mutated fake must turn the oracle red"
    assert "divergence" in (r.stdout + r.stderr).lower()


@pytest.mark.skipif(not HAVE_CPP, reason="g++/make absent (skip-policy)")
def test_differential_fuzz_min_iters_law(hosts) -> None:
    # Zero-case law: a run that executes nothing must FAIL, never pass.
    r = subprocess.run([sys.executable, str(TOOLS / "differential_fuzz.py"),
                        "--repo", str(REPO), "--iters", "3",
                        "--min-iters", "100", "--pairs", "themes"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 1
    assert "min-iters" in r.stdout
