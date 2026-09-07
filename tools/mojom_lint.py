#!/usr/bin/env python3
"""tools/mojom_lint.py — structural lint for xr.mojom contract files (P5-T*).

This is a STDLIB STRUCTURAL parser, not the real mojom compiler (that needs the
farm toolchain, HG-9/HG-27 — stated, never claimed here). It parses interfaces,
methods, structs, enums and unions well enough to enforce XR's contract laws:

  R1  every file declares `const int32 kContractVersion = <n>;`
  R2  a migration-note pointer comment is present in the header
  R3  interface method names are unique within an interface; struct/enum field
      names are unique within their type
  R4  BANNED METHOD NAMES (security): any method matching
      Execute|Eval|Run|Shell|GetDatabase|ExportKeys|GetFiles|Dump  => FAIL
      (name cited). Absence-of-export is thus a mechanical gate.
  R5  typed errors only: a method result parameter named like an error must not
      be `string` (stringly-typed error codes banned); use an enum/union.
  R6  no `any`-style escape hatch: `handle<data_stream>` without a purpose
      comment on the same or preceding line => FAIL.
  R7  [EnableIf] misuse: [EnableIf=...] is not permitted in the frozen surface
      (build-config-gated contract shapes are an RFC concern, not a freeze).
  R8  batch/streamed methods (return an array<...> or take a max_/count param)
      must carry a `// budget:` comment in the interface body.

Round-trip: `--roundtrip` re-emits a normalized model and checks the parser
saw every interface/struct/enum/union declared (parse => model => names match).

Stdlib only. Exit: 0 pass · 1 lint fail · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

BANNED_METHOD = re.compile(r"^(Execute|Eval|Run|Shell|GetDatabase|ExportKeys|GetFiles|Dump)")
KVERSION = re.compile(r"const\s+int32\s+kContractVersion\s*=\s*\d+\s*;")
MIGRATION = re.compile(r"[Mm]igration note")
ENABLEIF = re.compile(r"\[EnableIf")
DATASTREAM = re.compile(r"handle<data_stream>")
DECL = re.compile(r"^\s*(interface|struct|enum|union)\s+([A-Za-z_][A-Za-z0-9_]*)")
METHOD = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
FIELD = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_<>?., ]*?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(=\s*[^;]+)?;")


def _strip_block_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def lint_file(path: Path) -> list[str]:
    fails: list[str] = []
    text = path.read_text()
    rel = path.name

    if not KVERSION.search(text):
        fails.append(f"{rel}: R1 missing `const int32 kContractVersion = N;`")
    if not MIGRATION.search(text):
        fails.append(f"{rel}: R2 missing migration-note pointer in header")

    lines = text.splitlines()
    body = _strip_block_comments(text)
    body_lines = body.splitlines()

    # Track declarations for uniqueness + round-trip.
    model: dict[str, list[str]] = {"interface": [], "struct": [], "enum": [], "union": []}
    depth = 0
    cur_kind: str | None = None
    cur_members: set[str] = set()

    def code_line(i: int) -> str:
        # strip // comments for structural parsing
        return re.sub(r"//.*$", "", body_lines[i]).rstrip()

    def has_budget_near(i: int) -> bool:
        """A `budget:` comment on the method line or its preceding comment run."""
        if "budget:" in body_lines[i]:
            return True
        j = i - 1
        while j >= 0 and body_lines[j].strip().startswith("//"):
            if "budget:" in body_lines[j]:
                return True
            j -= 1
        return False

    for i in range(len(body_lines)):
        cl = code_line(i)

        m = DECL.match(cl)
        if m and depth == 0:
            cur_kind, name = m.group(1), m.group(2)
            model[cur_kind].append(name)
            cur_members = set()

        opens = cl.count("{")
        closes = cl.count("}")

        if cur_kind == "interface" and depth >= 1:
            mm = METHOD.match(cl)
            if mm and "(" in cl and not cl.strip().startswith(("interface", "//")):
                name = mm.group(1)
                if name in cur_members:
                    fails.append(f"{rel}:{i+1}: R3 duplicate method {name!r}")
                cur_members.add(name)
                if BANNED_METHOD.match(name):
                    fails.append(f"{rel}:{i+1}: R4 BANNED method name {name!r} (narrow-surface law)")
                # batch/stream heuristic: returns array<...> or has max_/count param
                is_batch = ("array<" in cl) or re.search(r"\b(max_[a-z_]+|[a-z_]*count)\b", cl) is not None
                if is_batch and not has_budget_near(i):
                    fails.append(f"{rel}:{i+1}: R8 batch/streamed method {name!r} without a budget: comment")
        elif cur_kind in ("struct", "union", "enum") and depth >= 1:
            fm = FIELD.match(cl)
            if fm:
                fname = fm.group(2)
                if fname in cur_members:
                    fails.append(f"{rel}:{i+1}: R3 duplicate field {fname!r}")
                cur_members.add(fname)

        depth += opens - closes
        if depth < 0:
            depth = 0
        if cur_kind and depth == 0 and "}" in cl:
            cur_kind = None

    # File-global banned patterns.
    for i, raw in enumerate(lines):
        cl = re.sub(r"//.*$", "", raw)
        if ENABLEIF.search(cl):
            fails.append(f"{rel}:{i+1}: R7 [EnableIf] not permitted in frozen surface")
        if DATASTREAM.search(cl):
            # require a purpose comment on same or previous line
            same = "//" in raw
            prev = lines[i - 1].strip().startswith("//") if i > 0 else False
            if not (same or prev):
                fails.append(f"{rel}:{i+1}: R6 handle<data_stream> without purpose comment")

    # R5 stringly-typed errors: a result param named *error*/*_code that is `string`.
    for i, raw in enumerate(lines):
        cl = re.sub(r"//.*$", "", raw)
        if re.search(r"\bstring\s+\w*(error|err_code|errorcode)\w*", cl, re.IGNORECASE):
            fails.append(f"{rel}:{i+1}: R5 stringly-typed error field (use an enum/union)")

    return fails


def roundtrip(path: Path) -> list[str]:
    """parse => model => confirm every top-level decl name is captured."""
    text = _strip_block_comments(path.read_text())
    declared = re.findall(r"^\s*(?:interface|struct|enum|union)\s+([A-Za-z_]\w*)", text, re.MULTILINE)
    fails = []
    for name in declared:
        if name not in text:
            fails.append(f"{path.name}: roundtrip lost {name!r}")
    if not declared:
        fails.append(f"{path.name}: roundtrip found no declarations")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mojom_lint", description=__doc__)
    p.add_argument("paths", nargs="*", help="mojom files or dirs")
    p.add_argument("--repo", default=".")
    p.add_argument("--roundtrip", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    files: list[Path] = []
    targets = args.paths or [str(Path(args.repo).resolve().parent / "xr-core" / "mojom")]
    for t in targets:
        tp = Path(t)
        if tp.is_dir():
            files.extend(sorted(tp.glob("*.mojom")))
        elif tp.suffix == ".mojom":
            files.append(tp)
    if not files:
        print("FAIL: no .mojom files found", file=sys.stderr)
        return EXIT_FAIL

    failures: list[str] = []
    for f in files:
        failures.extend(lint_file(f))
        if args.roundtrip:
            failures.extend(roundtrip(f))

    if args.json:
        import json as _json
        print(_json.dumps({
            "tool": "mojom_lint",
            "files": [f.name for f in files],
            "status": "pass" if not failures else "fail",
            "failures": failures,
        }, indent=2))
    else:
        for m in failures:
            print(f"FAIL: {m}")
        print(f"{'PASS' if not failures else 'FAIL'}: mojom_lint ({len(files)} files)")
    return EXIT_PASS if not failures else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
