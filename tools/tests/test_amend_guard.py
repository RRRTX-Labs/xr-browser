"""amend_guard.py: contract-amendment RFC trailer gate (T10). Builds a temp
git repo to prove: pre-stamp warn-only; post-stamp missing-trailer fails; draft
RFC fails; approved RFC passes."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def run(repo: Path, rng: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "amend_guard.py"), "--repo", str(repo), "--range", rng],
        capture_output=True, text=True)


def _init(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "a@b.c")
    git(repo, "config", "user.name", "t")
    (repo / "docs" / "contracts").mkdir(parents=True)
    (repo / "docs" / "rfcs").mkdir(parents=True)
    (repo / "xr-core" / "mojom").mkdir(parents=True)
    (repo / "README.md").write_text("seed\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "seed")
    return repo


def test_pre_stamp_warn_only(tmp_path):
    repo = _init(tmp_path)
    (repo / "xr-core/mojom/x.mojom").write_text("interface X {};\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "touch mojom pre-stamp")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 0
    assert "warn-only" in r.stdout.lower()


def test_post_stamp_missing_trailer_fails(tmp_path):
    repo = _init(tmp_path)
    (repo / "docs/contracts/FROZEN.yaml").write_text("contracts: []\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp")
    (repo / "xr-core/mojom/x.mojom").write_text("interface X {};\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "touch no trailer")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 1
    assert "without" in r.stdout


def test_post_stamp_draft_rfc_fails(tmp_path):
    repo = _init(tmp_path)
    (repo / "docs/contracts/FROZEN.yaml").write_text("contracts: []\n")
    (repo / "docs/rfcs/RFC-7.md").write_text("# RFC-7\nstatus: DRAFT\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp+draft")
    (repo / "xr-core/mojom/x.mojom").write_text("interface Y {};\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "amend", "-m", "Contract-Amendment: RFC-7")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 1
    assert "RFC-7" in r.stdout


def test_post_stamp_approved_rfc_passes(tmp_path):
    repo = _init(tmp_path)
    (repo / "docs/contracts/FROZEN.yaml").write_text("contracts: []\n")
    (repo / "docs/rfcs/RFC-7.md").write_text("# RFC-7\nstatus: APPROVED\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp+approved")
    (repo / "xr-core/mojom/x.mojom").write_text("interface Z {};\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "amend", "-m", "Contract-Amendment: RFC-7")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 0


def test_post_stamp_unlisted_new_contract_warns_only(tmp_path):
    """P6 law: a NEW (unlisted) contract file under docs/contracts/ is
    post-freeze drafting — warn-only. The freeze unit is per-contract;
    the directory is not sealed against new contracts being born."""
    repo = _init(tmp_path)
    (repo / "docs/contracts/review").mkdir(parents=True)
    (repo / "docs/contracts/FROZEN.yaml").write_text(
        "contracts:\n  - id: one\n    packet: review/01-one.md\n    status: REVIEW-COMPLETE\n    ratified: PENDING\n")
    (repo / "docs/contracts/review/01-one.md").write_text("# one\n")
    (repo / "docs/contracts/one-v1.md").write_text("# contract one\n")
    (repo / "docs/contracts/INDEX.md").write_text(
        "| one | schema | `one-v1.md` | - | fake | vectors | `review/01-one.md` | REVIEW-COMPLETE |\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp")
    (repo / "docs/contracts/newborn-v1.md").write_text("# new contract\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "birth a new contract")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 0
    assert "drafts unlisted" in r.stdout


def test_post_stamp_listed_file_still_fails_without_rfc(tmp_path):
    """The per-file scoping must NOT weaken frozen protection: touching a
    FROZEN.yaml/INDEX-listed contract file post-stamp still fails."""
    repo = _init(tmp_path)
    (repo / "docs/contracts/review").mkdir(parents=True)
    (repo / "docs/contracts/one-v1.md").write_text("# contract one\n")
    (repo / "docs/contracts/review/01-one.md").write_text("# one\n")
    (repo / "docs/contracts/FROZEN.yaml").write_text(
        "contracts:\n  - id: one\n    packet: review/01-one.md\n    status: REVIEW-COMPLETE\n    ratified: PENDING\n")
    (repo / "docs/contracts/INDEX.md").write_text(
        "| one | schema | `one-v1.md` | - | fake | vectors | `review/01-one.md` | REVIEW-COMPLETE |\n")
    (repo / "docs/contracts/one-v1.md").write_text("# contract one\n")
    (repo / "docs/contracts/review/01-one.md").write_text("# one\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp")
    (repo / "docs/contracts/one-v1.md").write_text("# contract one AMENDED\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "amend a frozen contract")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 1
    assert "without" in r.stdout


def test_post_stamp_index_and_frozen_register_fails_without_rfc(tmp_path):
    """Editing the freeze registers (INDEX.md / FROZEN.yaml) post-stamp is
    an amendment of the freeze record and fails without an approved RFC."""
    repo = _init(tmp_path)
    (repo / "docs/contracts/FROZEN.yaml").write_text("contracts: []\n")
    (repo / "docs/contracts/INDEX.md").write_text("# index\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp")
    (repo / "docs/contracts/INDEX.md").write_text("# index edited\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "edit the register")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 1
    assert "without" in r.stdout


def test_stamp_commit_cannot_smuggle_amendment(tmp_path):
    """Tightened exemption: a commit that re-stamps FROZEN.yaml is exempt
    ONLY if it touches no frozen-listed file and no mojom file."""
    repo = _init(tmp_path)
    (repo / "docs/contracts/review").mkdir(parents=True)
    (repo / "docs/contracts/one-v1.md").write_text("# contract one\n")
    (repo / "docs/contracts/review/01-one.md").write_text("# one\n")
    (repo / "docs/contracts/FROZEN.yaml").write_text(
        "contracts:\n  - id: one\n    packet: review/01-one.md\n    status: REVIEW-COMPLETE\n    ratified: PENDING\n")
    (repo / "docs/contracts/INDEX.md").write_text(
        "| one | schema | `one-v1.md` | - | fake | vectors | `review/01-one.md` | REVIEW-COMPLETE |\n")
    (repo / "docs/contracts/one-v1.md").write_text("# contract one\n")
    (repo / "docs/contracts/review/01-one.md").write_text("# one\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp")
    # re-stamp AND amend a frozen contract in one commit => must FAIL
    (repo / "docs/contracts/FROZEN.yaml").write_text(
        "contracts:\n  - id: one\n    packet: review/01-one.md\n    status: REVIEW-COMPLETE\n    ratified: PENDING\nschema_version: 2\n")
    (repo / "docs/contracts/one-v1.md").write_text("# contract one AMENDED\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "stamp + smuggle")
    r = run(repo, "HEAD~1..HEAD")
    assert r.returncode == 1
    assert "without" in r.stdout
