#!/usr/bin/env python3
"""tools/permission_write_path_check.py — the P15 write-path law (T9.2).

The permission overlay store is mutated ONLY by the permissions core's
operations (xr-core/permissions/core/ops.cc, ADR-0051). A call to one of those
mutators anywhere else in xr-core is a second write path, and a second write
path is how a grant appears without a ledger row. The rule is therefore:
  * no product source outside xr-core/permissions/ may CALL a mutator; and
  * no product source outside xr-core/permissions/ may INCLUDE the ops header.
Tests and the bench under permissions/ are exempt: they are the proof, not
the product. The renderer, the WebUI and Blink-side code are product, so a
planted call there is RED.

P15-CLOSE C2 adds the CLOCK-FREE row: the core under
xr-core/permissions/core/ must never read a clock. Time enters the core only as
a parameter; permissions/host/permissions_host.cc owns the one clock read. A
clock include or call in permissions/core/** is RED ("clock read inside core").

Mechanically: a stdlib scan of xr-core's C++ and TS/JS sources. --root DIR
scans a fixture tree instead (the negative case plants a renderer-side call and
must redden; a gate that cannot fail certifies nothing).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO.parent  # the sibling xr-core checkout lives next to xr-browser

# The mutators of the overlay store (xr-core/permissions/core/ops.h).
MUTATORS = ("SetDefault", "GrantTemp", "SetDenied", "ConsumeOnce",
            "SweepExpired", "RevokeSite", "RevokeAll")
CALL_RE = re.compile(r"\b(" + "|".join(MUTATORS) + r")\s*\(")
INCLUDE_RE = re.compile(r'#\s*include\s+"permissions/core/ops\.h"')
SUFFIXES = (".cc", ".h", ".mm", ".ts", ".js")
EXEMPT_PREFIX = "permissions/"          # the core, its tests and bench
PRUNE = {".git", "build", "out", "node_modules", "__pycache__"}
CLOCK_CORE = "permissions/core/"
# Includes and calls that read time (std::chrono clocks, libc time, POSIX).
CLOCK_RE = re.compile(
    r"#\s*include\s*<(chrono|ctime|time\.h|sys/time\.h)>"
    r"|\b(system_clock|steady_clock|high_resolution_clock|utc_clock|file_clock)\b"
    r"|\b(time|clock|gettimeofday|clock_gettime|localtime|gmtime|ftime)\s*\(")


def clock_rows(path: Path, rel: str) -> list[str]:
    """The clock-free row: any clock include/call in permissions/core/**."""
    out: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return [f"{rel}: unreadable ({e})"]
    for i, line in enumerate(lines, 1):
        code = line.split("//", 1)[0]
        if CLOCK_RE.search(code):
            out.append(f"{rel}:{i} clock read inside core (the host owns the clock): "
                       f"{line.strip()[:72]}")
    return out


def scan(core: Path) -> tuple[int, list[str]]:
    fails: list[str] = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(core):
        dirnames[:] = [d for d in dirnames if d not in PRUNE]
        for name in filenames:
            if not name.endswith(SUFFIXES):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(core).as_posix()
            if rel.startswith(CLOCK_CORE):
                fails += clock_rows(path, rel)
            if rel.startswith(EXEMPT_PREFIX):
                continue
            scanned += 1
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as e:  # unreadable product source: fail loud, never skip
                fails.append(f"{rel}: unreadable ({e})")
                continue
            for i, line in enumerate(lines, 1):
                code = line.split("//", 1)[0]  # a comment mention is not a call
                if CALL_RE.search(code):
                    fails.append(f"{rel}:{i} overlay mutator called outside permissions/: "
                                 f"{line.strip()[:72]}")
                if INCLUDE_RE.search(line):
                    fails.append(f"{rel}:{i} includes permissions/core/ops.h outside permissions/: "
                                 f"{line.strip()[:72]}")
    return scanned, fails


def main() -> int:
    ap = argparse.ArgumentParser(prog="permission-write-path",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None,
                    help="directory holding an xr-core/ tree (default: the sibling checkout)")
    a = ap.parse_args()
    root = Path(a.root) if a.root else DEFAULT_ROOT
    core = root / "xr-core"
    if not (core / "permissions" / "core" / "ops.cc").exists():
        print(f"FAIL: {core}/permissions/core/ops.cc missing (the write path has no owner)")
        return 1
    scanned, fails = scan(core)
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: permission-write-path ({len(fails)} second write path(s) "
              f"or core clock read(s))")
        return 1
    print(f"PASS: permission-write-path (overlay mutators confined to xr-core/permissions/; "
          f"permissions/core/ clock-free; {scanned} product source(s) scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
