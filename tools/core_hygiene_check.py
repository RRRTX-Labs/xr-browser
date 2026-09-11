#!/usr/bin/env python3
"""tools/core_hygiene_check.py — the std-only import law for xr-core cores.

Law: every ``xr-core/<x>/core/**`` translation unit compiles OFF-TREE with a
bare g++/make — which is only honest if it really includes nothing but the
C++ standard library and its own siblings. This gate proves it:

  * ``#include <...>`` must name a header on the std/libc allowlist below
    (unknown angle includes FAIL — the allowlist is closed, not open);
  * ``#include "..."`` must resolve to a file inside the SAME core root
    (cross-core and absolute quoted includes FAIL);
  * any include path mentioning chromium/chrome/base\\/third_party/components
    FAILS (the failure condition: a core that grew a Chromium dependency).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ANGLE_ALLOW = {
    # C++ standard library
    "algorithm", "any", "array", "atomic", "bitset", "cassert", "cctype",
    "cerrno", "cfenv", "cfloat", "charconv", "chrono", "cinttypes",
    "climits", "clocale", "cmath", "codecvt", "compare", "complex",
    "concepts", "condition_variable", "coroutine", "csetjmp", "csignal",
    "cstdarg", "cstddef", "cstdint", "cstdio", "cstdlib", "cstring",
    "ctime", "cuchar", "cwchar", "cwctype", "deque", "exception",
    "execution", "filesystem", "flat_map", "flat_set", "forward_list",
    "fstream", "functional", "future", "initializer_list", "iomanip",
    "ios", "iosfwd", "iostream", "istream", "iterator", "limits", "list",
    "locale", "map", "memory", "memory_resource", "mutex", "new",
    "numbers", "numeric", "optional", "ostream", "print", "queue",
    "random", "ranges", "ratio", "regex", "scoped_allocator",
    "semaphore", "set", "shared_mutex", "source_location", "span",
    "spanstream", "sstream", "stack", "stacktrace", "stdexcept",
    "stdfloat", "stop_token", "streambuf", "string", "string_view",
    "strstream", "syncstream", "system_error", "thread", "tuple",
    "typeindex", "typeinfo", "type_traits", "unordered_map",
    "unordered_set", "utility", "valarray", "variant", "vector",
    "version",
    # libc (the cores are allowed the C library too)
    "assert.h", "ctype.h", "errno.h", "fenv.h", "float.h", "inttypes.h",
    "limits.h", "locale.h", "math.h", "setjmp.h", "signal.h",
    "stdarg.h", "stddef.h", "stdint.h", "stdio.h", "stdlib.h",
    "string.h", "time.h", "uchar.h", "wchar.h", "wctype.h",
    # POSIX surface the hosts/cores may rely on (documented in each core)
    "fcntl.h", "unistd.h", "sys/stat.h", "sys/types.h", "sys/wait.h",
    "sys/time.h", "sys/resource.h",
}

ANGLE_RE = re.compile(r'^\s*#\s*include\s*<([^>]+)>')
QUOTED_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
FORBIDDEN_RE = re.compile(r"(^|/|\b)(chromium|chrome|third_party|components)(/|\b)")


def check_core(core_root: Path, core_name: str) -> list[str]:
    fails: list[str] = []
    for path in sorted(list(core_root.rglob("*.cc")) + list(core_root.rglob("*.h"))):
        rel = path.relative_to(core_root.parent)
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1):
            m = ANGLE_RE.match(line)
            if m:
                name = m.group(1).strip()
                if name not in ANGLE_ALLOW:
                    fails.append(f"{rel}:{lineno}: angle include <{name}> is "
                                 "not on the std/libc allowlist")
                if FORBIDDEN_RE.search(name):
                    fails.append(f"{rel}:{lineno}: Chromium include <{name}> "
                                 "in std-only core")
                continue
            m = QUOTED_RE.match(line)
            if m:
                name = m.group(1).strip()
                if FORBIDDEN_RE.search(name):
                    fails.append(f"{rel}:{lineno}: Chromium-style include "
                                 f'"{name}" in std-only core')
                    continue
                target = (path.parent / name).resolve()
                try:
                    target.relative_to(core_root.resolve())
                except ValueError:
                    fails.append(f"{rel}:{lineno}: quoted include \"{name}\" "
                                 f"escapes {core_name}/core (cross-core "
                                 "coupling is a design decision, not an "
                                 "accident)")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(prog="core-hygiene-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default="../xr-core")
    a = ap.parse_args()
    root = Path(a.xr_core).resolve()
    if not root.is_dir():
        print(f"FAIL: xr-core not found: {root}")
        return 1
    cores = sorted(d for d in root.iterdir()
                   if (d / "core").is_dir() and (d / "tests").is_dir())
    if not cores:
        print("FAIL: no cores discovered (a hygiene gate over zero cores "
              "certifies nothing)")
        return 1
    all_fails: list[str] = []
    checked = 0
    for c in cores:
        fails = check_core(c / "core", c.name)
        n = len(list((c / "core").rglob("*.cc"))) + \
            len(list((c / "core").rglob("*.h")))
        checked += n
        if fails:
            all_fails.extend(fails)
    if all_fails:
        for f in all_fails[:20]:
            print(f"FAIL: {f}")
        print(f"FAIL: core-hygiene ({len(all_fails)} violation(s) across "
              f"{checked} files in {len(cores)} cores)")
        return 1
    print(f"PASS: core-hygiene ({checked} files across {len(cores)} cores: "
          f"{', '.join(c.name for c in cores)}; std/libc includes only, "
          "no Chromium, no cross-core escapes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
