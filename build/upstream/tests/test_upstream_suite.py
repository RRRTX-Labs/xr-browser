"""P3 upstream-toolchain tests — the Plan's P3 acceptance surface, offline.

Covers (Plan §4 P3 Tests):
  - 3 sequential fake upstream ranges → classification verdicts + expected classes
  - ≥1 DRIFT/BROKEN range routes owner issue bundles (T2)
  - rebase-report schema self-validation (patch-ledger-v1 contract)
  - budget-break injection fails the gate (T3)
  - retirement: sanctioned path writes ledger + removes patch; raw removal
    without a ledger fails retirement-lint (T7)
  - assumptions: file-contract PASS/FAIL + pending-feature SKIP never passes (T6)
  - SLA clock deadline math from TAG PUBLICATION (T5)
  - fast-lane drills: in-window no-breach / breach freeze-marker (T5)
  - promotion series discovery over a fixture releases() source (T4)
  - dry-run reports are never citable as applied state (mode + no branch)

The REAL lane (pin + 2 later main SHAs via gitiles TEXT) runs in CI behind
XR_LIVE_NET and is evidenced under evidence/P3/logs/ — not here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import fixtures
from classify import (CLASS_CLEAN, CLASS_DRIFT, validate_rebase_report,
                      verdict_of, VERDICT_GREEN)
from fetch import FixtureFetchSource
import issues as issues_mod
import rebase_bot
import retirements as retirements_mod
import assumptions as assumptions_mod
import fastlane as fastlane_mod


@pytest.fixture(scope="module")
def corpus_setup(tmp_path_factory):
    corpus = fixtures.build_corpus()
    source = fixtures.fixture_source_for(corpus)
    root = tmp_path_factory.mktemp("fixture-xr")
    manifest = fixtures.write_manifest_tree(root, corpus)
    return corpus, source, root, manifest


def test_three_sequential_ranges_expected_classes(corpus_setup):
    """3 sequential fake upstream ranges; every patch classified per oracle."""
    corpus, source, root, manifest = corpus_setup
    for rev in (fixtures.REV_B, fixtures.REV_C, fixtures.REV_D):
        report = rebase_bot.run_rebase(
            to=rev, manifest_path=manifest, source=source,
            from_rev=fixtures.REV_A, source_label="fixture",
            work_dir=root / "work", dry_run=True)
        expected = fixtures.expected_classes(rev)
        got = {p["id"]: p["cls"] for p in report["patches"]}
        assert got == expected, f"{rev[:8]}: {got} != {expected}"
        assert validate_rebase_report(report) == []
        if rev == fixtures.REV_D:
            assert report["verdict"] == VERDICT_GREEN
        else:
            assert report["verdict"] != VERDICT_GREEN


def test_drift_range_routes_owner_issue_bundles(corpus_setup, tmp_path):
    """≥1 non-GREEN range ⇒ issue bundles materialize, owner-routed (T2)."""
    _, source, root, manifest = corpus_setup
    report = rebase_bot.run_rebase(
        to=fixtures.REV_B, manifest_path=manifest, source=source,
        from_rev=fixtures.REV_A, source_label="fixture",
        work_dir=tmp_path / "work", dry_run=True)
    assert report["verdict"] != VERDICT_GREEN
    bundles = issues_mod.route(report, tmp_path / "work" / "issues")
    assert bundles, "non-GREEN verdict must route issue bundles"
    owners = set()
    for b in bundles:
        text = b.read_text(encoding="utf-8")
        assert "UNVERIFIED" not in text or "listed as UNVERIFIED" in text
        for p in report["patches"]:
            if p["id"] in text and p["cls"] != CLASS_CLEAN:
                owners.add(p["owner"])
    assert owners, "bundles must carry owner routing"
    # one bundle per conflicting patch, named for it
    names = " ".join(b.name for b in bundles)
    for pid in ("F-0003-moved", "F-0004-deleted", "F-0005-semantic"):
        assert pid in names, f"{pid} bundle missing"


def test_dry_run_is_never_citable_as_applied_state(corpus_setup, tmp_path):
    _, source, root, manifest = corpus_setup
    report = rebase_bot.run_rebase(
        to=fixtures.REV_B, manifest_path=manifest, source=source,
        from_rev=fixtures.REV_A, source_label="fixture",
        work_dir=tmp_path / "work", dry_run=True)
    assert report["mode"] == "dry-run"
    assert "prepared_branch" not in report


def test_budget_break_injection_fails_gate(tmp_path):
    """Budget-break injection: over-cap manifest must fail the T3 gate."""
    manifest = tmp_path / "manifest.yaml"
    rows = []
    for i in range(3):  # extension_chokepoint cap = 2
        rows += [f'  - id: "inj-{i}"', "    owner: \"@xr/security\"",
                 "    category: extension_chokepoint", "    files:",
                 "      - \"extensions/test.txt\"",
                 f"    dir: inj/{i}"]
        d = tmp_path / "inj" / str(i)
        d.mkdir(parents=True, exist_ok=True)
        (d / "inj.patch").write_text("--- a/extensions/test.txt\n+++ b/extensions/test.txt\n"
                                     "@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")
    manifest.write_text(
        "schema_version: 1\ntotal_cap: 150\ncategories:\n"
        "  extension_chokepoint: { cap: 2 }\nallowed_roots:\n  - \"extensions/\"\n"
        "patches:\n" + "\n".join(rows) + "\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[2] / "farm" / "budget_meter.py"),
         "budget", "--manifest", str(manifest), "--gate"],
        capture_output=True, text=True)
    assert r.returncode == 1, f"over-cap manifest must fail the gate:\n{r.stdout}"
    assert "extension_chokepoint" in r.stdout


def _mini_git_manifest(root: Path) -> Path:
    """A tiny xr-core-like git repo with one patch in the manifest."""
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(root), "config", k, v],
                       check=True, capture_output=True)
    mdir = root / "patches"
    (mdir / "p" / "one").mkdir(parents=True)
    (mdir / "p" / "one" / "one.patch").write_text(
        "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")
    manifest = mdir / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\ntotal_cap: 150\ncategories:\n  ui: { cap: 35 }\n"
        "allowed_roots:\n  - \"a.txt\"\npatches:\n"
        '  - id: "one"\n    owner: "@xr/platform"\n    category: ui\n'
        "    files:\n      - \"a.txt\"\n    dir: p/one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True, capture_output=True)
    return manifest


def test_retire_sanctioned_path_and_lint(tmp_path):
    """xr-patch retire writes the ledger row + removes the patch; lint PASS."""
    root = tmp_path / "meta"
    root.mkdir()
    manifest = _mini_git_manifest(tmp_path / "xr-core")
    retirements_mod.append_retirement(
        root, patch_id="one", mechanism="upstreamed",
        evidence="crrev.com/c/123 (test)", note="test retirement",
        rev_retired_at="a" * 40, retired_by="t@t")
    retirements_mod.remove_patch_from_manifest(manifest, "one")
    fails = retirements_mod.lint(root, xr_core_dir=tmp_path / "xr-core")
    assert fails == [], fails


def test_removal_without_ledger_fails_lint(tmp_path):
    """Raw manifest removal (no xr-patch retire) fails retirement-lint."""
    root = tmp_path / "meta"
    root.mkdir()
    xr_core = tmp_path / "xr-core"
    _mini_git_manifest(xr_core)
    text = (xr_core / "patches" / "manifest.yaml").read_text(encoding="utf-8")
    (xr_core / "patches" / "manifest.yaml").write_text(
        text.split("patches:")[0] + "patches:\n", encoding="utf-8")
    (xr_core / "patches" / "p" / "one").exists() and None
    subprocess.run(["git", "-C", str(xr_core), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(xr_core), "commit", "-qm", "raw removal"],
                   check=True, capture_output=True)
    fails = retirements_mod.lint(root, xr_core_dir=xr_core)
    assert any("without a ledger entry" in f for f in fails), fails


def test_assumptions_contract_rows(tmp_path):
    """file-contract PASS/FAIL + pending-feature SKIP never passes (L6)."""
    files = {("r1", "a/b.txt"): "hello GetStoragePartitionConfig world"}
    source = FixtureFetchSource(files=files)
    reg = {"schema_version": 1, "rows": [
        {"id": "A1", "assumption": "pending feature", "owner": "@xr/security",
         "check_type": "pending-feature", "reason": "needs P12 runtime tests",
         "since_rev": "r1"},
        {"id": "A2", "assumption": "surface exists", "owner": "@xr/net",
         "check_type": "file-contract", "file": "a/b.txt",
         "contains": ["GetStoragePartitionConfig"], "since_rev": "r1"},
        {"id": "A3", "assumption": "missing string", "owner": "@xr/net",
         "check_type": "file-contract", "file": "a/b.txt",
         "contains": ["NoSuchSymbolAnywhere"], "since_rev": "r1"},
    ]}
    results, fails = assumptions_mod.run_rows(source, "r1", reg)
    by_id = {r["id"]: r for r in results}
    assert by_id["A1"]["status"] == "SKIP"
    assert by_id["A2"]["status"] == "PASS"
    assert by_id["A3"]["status"] == "FAIL"
    assert len(fails) == 1
    # SKIP never passes even when everything else is green
    assert all(r["status"] != "PASS" for r in results if r["id"] == "A1")


def test_sla_clock_from_tag_publication():
    """72h critical deadline measured from TAG PUBLICATION (not announcement)."""
    from datetime import datetime, timedelta, timezone
    published = datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc)
    rel = fastlane_mod.SecurityRelease(
        version="150.0.0.1", channel="Stable", milestone=150,
        published_at=published, previous_version="150.0.0.0",
        chromium_hash="f" * 40, source="fixture")
    plan = fastlane_mod.build_plan(rel)
    assert plan["deadlines"]["critical_iit"].startswith("2026-09-06T18:00")
    assert plan["sla_hours"]["critical_iit"] == 72
    clock = fastlane_mod.sla_clock(since_tag="150.0.0.1", published_at=published,
                                   severity="critical",
                                   now=published + timedelta(hours=80))
    assert clock["breached"] is True
    clock_ok = fastlane_mod.sla_clock(since_tag="150.0.0.1", published_at=published,
                                      severity="critical",
                                      now=published + timedelta(hours=30))
    assert clock_ok["breached"] is False
    assert clock_ok["remaining_hours"] == pytest.approx(42.0, abs=0.1)
    high = fastlane_mod.sla_clock(since_tag="150.0.0.1", published_at=published,
                                  severity="high",
                                  now=published + timedelta(hours=100))
    assert high["breached"] is False  # 14d window


def test_fastlane_drills(tmp_path):
    """Both drills PASS: in-window no freeze; breach writes the marker.

    P4-T0.1: the drill shell out to `minisign` (TEST keys) to sign the
    fixture artifact. On a host without it (bare clone, GitHub-hosted
    runner) the test SKIPS with a visible reason instead of failing —
    L6, never a silent pass, never a deleted test. When minisign IS
    installed the full round-trip below executes unchanged.
    """
    import skip_policy
    skip_policy.pytest_skip_if_absent("minisign")
    xr_root = Path(rebase_bot.__file__).resolve().parents[2]
    ok = fastlane_mod.run_drill(out_dir=tmp_path / "drill1-in-window",
                                root=xr_root, label="in-window",
                                published_hours_ago=30.0, expect_breach=False)
    assert ok["verdict"] == "PASS"
    assert ok["source"] == "fixture" and ok["simulated"] is True
    assert not (tmp_path / "drill1-in-window" / "feature-freeze.json").exists()
    bad = fastlane_mod.run_drill(out_dir=tmp_path / "drill2-breach",
                                 root=xr_root, label="breach",
                                 published_hours_ago=80.0, expect_breach=True)
    assert bad["verdict"] == "PASS"
    assert bad["steps"]["sla"]["breached"] is True
    assert (tmp_path / "drill2-breach" / "feature-freeze.json").exists()


def test_promotion_series_discovery_even_milestone(tmp_path):
    """Series discovery picks the even-milestone Extended release (cadence as data)."""
    import promotion as promotion_mod
    src = FixtureFetchSource(release_rows=[
        {"version": "153.0.5", "channel": "Extended", "milestone": 153,
         "time": 1, "platform": "All"},
        {"version": "152.0.4", "channel": "Extended", "milestone": 152,
         "time": 2, "platform": "All"},
    ])
    series = promotion_mod.discover_series(src, promotion_mod.load_config())
    assert series["milestone"] == 152 and series["version"] == "152.0.4"
    assert series["source"] == "real"  # discovery is live-data-shaped even in tests


def test_verdict_ordering():
    """BROKEN dominates DRIFT dominates GREEN."""
    from classify import PatchResult
    def pr(cls):
        return PatchResult(id="x", owner="o", category="ui", cls=cls, files=[])
    assert verdict_of([pr(CLASS_CLEAN), pr(CLASS_DRIFT)]) == "DRIFT"
    assert verdict_of([pr(CLASS_CLEAN), pr(CLASS_DRIFT), pr("semantic")]) == "BROKEN"
    assert verdict_of([pr(CLASS_CLEAN), pr(CLASS_CLEAN)]) == "GREEN"


# ---------------------------------------------------------------------------
# T0 — added-file semantics (P8 blocking debt). A manifest file missing at the
# pin is a patch ADDITION: clean when absent at the target too; BROKEN
# path-collision when upstream now owns the path. Moved-detection is never
# attempted for additions (no pin bytes to hash).
# ---------------------------------------------------------------------------

def test_t0_added_file_absent_at_target_is_clean():
    """addition + path absent at target => clean (apply creates the file)."""
    from classify import CLASS_PATH_COLLISION, classify_patch
    patch_text = fixtures._added_patch(fixtures.F6, "one\n")
    res = classify_patch("F-0006-added", "@xr/platform", "ui", patch_text,
                         pin_files={}, target_files={},
                         additions=[fixtures.F6])
    assert res.cls == CLASS_CLEAN, res.cls
    assert res.files and res.files[0].cls == CLASS_CLEAN
    assert "patch-added file" in res.files[0].detail
    assert verdict_of([res]) == VERDICT_GREEN
    assert res.cls != CLASS_PATH_COLLISION


def test_t0_added_file_present_at_target_is_path_collision():
    """addition + path PRESENT at target => path-collision (BROKEN, human item)."""
    from classify import (CLASS_PATH_COLLISION, VERDICT_BROKEN, classify_patch)
    patch_text = fixtures._added_patch(fixtures.F6, "one\n")
    target = {fixtures.F6: "upstream grew this file itself\n"}
    res = classify_patch("F-0006-added", "@xr/platform", "ui", patch_text,
                         pin_files={}, target_files=target,
                         additions=[fixtures.F6])
    assert res.cls == CLASS_PATH_COLLISION, res.cls
    assert verdict_of([res]) == VERDICT_BROKEN
    assert "never silently renamed" in res.files[0].detail


def test_t0_mixed_entry_drift_hook_plus_added_file():
    """A patch with an upstream hook (drifted) AND an added file classifies
    each file on its own: drift on the hook, clean on the addition."""
    from classify import classify_patch
    hook = fixtures.F2
    pin = {hook: fixtures._canon("original-two")}
    drifted = "context-one-drifted\ncontext-two\noriginal-two\ncontext-three\n"
    target = {hook: drifted}
    hook_patch = fixtures._patch(hook, "original-two", "XR-two")
    added_patch = fixtures._added_patch(fixtures.F6, "one\n")
    res = classify_patch("mixed", "@xr/platform", "ui",
                         hook_patch + added_patch,
                         pin_files=pin, target_files=target,
                         additions=[fixtures.F6])
    by_path = {f.path: f.cls for f in res.files}
    assert by_path[hook] == CLASS_DRIFT
    assert by_path[fixtures.F6] == CLASS_CLEAN
    assert res.cls == CLASS_DRIFT  # worst non-clean wins at patch level


def test_t0_run_rebase_reports_added_files_clean_with_rows(corpus_setup):
    """run_rebase end-to-end: the addition row is reported per-file (clean)
    instead of killing the canary with a fetch error."""
    _, source, root, manifest = corpus_setup
    report = rebase_bot.run_rebase(
        to=fixtures.REV_C, manifest_path=manifest, source=source,
        from_rev=fixtures.REV_A, source_label="fixture",
        work_dir=root / "work2", dry_run=True)
    row = next(p for p in report["patches"] if p["id"] == "F-0006-added")
    assert row["cls"] == CLASS_CLEAN
    assert any(f["cls"] == CLASS_CLEAN and "patch-added" in f["detail"]
               for f in row["files"])


def test_t0_classify_rejects_engine_misuse():
    """No overlap between pin files and additions; no moved entry for an
    addition (moved detection hashes pin bytes that additions lack)."""
    import pytest as _pytest
    from classify import ClassifyError, classify_patch
    patch_text = fixtures._added_patch(fixtures.F6, "one\n")
    with _pytest.raises(ClassifyError):
        classify_patch("x", "o", "ui", patch_text,
                       pin_files={fixtures.F6: "pin bytes"}, target_files={},
                       additions=[fixtures.F6])
    with _pytest.raises(ClassifyError):
        classify_patch("x", "o", "ui", patch_text,
                       pin_files={}, target_files={}, additions=[fixtures.F6],
                       moved_targets={fixtures.F6: "somewhere/else"})
    with _pytest.raises(ClassifyError):
        classify_patch("x", "o", "ui", patch_text, pin_files={},
                       target_files={}, additions=[fixtures.F6, fixtures.F6])


def test_t0_promotion_smoke_added_file_accepted_deleted_hook_refused(tmp_path):
    """promotion compat smoke: an added file is absent at the candidate rev BY
    DEFINITION — materialize as absent, let apply create it (clean); a hooked
    file upstream deleted fails the apply and is a refusal."""
    import promotion as promotion_mod
    # added-file-only patch: manifest with one entry (F-0006 at no rev)
    corpus_add = fixtures.build_corpus()
    corpus_add["patches"] = [p for p in corpus_add["patches"]
                             if p["id"] == "F-0006-added"]
    manifest_add = fixtures.write_manifest_tree(tmp_path / "add", corpus_add)
    src_add = fixtures.fixture_source_for(corpus_add)
    ok, detail = promotion_mod._patch_roundtrip_at(
        src_add, manifest_add, fixtures.REV_C)
    assert ok, f"added file must be created by apply: {detail}"
    # deleted-hook patch: F-0004's file is gone from REV_C — apply cannot find
    # it => refusal (a real re-anchor work item, never a silent pass)
    corpus_del = fixtures.build_corpus()
    corpus_del["patches"] = [p for p in corpus_del["patches"]
                             if p["id"] == "F-0004-deleted"]
    manifest_del = fixtures.write_manifest_tree(tmp_path / "del", corpus_del)
    src_del = fixtures.fixture_source_for(corpus_del)
    ok2, detail2 = promotion_mod._patch_roundtrip_at(
        src_del, manifest_del, fixtures.REV_C)
    assert not ok2, "an upstream-deleted hook file must refuse the smoke"
    assert "does not apply" in detail2
