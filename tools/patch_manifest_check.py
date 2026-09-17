#!/usr/bin/env python3
"""tools/patch_manifest_check.py — the patch budget ledger, machine-checked (P12).

patches/manifest.yaml is the ledger the fork's patch discipline rests on: it
caps how many upstream files each seam category may touch, and the caps are the
only thing standing between "we patch 12 files" and "we patch 900 and stop being
a fork". Until P12 nothing in the tree verified the ledger against the patches
it describes — the caps were prose, and a row whose `files:` list disagreed with
its own diff silently under-counted its category.

That gap is not hypothetical: the first P12 row listed 4 files while the
generated patch touched 5 (the payload's BUILD.gn was omitted), so the row
under-reported its own category by 20 %. This tool is what turns that into a
red gate instead of a drift nobody notices.

Checks, per patch row:
  * `dir` exists and holds `<id>.patch` and `patchinfo.md`;
  * the declared `files:` EQUALS the paths the patch actually touches, in both
    directions — a listed-but-untouched path is a lie in one direction, an
    untouched-by-the-ledger path is a cap bypass in the other;
  * every touched path is under an `allowed_root`;
  * per-category counts are within `categories[*].cap` (null = uncapped), and
    the patch count is within `total_cap`;
  * no duplicate patch ids.

The touched-path extraction reads the patch's `--- a/` and `+++ b/` headers,
which is what `git apply` itself consumes, so the ledger is compared against the
same notion of "what this patch changes" that the tool applying it uses.
Deletions (`+++ /dev/null`) and additions (`--- /dev/null`) are both handled.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
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
    counts: dict[str, int] = {}
    man = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(man, dict):
        return [f"{MANIFEST}: not a mapping"], counts

    roots = man.get("allowed_roots") or []
    cats = man.get("categories") or {}
    total_cap = man.get("total_cap")
    rows = man.get("patches") or []
    counts = {"patches": len(rows), "files": 0, "categories": 0}

    if not rows:
        # Not a failure — an empty ledger is a legitimate state — but it must
        # say so, because "0 patches, PASS" and "checked nothing, PASS" are
        # different claims.
        print("NOTE: the manifest declares no patches — nothing to check")
        return fails, counts

    if not roots:
        fails.append(f"{MANIFEST}: allowed_roots is empty — every patch would "
                     f"be outside the ledger, so the roots are missing rather "
                     f"than permissive")

    seen: Counter[str] = Counter()
    per_cat: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            fails.append(f"{MANIFEST}: patch row is not a mapping: {row!r}")
            continue
        pid = row.get("id") or "<no id>"
        seen[pid] += 1
        d = row.get("dir")
        cat = row.get("category")
        declared = list(row.get("files") or [])
        base = manifest.parent

        if cat not in cats:
            fails.append(f"{pid}: category {cat!r} is not in `categories` — an "
                         f"unknown category is uncapped by default, which is "
                         f"how a cap gets bypassed by typo")
        else:
            per_cat[cat] += len(declared)

        if not d:
            fails.append(f"{pid}: no `dir`")
            continue
        pdir = base / d
        patch = pdir / f"{pid}.patch"
        if not patch.is_file():
            fails.append(f"{pid}: {patch.relative_to(base)} does not exist")
            continue
        if not (pdir / "patchinfo.md").is_file():
            fails.append(f"{pid}: {pdir.relative_to(base)}/patchinfo.md is "
                         f"missing — a patch with no rationale cannot be "
                         f"reviewed or reverted on judgement")

        actual = touched_paths(patch)
        counts["files"] += len(actual)
        missing = sorted(set(declared) - actual)
        extra = sorted(actual - set(declared))
        if missing:
            fails.append(f"{pid}: declares {len(missing)} file(s) the patch "
                         f"does not touch — the ledger over-reports, so the "
                         f"count is not a floor: " + ", ".join(missing))
        if extra:
            fails.append(f"{pid}: touches {len(extra)} file(s) the ledger does "
                         f"not declare — the ledger under-reports, which is the "
                         f"direction that hides a cap breach: "
                         + ", ".join(extra))
        for path in sorted(actual):
            if not any(path.startswith(r) for r in roots):
                fails.append(f"{pid}: {path} is outside every allowed_root "
                             f"({', '.join(roots)})")

    for pid, n in sorted(seen.items()):
        if n > 1:
            fails.append(f"duplicate patch id {pid!r} ({n} rows) — the ledger "
                         f"can no longer say which row a budget belongs to")

    for cat, n in sorted(per_cat.items()):
        spec = cats.get(cat)
        cap = spec.get("cap") if isinstance(spec, dict) else spec
        if isinstance(cap, int) and n > cap:
            fails.append(f"category {cat!r}: {n} declared file(s) > cap {cap}")

    counts["categories"] = len(per_cat)
    if isinstance(total_cap, int) and len(rows) > total_cap:
        fails.append(f"{len(rows)} patches > total_cap {total_cap}")
    return fails, counts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="patch-manifest-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default="../xr-core",
                    help="xr-core checkout (default: ../xr-core)")
    a = ap.parse_args(argv)
    xr_core = Path(a.xr_core).resolve()
    manifest = xr_core / MANIFEST
    if not manifest.is_file():
        print(f"FAIL: {manifest} not found")
        return EXIT_FAIL

    fails, counts = check(manifest)
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: patch_manifest_check (patches: {counts.get('patches')}, "
              f"files: {counts.get('files')}; {len(fails)} finding(s))")
        return EXIT_FAIL
    print(f"PASS: patch_manifest_check (patches: {counts['patches']}, "
          f"files: {counts['files']}, categories: {counts['categories']})")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
