"""fsdiff.py — real filesystem diff (P4-T5).

The Plan's ephemeral claim is "zero bytes on disk". The only honest way to
show that is to hash every path before and after and diff the manifests
(L5: an assertion without a measurement is not evidence).

Deliberately dumb: `snapshot()` walks a tree and records sha256 + size per
relative path; `diff()` compares two snapshots. No heuristics, no ignore
lists — a caller that wants to exclude something filters the manifest, and
the exclusion is then visible in the output rather than hidden in a matcher.

Used by `probe_driver.py` around an ephemeral-identity create/use/destroy
cycle; until the farm exists it is exercised against synthetic trees by
build/spike/tests/test_fsdiff.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

Snapshot = dict[str, dict[str, int | str]]
Diff = dict[str, list[str]]


def snapshot(root: Path) -> Snapshot:
    """Hash every regular file under `root`. Symlinks are recorded, not followed."""
    out: Snapshot = {}
    root = Path(root)
    if not root.exists():
        return out
    if root.is_file():
        out[root.name] = _entry(root)
        return out
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            out[str(p.relative_to(root))] = {"link": str(p.readlink())}
        elif p.is_file():
            out[str(p.relative_to(root))] = _entry(p)
    return out


def _entry(p: Path) -> dict[str, int | str]:
    data = p.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def diff(before: Snapshot, after: Snapshot) -> Diff:
    """Added / removed / changed paths. Ordering is deterministic (sorted)."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def is_empty(d: Diff) -> bool:
    return not (d["added"] or d["removed"] or d["changed"])


def write_json(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def read_json(path: Path) -> Snapshot:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(prog="fsdiff", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="hash a tree -> JSON manifest")
    s.add_argument("root")
    s.add_argument("--out", required=True)
    d = sub.add_parser("diff", help="diff two manifests; exit 1 if they differ")
    d.add_argument("before")
    d.add_argument("after")
    args = ap.parse_args()

    if args.cmd == "snapshot":
        snap = snapshot(Path(args.root))
        write_json(Path(args.out), snap)
        print(f"{len(snap)} path(s) hashed -> {args.out}")
        return 0
    before, after = read_json(Path(args.before)), read_json(Path(args.after))
    d2 = diff(before, after)
    print(json.dumps(d2, indent=2))
    if is_empty(d2):
        print("NO DIFF — zero residual (measured, not asserted)")
        return 0
    print(f"DIFF: {len(d2['added'])} added, {len(d2['removed'])} removed, "
          f"{len(d2['changed'])} changed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
