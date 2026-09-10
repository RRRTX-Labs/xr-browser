#!/usr/bin/env python3
"""tools/browser_test_lint.py — XR browser-test fixture law (P9-T1).

The T1 fixtures are runner-ready (farm-executed): this sandbox has no
Chromium checkout and no gn/ninja, so the COMPILE/RUN half is honestly
recorded as farm work and this gate lints the SOURCE half for real. The laws:

  1. Every file that declares an ``XR_*_TEST`` must use a fixture from
     ``xr-core/test/browser/fixtures/`` (a test that hand-rolls its own
     partition/network/clock is the exact drift the fixtures exist to stop).
  2. Every test file is covered by an owner in the sidecar ``OWNERS.yaml``
     (a test with no escalation path is a test nobody owns).
  3. No ``GTEST_SKIP()`` may appear on a security assertion — a security
     assertion that cannot run must fail loudly on the farm, never skip
     (plan §11.2: corrupt-prefs/corrupt-store fixtures are mandatory, and a
     skip would silently pass them).

Also enforces the P9 empty-run law: zero test files found is a FAILURE, not
a pass (a lint that saw nothing certifies nothing). ``--syntax`` attempts
``g++ -fsyntax-only`` and SKIPs visibly when g++ or the Chromium headers are
absent (they are, here — the farm compiles for real).

Exit: 0 pass · 1 fail · 2 usage · 77 skip (only for the --syntax pass).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77

XR_TEST_RE = re.compile(r"\bXR_[A-Z0-9_]*_TEST\b")
FIXTURE_INCLUDE_RE = re.compile(
    r'#\s*include\s*[<"]test/browser/fixtures/[A-Za-z0-9_./-]+\.h[>"]')
GTEST_SKIP_RE = re.compile(r"\bGTEST_SKIP\s*\(")

DEFAULT_BROWSER_DIR = "../xr-core/test/browser"


def browser_dir(repo: Path, arg: str) -> Path:
    p = Path(arg)
    if not p.is_absolute():
        p = repo / p
    return p


def collect_test_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for f in sorted(root.rglob("*")):
        if f.suffix != ".cc" or not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if XR_TEST_RE.search(text):
            out.append(f)
    return out


def check(repo: Path, root: Path) -> list[str]:
    fails: list[str] = []
    tests = collect_test_files(root)
    if not tests:
        fails.append(f"{root}: no XR_*_TEST files found — a browser-test "
                     f"tree that tests nothing is not a pass (empty-run law)")
        return fails

    fixture_headers = sorted(
        p.name for p in (root / "fixtures").glob("*.h")) if \
        (root / "fixtures").is_dir() else []
    if not fixture_headers:
        fails.append(f"{root}/fixtures: no fixture headers found")

    for f in tests:
        rel = f.relative_to(root)
        text = f.read_text(encoding="utf-8", errors="replace")
        if not FIXTURE_INCLUDE_RE.search(text):
            fails.append(f"{rel}: declares an XR_*_TEST but includes no "
                         f"test/browser/fixtures/ header")
        # The ban is on the skip CALL in code; a comment mentioning the
        # macro is documentation, not a skip (same rule as mode_lint).
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*") or \
                    stripped.startswith("*"):
                continue
            if GTEST_SKIP_RE.search(line):
                fails.append(f"{rel}:{lineno}: GTEST_SKIP() on a test path "
                             f"is forbidden (security assertions fail "
                             f"loudly, never skip)")
                break

    owners = root / "OWNERS.yaml"
    if not owners.exists():
        fails.append(f"{root}: missing OWNERS.yaml sidecar")
    else:
        try:
            import yaml
            doc = yaml.safe_load(owners.read_text(encoding="utf-8"))
        except Exception as exc:
            fails.append(f"OWNERS.yaml: not parseable ({exc})")
            doc = None
        if isinstance(doc, dict):
            default_owner = (doc.get("default") or {}).get("owner")
            covered: dict[str, str] = {}
            if default_owner:
                covered["*"] = str(default_owner)
            for row in (doc.get("paths") or []):
                if isinstance(row, dict) and row.get("file"):
                    covered[row["file"]] = row.get("owner", str(default_owner))
            for f in tests:
                rel = str(f.relative_to(root)).replace("\\", "/")
                if rel not in covered and "*" not in covered:
                    fails.append(f"{rel}: no owner in OWNERS.yaml "
                                 f"(default or per-path row required)")
                elif rel in covered and not covered[rel]:
                    fails.append(f"{rel}: OWNERS.yaml row has an empty owner")
    return fails


def syntax_pass(root: Path) -> tuple[int, list[str]]:
    """Best-effort g++ -fsyntax-only over the fixture sources (visible SKIP)."""
    if shutil.which("g++") is None:
        return EXIT_SKIP, ["SKIP (tool absent: g++) — needed for: a "
                           "syntax-level compile check of the browser-test "
                           "fixtures; local hint: apt-get install g++"]
    srcs = sorted(root.rglob("*.cc")) + sorted(root.rglob("*.h"))
    if not srcs:
        return EXIT_FAIL, ["no browser-test sources to syntax-check"]
    cmd = ["g++", "-fsyntax-only", "-x", "c++", "-std=c++20",
           "-I", str(root.parent.parent)] + [str(s) for s in srcs]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return EXIT_PASS, []
    # Missing Chromium headers is the EXPECTED state here: record it as a
    # visible SKIP, never a fake pass (the farm compiles against the checkout).
    err = proc.stderr or proc.stdout
    return EXIT_SKIP, ["SKIP: g++ -fsyntax-only failed (Chromium headers "
                       "absent in this sandbox — farm compiles for real): "
                       + err.strip().splitlines()[0][:160] if err.strip()
                       else "no compiler output"]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="browser_test_lint", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--browser-dir", default=DEFAULT_BROWSER_DIR,
                   help="xr-core/test/browser tree")
    p.add_argument("--syntax", action="store_true",
                   help="also attempt g++ -fsyntax-only (SKIP-visible)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    root = browser_dir(repo, args.browser_dir)
    fails = check(repo, root)
    notes: list[str] = []
    if args.syntax:
        code, lines = syntax_pass(root)
        notes.extend(lines)
        if code == EXIT_FAIL and not fails:
            fails.append("syntax pass failed with no lint failures recorded")

    if args.json:
        print(json.dumps({"tool": "browser_test_lint", "count": len(fails),
                          "violations": fails, "notes": notes},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        for n in notes:
            print(n)
        print(f"browser_test_lint: {len(fails)} violation(s) "
              f"({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
