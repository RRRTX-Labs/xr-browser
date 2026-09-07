import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
APPLY = HERE.parent / "apply.py"


def _run(*args, cwd=None):
    return subprocess.run([sys.executable, str(APPLY), *args], cwd=cwd or HERE,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@pytest.fixture()
def fixture(tmp_path):
    """A minimal 'chromium' checkout: src git repo with chrome/VERSION + a file to patch."""
    src = tmp_path / "checkout" / "src"
    (src / "chrome" / "app" / "theme" / "chromium").mkdir(parents=True)
    (src / "chrome" / "VERSION").write_text("MAJOR=152\nMINOR=0\nBUILD=7977\nPATCH=82\n")
    (src / "chrome" / "app" / "theme" / "chromium" / "BRANDING").write_text("A=one\nB=two\n")
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                ["add", "-A"], ["commit", "-qm", "pin"]):
        subprocess.run(["git", "-C", str(src), *cmd], check=True, stdout=subprocess.DEVNULL)
    pin = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()

    mdir = tmp_path / "manifest"
    (mdir / "patches" / "branding" / "0001").mkdir(parents=True)
    (mdir / "patches" / "branding" / "0001" / "patchinfo.md").write_text(
        "- **id:** 0001\n- **title:** t\n- **owner:** @xr/platform\n- **category:** branding\n"
        "- **files:** chrome/app/theme/chromium/BRANDING\n- **upstream-bug-if-any:** none\n"
        "- **retirement plan:** n/a\n- **rebase-notes:** n/a\n")
    (mdir / "patches" / "branding" / "0001" / "0001.patch").write_text(
        "--- a/chrome/app/theme/chromium/BRANDING\n+++ b/chrome/app/theme/chromium/BRANDING\n"
        "@@ -1,2 +1,2 @@\n-A=one\n+A=XR\n B=two\n")
    (mdir / "patches" / "manifest.yaml").write_text(
        "schema_version: 1\ntotal_cap: 150\n"
        "categories:\n  branding: { cap: null }\n  hook_points: { cap: 45 }\n  blink_seams: { cap: 25 }\n"
        "  content_seams: { cap: 30 }\n  network_seams: { cap: 20 }\n  ui: { cap: 35 }\n"
        "  extension_chokepoint: { cap: 2 }\nallowed_roots: [\"chrome/app/\"]\n"
        "patches:\n  - id: \"0001\"\n    owner: \"@xr/platform\"\n    category: branding\n"
        "    files: [\"chrome/app/theme/chromium/BRANDING\"]\n    dir: branding/0001\n")
    return {"checkout": tmp_path / "checkout", "pin": pin, "manifest": mdir / "patches" / "manifest.yaml",
            "branding": src / "chrome" / "app" / "theme" / "chromium" / "BRANDING"}


def test_lint_ok(fixture):
    r = _run("lint", "--manifest", str(fixture["manifest"]))
    assert r.returncode == 0


def test_apply_verify_revert_roundtrip(fixture):
    c, pin, m = fixture["checkout"], fixture["pin"], fixture["manifest"]
    r = _run("apply", "--checkout", str(c), "--pin", pin, "--manifest", str(m))
    assert r.returncode == 0
    assert "A=XR" in fixture["branding"].read_text()
    # re-apply = idempotent no-op
    r2 = _run("apply", "--checkout", str(c), "--pin", pin, "--manifest", str(m), "--json")
    assert r2.returncode == 0
    assert json.loads(r2.stdout)["results"][0]["status"] == "no-op (already applied)"
    # verify
    r3 = _run("verify", "--checkout", str(c), "--pin", pin, "--manifest", str(m), "--json")
    assert json.loads(r3.stdout)["results"][0]["status"] == "applied"
    # revert -> original
    r4 = _run("revert", "--checkout", str(c), "--pin", pin, "--manifest", str(m))
    assert r4.returncode == 0
    assert "A=one" in fixture["branding"].read_text()


def test_conflict_fails_loud(fixture):
    c, pin, m = fixture["checkout"], fixture["pin"], fixture["manifest"]
    fixture["branding"].write_text("A=CHANGED\nB=two\n")  # drift so patch won't apply
    r = _run("apply", "--checkout", str(c), "--pin", pin, "--manifest", str(m))
    assert r.returncode == 1
    assert "does not apply cleanly" in r.stdout + r.stderr


def test_wrong_pin_refused(fixture):
    c, m = fixture["checkout"], fixture["manifest"]
    r = _run("apply", "--checkout", str(c), "--pin", "0" * 40, "--manifest", str(m))
    assert r.returncode == 1
    assert "!= pin" in r.stdout + r.stderr


def test_path_policy_escape():
    from apply import check_path_policy
    fails = check_path_policy(["../../etc/passwd", "/abs/path"], ["chrome/app/"])
    assert len(fails) == 2


def test_manifest_lint_unknown_key_and_caps(fixture, tmp_path):
    m = fixture["manifest"]
    text = m.read_text()
    # unknown patch field must fail
    bad = tmp_path / "manifest-bad.yaml"
    bad.write_text(text.replace("    dir: branding/0001\n", "    dir: branding/0001\n    bogus_field: 1\n", 1))
    r = _run("lint", "--manifest", str(bad))
    assert r.returncode == 1
    assert "unknown field" in r.stdout + r.stderr
    # unknown category must fail
    bad2 = tmp_path / "manifest-bad2.yaml"
    bad2.write_text(text.replace("category: branding", "category: not_a_class"))
    r2 = _run("lint", "--manifest", str(bad2))
    assert r2.returncode == 1
    assert "not a Plan" in r2.stdout + r2.stderr


def test_missing_patchinfo_field(fixture, tmp_path):
    m = fixture["manifest"]
    info = m.parent / "branding" / "0001" / "patchinfo.md"
    info.write_text("- **id:** 0001\n- **title:** t\n")  # drop most fields
    r = _run("lint", "--manifest", str(m))
    assert r.returncode == 1
    assert "missing mandatory field" in r.stdout + r.stderr


# --- P3 T0.3 (D2 regression): absent manifest must fail CLEAN, never crash ---

def test_lint_no_args_outside_checkout_fails_clean(tmp_path, monkeypatch):
    """No --manifest, no --checkout, cwd has no chromium/ checkout: the exact
    D2 path that used to die with TypeError(NoneType)."""
    monkeypatch.chdir(tmp_path)  # outside any git repo / checkout
    r = _run("lint", cwd=tmp_path)
    assert r.returncode == 1
    assert "manifest not found at" in r.stderr
    assert "run build sync" in r.stderr
    assert "Traceback" not in r.stderr + r.stdout
    assert "TypeError" not in r.stderr + r.stdout


def test_lint_missing_manifest_explicit_path_fails_clean(tmp_path):
    r = _run("lint", "--manifest", str(tmp_path / "nope" / "manifest.yaml"))
    assert r.returncode == 1
    assert "manifest not found at" in r.stderr
    assert "run build sync" in r.stderr
    assert "Traceback" not in r.stderr + r.stdout


def test_lint_missing_manifest_from_repo_cites_deps_pin(tmp_path):
    """Run from the real repo (no checkout present): error cites the DEPS
    xr_core_rev so the operator knows which rev to sync."""
    repo = HERE.parents[2]  # .../xr-browser (tests -> patching -> build -> repo)
    r = _run("lint", cwd=repo)
    assert r.returncode == 1
    msg = r.stderr
    assert "manifest not found at" in msg
    assert "run build sync" in msg
    import re
    m = re.search(r"xr-core rev ([0-9a-f]{40}|\S+)", msg)
    assert m, f"no xr-core rev cited in: {msg}"
    if m.group(1) != "<unknown>":  # repo present -> must be the DEPS pin
        deps_pin = None
        for line in (repo / "DEPS").read_text().splitlines():
            if line.startswith("xr_core_rev:"):
                deps_pin = line.split('"')[1]
        assert m.group(1) == deps_pin
    assert "Traceback" not in msg
