#!/usr/bin/env python3
"""tools/patch_manifest_check.py — declared `files:` vs the patch's real diff.

`docs/contracts/patch-manifest-v1.md` §2 calls a row's `files:` list "upstream
files touched (metadata; **the .patch is truth**)". Nothing else in the tree
compared the metadata to the truth, so a row could drift from its own diff and
stay green: the first P12 row declared 4 files while its patch touched 5 (the
payload's BUILD.gn was omitted), and `xr-patch lint` passed it correctly — that
list is not its input.

So this tool checks ONE thing, in both directions:

  * a declared path the patch does not touch — the metadata over-reports, so a
    reader auditing by the manifest is told the patch is bigger than it is;
  * a touched path the row does not declare — the metadata under-reports, and
    `build/farm/budget_meter.py`'s `registered_files()` reads exactly this list
    to decide what counts as registered, so an undeclared upstream file is
    invisible to the audit surface it feeds.

WHAT THIS TOOL DELIBERATELY DOES NOT CHECK, and who does:

  * per-category and total caps — `build/patching/apply.py lint` and
    `build/farm/budget_meter.py` own them, and since P12-CLOSE T0-U3 the meter
    counts FILES (derived from each patch's diff headers) against the caps,
    exactly as the plan's "~N files" columns read. `apply.py lint` keeps its
    entry-count lint shape pinned by test_apply_lint_does_not_see_files_drift
    (division of labour). An earlier version of THIS file counted files against
    caps before the meter did — falsely failing 30 files over 2 patches — and
    was removed; the meter is now the single files-vs-cap enforcement point.
  * allowed_roots membership of the diff paths — `apply.py lint` runs
    `check_path_policy(diff_paths(pf), roots)` on the real patch.
  * patchinfo.md mandatory fields and id match — `lint_patchinfo()`.
  * duplicate ids, category validity, unknown row fields — `lint_manifest()`.

The touched-path extraction reads the `--- a/` and `+++ b/` headers, which is
what `git apply` consumes, so the metadata is compared against the same notion
of "what this patch changes" that the tool applying it uses. Pure adds
(`--- /dev/null`) and pure deletes (`+++ /dev/null`) are both handled.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required (pip install pyyaml)")
    sys.exit(1)

MANIFEST = "patches/manifest.yaml"
# `git diff` emits these headers; `/dev/null` marks a pure add or delete.
MINUS_RE = re.compile(r"^--- (?:a/(.+)|/dev/null)\t?")
PLUS_RE = re.compile(r"^\+\+\+ (?:b/(.+)|/dev/null)\t?")

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def touched_paths(patch: Path) -> set[str]:
    """Every path the patch changes, as `git apply` would see it.

    A pure add has `--- /dev/null` + `+++ b/x`; a pure delete is the reverse; a
    modify has both. Taking the union of the two sides and dropping /dev/null
    handles all three without guessing at hunk contents.
    """
    out: set[str] = set()
    for line in patch.read_text(encoding="utf-8").splitlines():
        for rx in (MINUS_RE, PLUS_RE):
            m = rx.match(line)
            if m and m.group(1):
                out.add(m.group(1))
    return out


def check(manifest: Path) -> tuple[list[str], dict[str, int]]:
    fails: list[str] = []
    man = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(man, dict):
        return [f"{MANIFEST}: not a mapping"], {}

    rows = man.get("patches") or []
    counts = {"patches": len(rows), "files": 0, "drift": 0}
    if not rows:
        # Not a failure — an empty ledger is a legitimate state — but it must
        # say so, because "0 patches, PASS" and "checked nothing, PASS" are
        # different claims and only the counts tell them apart.
        print("NOTE: the manifest declares no patches — nothing to check")
        return fails, counts

    base = manifest.parent
    for row in rows:
        if not isinstance(row, dict):
            fails.append(f"{MANIFEST}: patch row is not a mapping: {row!r}")
            continue
        pid = row.get("id") or "<no id>"
        declared = list(row.get("files") or [])
        d = row.get("dir")
        if not d:
            continue  # apply.py lint owns the missing-dir finding
        patch = base / d / f"{pid}.patch"
        if not patch.is_file():
            continue  # apply.py lint owns the missing-patch finding
        actual = touched_paths(patch)
        counts["files"] += len(actual)
        missing = sorted(set(declared) - actual)
        extra = sorted(actual - set(declared))
        counts["drift"] += len(missing) + len(extra)
        if missing:
            fails.append(f"{pid}: declares {len(missing)} file(s) the patch "
                         f"does not touch — the metadata over-reports, so a "
                         f"reader auditing by the manifest is told the patch is "
                         f"bigger than it is: " + ", ".join(missing))
        if extra:
            fails.append(f"{pid}: touches {len(extra)} file(s) the row does not "
                         f"declare — the metadata under-reports, and "
                         f"budget_meter.py's registered_files() reads this "
                         f"list, so the file is invisible to the audit surface "
                         f"it feeds: " + ", ".join(extra))
    return fails, counts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="patch-manifest-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default="../xr-core",
                    help="xr-core checkout (default: ../xr-core)")
    a = ap.parse_args(argv)
    manifest = Path(a.xr_core).resolve() / MANIFEST
    if not manifest.is_file():
        print(f"FAIL: {manifest} not found")
        return EXIT_FAIL

    fails, counts = check(manifest)
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: patch_manifest_check (patches: {counts.get('patches')}, "
              f"files: {counts.get('files')}, drifted: {counts.get('drift')}; "
              f"{len(fails)} finding(s))")
        return EXIT_FAIL
    print(f"PASS: patch_manifest_check (patches: {counts['patches']}, "
          f"files: {counts['files']}, drifted: 0 — declared `files:` equals "
          f"the patch diff in both directions)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
