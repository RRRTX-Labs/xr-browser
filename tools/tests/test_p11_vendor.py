#!/usr/bin/env python3
"""tools/tests/test_p11_vendor.py — P11-T1 canaries: the allowlist ceremony,
the crate-graph resolver, the license/advisory verdicts, and vendor_check's
tamper sight. Offline except the real-tree check (which is offline too — it
only hashes files)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "build" / "upstream"))
sys.path.insert(0, str(REPO / "tools"))
import fetch  # noqa: E402
import vendor_check as vc  # noqa: E402
import vendor_rust_graph as vg  # noqa: E402

XR_CORE = REPO.parent / "xr-core"
VENDOR_ROOT = XR_CORE / "third_party" / "rust"


# ---------------------------------------------------------------------------
# the ADR-0044 allowlist ceremony: the CDN joins, the index/API hosts do not
# ---------------------------------------------------------------------------
def test_ceremony_cdn_host_allowed():
    fetch.assert_url_allowed(
        "https://static.crates.io/crates/adblock/adblock-0.13.3.crate")


@pytest.mark.parametrize("url", [
    "https://index.crates.io/ad/bl/adblock",     # the sparse INDEX: mutable
    "https://crates.io/api/v1/crates/adblock",   # the API: mutable
    "https://raw.githubusercontent.com/x/y/z",   # never sanctioned
])
def test_ceremony_index_and_api_hosts_refused(url):
    with pytest.raises(fetch.FetchError):
        fetch.assert_url_allowed(url)


def test_github_api_url_builds_inside_the_chokepoint():
    u = fetch.github_api_url("repos/RRRTX-Labs/xr-browser")
    assert u == "https://api.github.com/repos/RRRTX-Labs/xr-browser"
    # the invariant: whatever path a caller passes, the built URL can never
    # leave api.github.com (the host is pinned by construction + asserted)
    for weird in ("@evil.example/x", "https://evil.example", "../../etc"):
        fetch.assert_url_allowed(fetch.github_api_url(weird))


# ---------------------------------------------------------------------------
# license verdicts: a disjunction is a CHOICE, recorded; a shrug is a red
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("expr,ok,chosen", [
    ("MIT", True, "MIT"),
    ("MIT/Apache-2.0", True, "MIT"),                      # legacy spelling
    ("MIT OR Apache-2.0", True, "MIT"),
    ("Apache-2.0 OR MIT", True, "Apache-2.0"),
    ("MIT OR Apache-2.0 OR LGPL-2.1-or-later", True, "MIT"),
    ("(MIT OR Apache-2.0) AND Unicode-3.0", True,
     "(MIT OR Apache-2.0) AND Unicode-3.0"),
    ("Apache-2.0 WITH LLVM-exception", True, "Apache-2.0"),
    ("GPL-3.0-only", False, None),
    ("GPL-2.0 OR AGPL-3.0", False, None),
    ("MIT WITH SomeUnknownException", False, None),
    ("MIT AND GPL-2.0", False, None),   # AND: one bad part poisons it
    (None, False, None),
])
def test_license_verdict(expr, ok, chosen):
    assert vg.license_verdict(expr) == (ok, chosen)


@pytest.mark.parametrize("version,rng,verdict", [
    ("1.5.0", ">= 1.0, < 2.0", "hit"),
    ("2.0.0", ">= 1.0, < 2.0", "miss"),
    ("0.22.1", "< 0.5.2", "miss"),
    ("1.15.1", ">= 1.0.0, < 1.6.1", "miss"),
    ("1.5.0", "1.0 - 2.0", "NEEDS-REVIEW"),   # unparseable: never a silent miss
    ("1.5.0", None, "NEEDS-REVIEW"),
])
def test_range_hit(version, rng, verdict):
    assert vg.range_hit(version, rng) == verdict


def test_semver_bare_req_is_caret():
    assert vg.semver_satisfies("1.0.69", "1.0")
    assert not vg.semver_satisfies("2.0.18", "1.0")   # the pin bug this caught
    assert vg.semver_satisfies("0.14.0", "0.14")
    assert not vg.semver_satisfies("0.13.0", "0.14")


# ---------------------------------------------------------------------------
# closure semantics: dev twins, off-features, default-features=false
# ---------------------------------------------------------------------------
def _mini_lock():
    return vg.parse_lock('''
version = 4
[[package]]
name = "root"
version = "1.0.0"
dependencies = ["plain 1.0.0", "optdep 1.0.0", "benchy 0.3.0"]
[[package]]
name = "plain"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "aa"
[[package]]
name = "optdep"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bb"
[[package]]
name = "benchy"
version = "0.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "cc"
''')


ROOT_MAN = {
    "package": {"name": "root", "version": "1.0.0"},
    "features": {"default": ["on"], "on": ["dep:optdep"],
                 "extra": ["dep:benchy"]},
    "dependencies": {
        "plain": {"version": "1.0"},
        "optdep": {"version": "1.0", "optional": True},
        "benchy": {"version": "0.3", "optional": True},
    },
    "dev-dependencies": {"benchy": {"version": "0.3"}},
}
LEAF = {"package": {"name": "leaf", "version": "1.0.0"}, "dependencies": {}}


def test_closure_feature_aware():
    mans = {("plain", "1.0.0"): LEAF, ("optdep", "1.0.0"): LEAF,
            ("benchy", "0.3.0"): LEAF}
    closure, _ = vg.build_closure(_mini_lock(), ROOT_MAN, ("root", "1.0.0"),
                                  lambda nv: mans[nv])
    assert ("plain", "1.0.0") in closure
    assert ("optdep", "1.0.0") in closure        # default feature 'on'
    assert ("benchy", "0.3.0") not in closure    # off at the pin + dev twin
    closure2, _ = vg.build_closure(_mini_lock(), ROOT_MAN, ("root", "1.0.0"),
                                   lambda nv: mans[nv],
                                   root_features={"default", "extra"})
    assert ("benchy", "0.3.0") in closure2       # --features extra


def test_closure_optional_edge_with_incompatible_lock_version_skipped():
    # the phf_generator/criterion quirk: an optional bench dep whose lock
    # version does not satisfy the edge req is a feature that is OFF
    lock = _mini_lock()
    man = {"package": {"name": "root", "version": "1.0.0"},
           "features": {"default": []},
           "dependencies": {"benchy": {"version": "0.4", "optional": True}}}
    closure, _ = vg.build_closure(lock, man, ("root", "1.0.0"),
                                  lambda nv: LEAF)
    assert closure == set()


# ---------------------------------------------------------------------------
# vendor_check on a synthetic tree: pass, then every tamper class reddens
# ---------------------------------------------------------------------------
def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture()
def mini_tree(tmp_path):
    root = tmp_path / "rust"
    mini_sha = hashlib.sha256(b"mini-tarball").hexdigest()
    lock_text = (
        'version = 4\n\n[[package]]\nname = "adblock"\nversion = "0.13.3"\n'
        'dependencies = [\n "mini 1.0.0",\n]\n\n[[package]]\nname = "mini"\n'
        'version = "1.0.0"\nsource = "registry+https://github.com/rust-lang/'
        'crates.io-index"\nchecksum = "%s"\n' % mini_sha)
    lock_sha = hashlib.sha256(lock_text.encode()).hexdigest()
    pin = root / "adblock" / "0.13.3"
    _write(pin / "Cargo.toml", '[package]\nname = "adblock"\nversion = '
           '"0.13.3"\nlicense = "MPL-2.0"\n\n[dependencies]\nmini = "1.0"\n')
    _write(pin / "Cargo.lock", lock_text)
    _write(pin / "src" / "lib.rs", "// upstream bytes\n")
    _write(pin / "README.xr.md", "# xr\n")
    _write(pin / "UPDATING.md", "# updating\n")
    def seal(name, rels):
        lines = []
        for rel in sorted(rels):
            h = hashlib.sha256((pin / rel).read_bytes()).hexdigest()
            lines.append(f"{h}  {rel}\n")
        _write(pin / name, "".join(lines))
    seal("MANIFEST.sha256", ["Cargo.toml", "Cargo.lock", "src/lib.rs"])
    seal("MANIFEST.xr.sha256", ["README.xr.md", "UPDATING.md"])
    _write(root / "Cargo.lock", lock_text)
    _write(root / ".cargo" / "config.toml",
           '[source.crates-io]\nreplace-with = "xr-vendored-sources"\n\n'
           '[source.xr-vendored-sources]\ndirectory = "vendor"\n')
    vd = root / "vendor" / "mini-1.0.0"
    _write(vd / "Cargo.toml", '[package]\nname = "mini"\nversion = "1.0.0"\n'
           'license = "MIT"\n')
    _write(vd / "src" / "lib.rs", "// mini\n")
    files = {rel: hashlib.sha256((vd / rel).read_bytes()).hexdigest()
             for rel in ("Cargo.toml", "src/lib.rs")}
    _write(vd / ".cargo-checksum.json",
           json.dumps({"files": files, "package": mini_sha}))
    sc = root / "supply-chain"
    _write(sc / "PROVENANCE.md", "# provenance\n")
    _write(sc / "licenses.json", json.dumps(
        {"root": {"sha256_lock": lock_sha},
         "crates": {"mini 1.0.0": {"expression": "MIT", "chosen": "MIT"}}}))
    _write(sc / "advisories.json", json.dumps(
        {"match": {"hits": [], "needs_review": [], "name_matches": []}}))
    return root


def _check(root):
    return vc.run(Path(root), False)


def test_vendor_check_mini_tree_passes(mini_tree):
    assert _check(mini_tree) == 0


def test_vendor_check_tamper_reddens_naming_the_file(mini_tree):
    p = mini_tree / "vendor" / "mini-1.0.0" / "src" / "lib.rs"
    p.write_text(p.read_text() + "// tamper\n")
    assert _check(mini_tree) == 1


def test_vendor_check_root_tamper_reddens(mini_tree):
    p = mini_tree / "adblock" / "0.13.3" / "src" / "lib.rs"
    p.write_text(p.read_text() + "// tamper\n")
    assert _check(mini_tree) == 1


def test_vendor_check_unaccounted_file_reddens(mini_tree):
    _write(mini_tree / "adblock" / "0.13.3" / "backdoor.rs", "// evil\n")
    assert _check(mini_tree) == 1


def test_vendor_check_missing_file_reddens(mini_tree):
    (mini_tree / "vendor" / "mini-1.0.0" / "src" / "lib.rs").unlink()
    assert _check(mini_tree) == 1


def test_vendor_check_closure_gap_reddens(mini_tree):
    # a crate the build graph needs but vendor/ lost
    import shutil
    shutil.rmtree(mini_tree / "vendor" / "mini-1.0.0")
    assert _check(mini_tree) == 1


def test_vendor_check_advisory_hit_reddens(mini_tree):
    p = mini_tree / "supply-chain" / "advisories.json"
    p.write_text(json.dumps({"match": {
        "hits": [{"crate": "mini", "vendored_version": "1.0.0",
                  "ghsa_id": "GHSA-xxxx", "severity": "critical",
                  "vulnerable_version_range": "< 2.0"}],
        "needs_review": [], "name_matches": []}}))
    assert _check(mini_tree) == 1


def test_vendor_check_license_outside_allowed_reddens(mini_tree):
    p = mini_tree / "supply-chain" / "licenses.json"
    d = json.loads(p.read_text())
    d["crates"]["mini 1.0.0"] = {"expression": "GPL-3.0-only", "chosen": None}
    p.write_text(json.dumps(d))
    assert _check(mini_tree) == 1


def test_vendor_check_lock_desync_reddens(mini_tree):
    p = mini_tree / "Cargo.lock"
    p.write_text(p.read_text() + "\n# desync\n")
    assert _check(mini_tree) == 1


@pytest.mark.skipif(not VENDOR_ROOT.is_dir(),
                    reason="xr-core third_party/rust not checked out")
def test_vendor_check_real_tree():
    rc = subprocess.run([sys.executable, str(REPO / "tools" / "vendor_check.py"),
                         "--check"], capture_output=True, text=True, cwd=REPO)
    assert rc.returncode == 0, rc.stdout + rc.stderr
    assert "PASS: vendor_check" in rc.stdout
