"""build/upstream/fixtures.py — synthetic chromium-mini corpora (P3).

The Plan's exact synthetic drill (§4 P3 Tests): "inject a fake upstream
refactor across 5 XR patches, verify classification+issues+fix; budget-break
injection fails CI." Fixtures are MINIMAL SYNTHETIC TREES authored here —
never copied Chromium blobs (research fixtures rule); real-upstream data is
fetched live by the real lane and stamped source:"real".

Corpus (5 patches, one per classification):
  F-0001-clean     target identical to pin
  F-0002-drift     upstream drift on a hunk-context line (direct apply fails,
                   three-way merge clean)  -> textual-drift(3way-ok)
  F-0003-moved     target path absent; identical content under a new path
  F-0004-deleted   target path absent, content gone
  F-0005-semantic  upstream rewrote the exact line the patch touches

All files share a canonical 4-line shape so the generated hunks are valid at
the pin rev; drift/semantic events modify specific lines (see REV_* below).
"""
from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Any

REV_A = "a" * 40          # "pin" rev in every fixture corpus
REV_B = "b" * 40          # first fake upstream range target (full event set)
REV_C = "c" * 40          # second range target (moved-file moves again)
REV_D = "d" * 40          # third range target: everything reverts -> GREEN

F1 = "chrome/app/theme/xr/ONE"
F2 = "chrome/app/theme/xr/TWO"
F3 = "chrome/app/moved/THREE"
F4 = "chrome/app/gone/FOUR"
F5 = "chrome/app/semantic/FIVE"


def _canon(payload: str) -> str:
    return f"context-one\ncontext-two\n{payload}\ncontext-three\n"


def _patch(path: str, old: str, new: str) -> str:
    return (f"--- a/{path}\n+++ b/{path}\n@@ -1,4 +1,4 @@\n"
            f" context-one\n context-two\n-{old}\n+{new}\n context-three\n")


PIN_FILES = {
    F1: _canon("original-one"),
    F2: _canon("original-two"),
    F3: _canon("original-three"),
    F4: _canon("original-four"),
    F5: _canon("original-five"),
}

FILES_B = dict(PIN_FILES)
FILES_B[F2] = "context-one-drifted\ncontext-two\noriginal-two\ncontext-three\n"
del FILES_B[F3]
FILES_B["chrome/app/moved/THREE-RENAMED"] = PIN_FILES[F3]
del FILES_B[F4]
FILES_B[F5] = _canon("UPSTREAM-REWRITE")

FILES_C = dict(FILES_B)
del FILES_C["chrome/app/moved/THREE-RENAMED"]
FILES_C["chrome/app/moved/THREE-MOVED-AGAIN"] = PIN_FILES[F3]

FILES_D = dict(PIN_FILES)  # everything back at pin content -> GREEN range

PATCHES = [
    {"id": "F-0001-clean", "owner": "@xr/platform", "category": "branding",
     "files": [F1], "patch": _patch(F1, "original-one", "XR-one")},
    {"id": "F-0002-drift", "owner": "@xr/platform", "category": "branding",
     "files": [F2], "patch": _patch(F2, "original-two", "XR-two")},
    {"id": "F-0003-moved", "owner": "@xr/platform", "category": "ui",
     "files": [F3], "patch": _patch(F3, "original-three", "XR-three")},
    {"id": "F-0004-deleted", "owner": "@xr/platform", "category": "hook_points",
     "files": [F4], "patch": _patch(F4, "original-four", "XR-four")},
    {"id": "F-0005-semantic", "owner": "@xr/security", "category": "content_seams",
     "files": [F5], "patch": _patch(F5, "original-five", "XR-five")},
]

REV_FILES = {REV_A: PIN_FILES, REV_B: FILES_B, REV_C: FILES_C, REV_D: FILES_D}


def build_corpus() -> dict[str, Any]:
    return {"revs": [REV_A, REV_B, REV_C, REV_D],
            "files": REV_FILES, "patches": PATCHES}


def fixture_source_for(corpus: dict[str, Any] | None = None):
    """Build a FixtureFetchSource over the corpus (offline, deterministic)."""
    from fetch import FixtureFetchSource
    corpus = corpus or build_corpus()
    files: dict[tuple[str, str], str] = {}
    dirs: dict[tuple[str, str], list[str]] = {}
    for rev, revfiles in corpus["files"].items():
        for path, text in revfiles.items():
            files[(rev, path)] = text
            parent = posixpath.dirname(path)
            name = posixpath.basename(path)
            lst = dirs.setdefault((rev, parent), [])
            if name not in lst:
                lst.append(name)
    logs = {
        REV_B: [
            {"commit": REV_B, "message": "fake upstream refactor: rename THREE, drop FOUR, rewrite FIVE, drift TWO\n\nBug: b:1\nCr-Commit-Position: refs/heads/fake-main@{#2}",
             "committer": {"time": "Mon Sep 07 10:00:00 2026"}},
        ],
        f"{REV_A}..{REV_B}": [
            {"commit": REV_B, "message": "fake upstream refactor: rename THREE, drop FOUR, rewrite FIVE, drift TWO\n\nBug: b:1\nCr-Commit-Position: refs/heads/fake-main@{#2}",
             "committer": {"time": "Mon Sep 07 10:00:00 2026"}},
        ],
    }
    refs = {"tags/fake-1.0.0.0": REV_B}
    return FixtureFetchSource(files=files, dirs=dirs, logs=logs, refs=refs)


def write_manifest_tree(root: Path, corpus: dict[str, Any] | None = None) -> Path:
    """Materialize a fake xr-core (manifest + patch dirs) under root; returns
    the manifest path. Used by the e2e drill and `rebase-bot selftest`."""
    corpus = corpus or build_corpus()
    mdir = root / "patches"
    for p in corpus["patches"]:
        d = mdir / p["category"] / p["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{p['id']}.patch").write_text(p["patch"], encoding="utf-8")
        (d / "patchinfo.md").write_text(
            f"- **id:** {p['id']}\n- **title:** fixture {p['id']}\n"
            f"- **owner:** {p['owner']}\n- **category:** {p['category']}\n"
            f"- **files:** {', '.join(p['files'])}\n- **upstream-bug-if-any:** none\n"
            f"- **retirement plan:** fixture (retired with the corpus)\n"
            f"- **rebase-notes:** synthetic drill patch (P3 fixtures.py)\n", encoding="utf-8")
    manifest = mdir / "manifest.yaml"
    lines = ["schema_version: 1", "total_cap: 150",
             "categories:",
             "  branding: { cap: null }", "  hook_points: { cap: 45 }",
             "  blink_seams: { cap: 25 }", "  content_seams: { cap: 30 }",
             "  network_seams: { cap: 20 }", "  ui: { cap: 35 }",
             "  extension_chokepoint: { cap: 2 }",
             "allowed_roots:", "  - \"chrome/app/\"", "patches:"]
    for p in corpus["patches"]:
        lines += [f"  - id: \"{p['id']}\"", f"    owner: \"{p['owner']}\"",
                  f"    category: {p['category']}", "    files:",
                  *[f"      - \"{f}\"" for f in p["files"]],
                  f"    dir: {p['category']}/{p['id']}"]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def expected_classes(rev: str) -> dict[str, str]:
    """The drill's asserted routing per rev (test oracle)."""
    if rev == REV_B or rev == REV_C:
        return {"F-0001-clean": "clean", "F-0002-drift": "textual-drift(3way-ok)",
                "F-0003-moved": "file-moved", "F-0004-deleted": "file-deleted",
                "F-0005-semantic": "semantic"}
    if rev == REV_D:
        return {"F-0001-clean": "clean", "F-0002-drift": "clean",
                "F-0003-moved": "clean", "F-0004-deleted": "clean",
                "F-0005-semantic": "clean"}
    raise ValueError(f"unknown fixture rev {rev!r}")
