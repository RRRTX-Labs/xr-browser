"""build/upstream/classify.py — patch-applicability classification engine (P3-T1).

Pure engine: no network, no repo state — consumes file contents and patch
texts, produces per-file and per-patch classifications per Plan §12.3
semantics. Shared by the rebase bot (real lane), the fixture drills
(`rebase-bot selftest`) and the promotion job's compat smoke.

Classification classes (Plan §4 P3-T2, phase prompt §12.3):
  clean                  patch applies as-is at the target rev
  textual-drift(3way-ok) content drifted but the three-way merge is clean
                         (git merge-file rc=0; base=pin, ours=patched-pin,
                         theirs=target — R5 research note: works without
                         patch `index` lines, which the XR corpus lacks)
  semantic               three-way merge conflicts (rc>0) — human resolution
                         in PATCH SEMANTICS; never disable/TODO (§12.3 law)
  file-moved             target path absent; identical pin content found at a
                         different path in the target rev (re-anchor candidate)
  file-deleted           target path absent and content gone (retirement
                         review per §12.3 — user-visible consequence)
  stale-base             patch does not apply against its OWN recorded pin
                         (manifest rot; the manifest/patch pair is inconsistent)
  (added file, T0)       a manifest file ABSENT at the pin is a patch
                         ADDITION (the patch creates it; e.g. XR-owned
                         payload files that exist at no upstream rev):
                           addition + absent at target  -> clean
                           addition + PRESENT at target -> path-collision
                         (upstream now owns our path — human work item,
                         BROKEN verdict; never silently renamed)

Verdicts: GREEN (all clean) / DRIFT (moved or textual-drift: mechanical
re-anchor) / BROKEN (semantic, path-collision, deleted or stale-base: human
work item). Conflicts are work items, not outages (§12.1) — exit code 1 +
routed bundle.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CLASS_CLEAN = "clean"
CLASS_DRIFT = "textual-drift(3way-ok)"
CLASS_SEMANTIC = "semantic"
CLASS_MOVED = "file-moved"
CLASS_DELETED = "file-deleted"
CLASS_STALE_BASE = "stale-base"
CLASS_PATH_COLLISION = "path-collision"

# worst -> best ordering for patch-level aggregation. path-collision is a
# BROKEN human work item (T0: upstream now owns a path our patch adds).
_SEVERITY = [CLASS_STALE_BASE, CLASS_SEMANTIC, CLASS_PATH_COLLISION,
             CLASS_DELETED, CLASS_MOVED, CLASS_DRIFT, CLASS_CLEAN]

VERDICT_GREEN = "GREEN"
VERDICT_DRIFT = "DRIFT"
VERDICT_BROKEN = "BROKEN"

_BROKEN_CLASSES = {CLASS_STALE_BASE, CLASS_SEMANTIC, CLASS_DELETED,
                   CLASS_PATH_COLLISION}
_DRIFT_CLASSES = {CLASS_MOVED, CLASS_DRIFT}

VALID_SOURCES = {"real", "fixture"}


class ClassifyError(Exception):
    """Engine misuse (never an upstream condition — those are classes)."""


@dataclass
class FileResult:
    path: str
    cls: str
    detail: str = ""
    moved_to: str | None = None


@dataclass
class PatchResult:
    id: str
    owner: str
    category: str
    cls: str = CLASS_CLEAN
    files: list[FileResult] = field(default_factory=list)
    detail: str = ""


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        # paths come from the validated manifest (apply.py path policy);
        # refuse traversal defensively anyway
        if ".." in Path(rel).parts or rel.startswith("/"):
            raise ClassifyError(f"illegal path in fixture/manifest: {rel!r}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def diff_paths(patch_text: str) -> list[str]:
    """`+++ b/<path>` targets of a unified diff."""
    return [ln[6:].split("\t", 1)[0]
            for ln in patch_text.splitlines() if ln.startswith("+++ b/")]


def apply_check(scratch: Path, patch_text: str) -> tuple[bool, str]:
    """`git apply --check` of patch_text against the tree in scratch."""
    pf = scratch / ".check.patch"
    pf.write_text(patch_text, encoding="utf-8")
    r = _git("apply", "--check", ".check.patch", cwd=scratch)
    pf.unlink(missing_ok=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-800:]


def apply_patch(scratch: Path, patch_text: str) -> tuple[bool, str]:
    """Apply patch_text in scratch (no repo needed — git apply is repo-less)."""
    pf = scratch / ".apply.patch"
    pf.write_text(patch_text, encoding="utf-8")
    r = _git("apply", ".apply.patch", cwd=scratch)
    pf.unlink(missing_ok=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-800:]


def merge_file(ours: str, base: str, theirs: str) -> tuple[int, str]:
    """git merge-file -p ours base theirs → (conflict_count, merged_text).
    rc==0 → clean three-way merge; rc>0 → number of conflicts."""
    with tempfile.TemporaryDirectory(prefix="xr-3way-") as td:
        d = Path(td)
        (d / "ours").write_text(ours, encoding="utf-8")
        (d / "base").write_text(base, encoding="utf-8")
        (d / "theirs").write_text(theirs, encoding="utf-8")
        r = _git("merge-file", "-p", "ours", "base", "theirs", cwd=d)
        return r.returncode, r.stdout


def classify_file(path: str, pin: str, target: str | None,
                  patched: str | None) -> FileResult:
    if target is None:
        return FileResult(path, CLASS_DELETED, "target file absent at to-rev")
    if pin == target:
        return FileResult(path, CLASS_CLEAN)
    if patched is None:
        # file untouched by the patch but drifted upstream: not our conflict —
        # the patch still applies; classify as clean for THIS patch's purposes
        return FileResult(path, CLASS_CLEAN,
                          "upstream drift outside patch scope (hunks unaffected)")
    conflicts, _ = merge_file(patched, pin, target)
    if conflicts == 0:
        return FileResult(path, CLASS_DRIFT,
                          "three-way merge clean (base=pin, ours=patched, theirs=target)")
    return FileResult(path, CLASS_SEMANTIC,
                      f"{conflicts} three-way conflict(s) — resolve in patch semantics (§12.3)")


def _worst(classes: list[str]) -> str:
    for c in _SEVERITY:
        if c in classes:
            return c
    return CLASS_CLEAN


def classify_patch(patch_id: str, owner: str, category: str,
                   patch_text: str,
                   pin_files: dict[str, str],
                   target_files: dict[str, str | None],
                   additions: list[str] | None = None,
                   moved_targets: dict[str, str] | None = None) -> PatchResult:
    """Classify one patch against pin/target file contents.

    pin_files: path -> content at the from-rev (the patch's recorded base)
    target_files: path -> content at the to-rev (None = absent)
    additions: manifest paths ABSENT at the from-rev (patch-ADDED files that
               exist at no upstream rev — the T0 addition semantics: absent
               at the pin is an addition, never a fetch error)
    moved_targets: path -> new path when an identical blob was located elsewhere
    """
    additions = list(additions or [])
    if len(set(additions)) != len(additions):
        raise ClassifyError(f"duplicate addition path in patch {patch_id}")
    overlap = set(additions) & set(pin_files)
    if overlap:
        raise ClassifyError(f"path in both pin_files and additions: "
                            f"{sorted(overlap)} (manifest inconsistency)")
    moved_targets = moved_targets or {}
    # moved detection is byte-hash-based; additions have no pin bytes, so a
    # moved entry for an added path is engine misuse (never attempted).
    if set(additions) & set(moved_targets):
        raise ClassifyError("moved_targets must never contain an added path "
                            "(no pin bytes to hash)")
    res = PatchResult(id=patch_id, owner=owner, category=category)
    all_files = sorted(set(pin_files) | set(additions))

    # 1. the patch must apply at its own recorded pin (stale-base check).
    # Added files are absent at the pin by definition: the pin scratch tree
    # holds only pin-present files and `git apply` creates the additions.
    with tempfile.TemporaryDirectory(prefix="xr-pin-") as td:
        pin_scratch = Path(td)
        _write_tree(pin_scratch, pin_files)
        ok, err = apply_patch(pin_scratch, patch_text)
        if not ok:
            res.cls = CLASS_STALE_BASE
            res.detail = f"patch does not apply at its recorded pin: {err}"
            return res
        patched_files = {p: (pin_scratch / p).read_text(encoding="utf-8")
                         for p in pin_files}

    # 2. clean-at-target check (whole patch; additions are created by apply).
    if all(target_files.get(p) is not None for p in pin_files):
        with tempfile.TemporaryDirectory(prefix="xr-tgt-") as td:
            tgt_scratch = Path(td)
            _write_tree(tgt_scratch, {p: t for p, t in target_files.items()
                                      if t is not None})
            ok, _err = apply_check(tgt_scratch, patch_text)
            if ok:
                for p in all_files:
                    detail = ("patch-added file: absent at pin AND at target — "
                              "apply creates it (whole-patch clean; T0)"
                              if p in additions else "")
                    res.files.append(FileResult(p, CLASS_CLEAN, detail))
                res.cls = CLASS_CLEAN
                return res

    # 3. per-file classification (additions first — they have no pin bytes).
    for path in all_files:
        if path in additions:
            if target_files.get(path) is None:
                res.files.append(FileResult(
                    path, CLASS_CLEAN,
                    "patch-added file: absent at pin AND at target — apply "
                    "creates it (T0 addition semantics)"))
            else:
                res.files.append(FileResult(
                    path, CLASS_PATH_COLLISION,
                    "path-collision: upstream now owns a path this patch "
                    "ADDS — human work item, never silently renamed (T0)"))
            continue
        if path in moved_targets:
            res.files.append(FileResult(
                path, CLASS_MOVED,
                "identical pin content found at a new path (re-anchor candidate)",
                moved_to=moved_targets[path]))
            continue
        res.files.append(classify_file(path, pin_files[path],
                                       target_files.get(path),
                                       patched_files.get(path)))
    res.cls = _worst([f.cls for f in res.files])
    return res


def verdict_of(patches: list[PatchResult]) -> str:
    classes = {p.cls for p in patches}
    if classes & _BROKEN_CLASSES:
        return VERDICT_BROKEN
    if classes & _DRIFT_CLASSES:
        return VERDICT_DRIFT
    return VERDICT_GREEN


def next_action(verdict: str) -> str:
    return {
        VERDICT_GREEN: "all patches apply cleanly at the target rev — proceed to "
                       "promotion/DEPS-bump review (human presses the button; L24)",
        VERDICT_DRIFT: "mechanical re-anchor required: review routed issue bundles "
                       "(3-way merge is clean or path moved); update patches via "
                       "xr-patch machinery, never ad-hoc edits (L10)",
        VERDICT_BROKEN: "semantic work items: owners must resolve in patch "
                        "semantics or retire with a user-visible consequence + "
                        "review entry (§12.3); the bot never drops hooks",
    }[verdict]


# --- rebase-report v1 schema (docs/contracts/patch-ledger-v1.md) ------------

def validate_rebase_report(report: dict) -> list[str]:
    """Fail-closed structural validation of a rebase-report v1 dict.
    Enforces source: fixture|real — a fixture run can never be cited as real."""
    fails: list[str] = []
    if report.get("schema_version") != 1:
        fails.append("schema_version must be 1")
    if report.get("tool") != "xr-rebase":
        fails.append("tool must be 'xr-rebase'")
    if report.get("source") not in VALID_SOURCES:
        fails.append(f"source must be one of {sorted(VALID_SOURCES)}, "
                     f"got {report.get('source')!r}")
    if report.get("verdict") not in (VERDICT_GREEN, VERDICT_DRIFT, VERDICT_BROKEN):
        fails.append(f"verdict invalid: {report.get('verdict')!r}")
    for key in ("from_rev", "to_rev", "to_resolved", "generated_at",
                "wall_clock_seconds", "bytes_fetched", "patches"):
        if key not in report:
            fails.append(f"missing required field {key!r}")
    if fails:
        return fails
    for p in report["patches"]:
        if p.get("source") not in VALID_SOURCES:
            fails.append(f"patch row missing its own source stamp: {p.get('id')!r}")
        if p.get("cls") not in _SEVERITY:
            fails.append(f"patch {p.get('id')!r} class invalid: {p.get('cls')!r}")
        if p.get("source") != report.get("source"):
            fails.append(f"patch row {p.get('id')!r} source stamp diverges from report source")
    return fails
