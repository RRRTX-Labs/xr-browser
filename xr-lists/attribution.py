#!/usr/bin/env python3
"""xr-lists/attribution.py — per-list attribution: enforce the shape law,
embed it into the signed package, emit the human-readable sidecar
(P11-T3).

Attribution lives in THREE bound places (the §arch-3 posture — lists are
DATA, and copyleft data carries redistribution obligations; see
docs/dependencies/easylist-family.yaml and research-log-P11.md R6):

1. the bundle's per-list `attribution` field — REQUIRED by the shield
   core's bundle grammar and INSIDE the digest (xr-core/shield/core/
   bundle.h: "where T3's attribution rides"), so attribution cannot be
   stripped without breaking the binding;
2. the manifest's per-list entry `attribution` field — the frozen
   list-bundle-manifest-v1 schema leaves lists[] entries free-form, so
   the field rides there too (sign.py embeds it), and the host's
   bundle-check BINDS it: a manifest may not claim attribution other
   than the one the pinned bytes carry (`manifest-attribution:<name>`);
3. LICENSE.attribution.txt — the human-readable sidecar in the bundle
   package (this tool's output), one block per list with the list's
   sha256 so the sidecar is byte-bound to the compiled lists.

Shape law (enforced here, documented in xr-lists/README.md):
    "<list name> — © <rightsholders> — <SPDX license expression> — <source>"
four " — "-separated non-empty segments; segment 1 MUST equal the list
name; no segment may contain " — " itself.

Deterministic: no clock, no network. Exit: 0 ok · 1 violation/drift ·
2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bundle_bytes import list_sha  # noqa: E402

SEP = " \u2014 "  # " — " — the attribution shape separator

HEADER = """XR Shield list bundle — attribution sidecar (P11-T3)
====================================================
Lists are DATA (DR-04: copyleft list data is never linked as code). Each
block below is byte-bound to the compiled list via its sha256 (the same
digest the signed manifest pins). The machine-readable attribution rides
in the bundle (per-list `attribution`, inside the bundle digest) and in
the manifest (per-entry `attribution`, bound by the host's bundle-check).
Shape law: "<list name>%s© <rightsholders>%s<SPDX>%s<source>".
""" % (SEP, SEP, SEP)


def validate_attribution(name: str, attribution: str) -> str | None:
    """None when the shape law holds; the violation token otherwise."""
    if not attribution:
        return "empty-attribution"
    parts = attribution.split(SEP)
    if len(parts) != 4:
        return "attribution-shape:not-4-segments"
    if any(not p.strip() for p in parts):
        return "attribution-shape:empty-segment"
    if parts[0].strip() != name:
        return "attribution-shape:name-mismatch"
    return None


def sidecar_text(bundle: dict) -> str:
    blocks = [HEADER]
    for lst in bundle["lists"]:
        blocks.append(
            f"\nList: {lst['name']}\nsha256: {list_sha(lst)}\n"
            f"rules: {len(lst['rules'])}\nAttribution: {lst['attribution']}\n")
    return "".join(blocks)


def check_bundle(bundle: dict) -> list[str]:
    problems = []
    for lst in bundle["lists"]:
        bad = validate_attribution(lst["name"], lst.get("attribution", ""))
        if bad:
            problems.append(f"{lst['name']}: {bad}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(prog="xr-lists/attribution.py")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out-dir", default=None,
                    help="write LICENSE.attribution.txt here")
    ap.add_argument("--check", action="store_true",
                    help="byte-compare the sidecar against out-dir's copy")
    a = ap.parse_args()
    bundle_path = Path(a.bundle)
    if not bundle_path.exists():
        print(f"FAIL: bundle not found: {bundle_path}")
        return 2
    if not a.out_dir:
        print("FAIL: --out-dir is required")
        return 2
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    problems = check_bundle(bundle)
    if problems:
        for p in problems:
            print(f"FAIL: attribution shape law: {p}")
        return 1
    text = sidecar_text(bundle)
    out = Path(a.out_dir) / "LICENSE.attribution.txt"
    if a.check:
        if not out.exists():
            print(f"FAIL: sidecar missing: {out}")
            return 1
        if out.read_text(encoding="utf-8") != text:
            print(f"DRIFT: {out} does not match regeneration — run "
                  "xr-lists/attribution.py")
            return 1
        print(f"PASS: {out.name} byte-identical "
              f"({len(bundle['lists'])} lists, shape law enforced)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(bundle['lists'])} lists, shape law enforced)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
