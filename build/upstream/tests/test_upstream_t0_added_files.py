"""build/upstream/tests/test_upstream_t0_added_files.py — added-file
semantics (P8 blocking debt), split out of test_upstream_suite.py by the
P11-T0-e touched-file size law (<=380 lines): the T0 canary family is its
own responsibility — a manifest file missing at the pin is a patch
ADDITION: clean when absent at the target too; BROKEN path-collision when
upstream now owns the path. Moved-detection is never attempted for
additions (no pin bytes to hash).
"""
from __future__ import annotations

import fixtures
from classify import (CLASS_CLEAN, CLASS_DRIFT, verdict_of, VERDICT_GREEN)
import rebase_bot


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
