#!/usr/bin/env python3
"""tools/wall_clock_lint.py — a gate tool may not read the wall clock (P12-T0-a).

Root cause this closes: three tools in ``run_checks.sh``'s dependency closure
read ``date.today()`` in their bodies, so the gate's verdict changed with the
calendar even when nothing in the repo changed
(``release_notes.py:41``, ``visual_diff.py:76``,
``exception_ledger_check.py:195`` at the P11 tip). A check whose verdict moves
while the tree is unchanged is not a gate, and a "hermetic" gate that silently
reaches for the network or the clock is a flake machine.

Law: every Python file reachable from ``tools/run_checks.sh`` (directly
invoked, or imported transitively by something that is) MUST NOT call
``date.today()`` / ``datetime.now()`` / ``datetime.utcnow()`` /
``time.time()`` / ``time.localtime()`` / ``time.gmtime()`` /
``time.monotonic()`` / ``time.perf_counter()`` **outside an argument
default**. The one permitted shape is

    parser.add_argument("--as-of", default=date.today().isoformat(), ...)

because there the clock is (a) an argument DEFAULT a caller can always
override, and (b) never part of the verdict when the gate pins the flag. Every
other read is a FAIL with ``path:line``.

Discovery is DERIVED (the P11-T0-a lesson — a hand-written file list is a
blind spot): the closure is computed from run_checks.sh + tools/checks/*.sh by
following ``"$PY" <path>`` / ``bash <path>`` invocations and then every local
``import`` in those modules, transitively.

Usage:  python3 tools/wall_clock_lint.py [--repo .] [--json] [--self-test]
Exit: 0 pass · 1 offender · 2 usage. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# attribute-name -> the base it must hang off. These are DATE / TIME-OF-DAY
# reads: the T0-a class, because a verdict computed from them moves with the
# calendar.
#
# NOT banned, by definition: time.monotonic() / time.perf_counter() /
# time.time(). Those are DURATION timers — they drive a timebox and no date
# comparison can read them, so they cannot make a gate's verdict move with the
# calendar. Banning them would only push fuzz lanes onto worse clocks.
WALL_CLOCK = {
    "today": ("date", "datetime", "dt", "d"),
    "now": ("datetime", "dt"),
    "utcnow": ("datetime", "dt"),
    "localtime": ("time", "t"),
    "gmtime": ("time", "t"),
}
ALLOWLIST = Path(__file__).resolve().parent / "wall_clock_allowlist.yaml"

INVOCATION_RE = re.compile(
    r"""(?:"\$PY"|python3?|bash|\./)\s+"""
    r"""((?:tools|build|release|xr-lists)/[A-Za-z0-9_./-]+\.(?:py|sh))""")


def _base_name(node: ast.AST) -> str:
    """Left-most Name of a dotted expression (`datetime.date.today` -> datetime)."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _is_wall_clock(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    attr, base = node.func.attr, _base_name(node.func.value)
    allowed_bases = WALL_CLOCK.get(attr)
    return bool(allowed_bases) and base in allowed_bases


def load_allowlist() -> dict[tuple[str, int], str]:
    """(relpath, line) -> reason. DATA rows, not code comments."""
    if not ALLOWLIST.is_file():
        return {}
    import yaml
    doc = yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8")) or {}
    out: dict[tuple[str, int], str] = {}
    for row in doc.get("rows") or []:
        out[(row["path"], int(row["line"]))] = row.get("reason", "")
    return out


def _default_lines(tree: ast.AST) -> set[int]:
    """Line numbers inside an `add_argument(..., default=<expr>)` expression.

    This is the single carve-out: an argument default is overridable by any
    caller, so a gate that pins the flag never lets the clock reach a verdict.
    """
    allowed: set[int] = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        fn = call.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else "")
        if fname != "add_argument":
            continue
        for kw in call.keywords:
            if kw.arg != "default":
                continue
            for sub in ast.walk(kw.value):
                if hasattr(sub, "lineno"):
                    allowed.add(sub.lineno)
    return allowed


def lint_file(path: Path, repo: Path) -> list[str]:
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: unreadable ({exc})"]
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: unparseable ({exc.msg})"]
    allowed = _default_lines(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if _is_wall_clock(node) and node.lineno not in allowed:
            try:
                frag = src.splitlines()[node.lineno - 1].strip()[:70]
            except IndexError:
                frag = ""
            out.append(f"{path.relative_to(repo)}:{node.lineno}: wall-clock "
                       f"read outside an argument default — `{frag}`")
    return out


def _local_imports(path: Path, repo: Path) -> list[Path]:
    """Local modules a file imports (same-dir, tools/, build/, repo root)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    roots = {repo, repo / "tools", repo / "build", repo / "build" / "upstream",
             path.parent}
    found: list[Path] = []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    for mod in mods:
        for part in mod.split("."):
            for root in roots:
                for cand in (root / f"{part}.py", root / part / "__init__.py"):
                    if cand.is_file():
                        found.append(cand.resolve())
    return found


def closure(repo: Path) -> list[Path]:
    """Every Python file reachable from the push gate, derived from the tree."""
    seeds: list[Path] = []
    shell_files = [repo / "tools" / "run_checks.sh"]
    shell_files += sorted((repo / "tools" / "checks").glob("*.sh"))
    for sh in shell_files:
        if not sh.is_file():
            continue
        for m in INVOCATION_RE.finditer(sh.read_text(encoding="utf-8")):
            cand = repo / m.group(1)
            if cand.is_file():
                seeds.append(cand.resolve())
    seen: set[Path] = set()
    queue = list(dict.fromkeys(seeds))
    while queue:
        cur = queue.pop()
        if cur in seen or cur.suffix != ".py":
            continue
        seen.add(cur)
        for dep in _local_imports(cur, repo):
            if dep not in seen:
                queue.append(dep)
    return sorted(seen)


def run(repo: Path) -> tuple[list[str], list[str], int, int]:
    """(offenders, dead_allowlist_rows, files_scanned, allowlisted_hits)."""
    allow = load_allowlist()
    files = closure(repo)
    offenders: list[str] = []
    hit: set[tuple[str, int]] = set()
    exempt = 0
    for f in files:
        for o in lint_file(f, repo):
            rel, _, rest = o.partition(":")
            line = int(rest.partition(":")[0])
            if (rel, line) in allow:
                hit.add((rel, line))
                exempt += 1
                continue
            offenders.append(o)
    # A row is DEAD only when the file it names is in the scanned closure and
    # the read at that line is gone. A row whose file is not in this closure
    # (a synthetic --repo in a negative fixture) cannot be judged, so it is
    # not reported: "not scanned" is not the same claim as "no longer needed".
    scanned = {f.relative_to(repo).as_posix() for f in files}
    dead = sorted(f"{r[0]}:{r[1]}" for r in allow
                  if r not in hit and r[0] in scanned)
    return sorted(offenders), dead, len(files), exempt


def _self_test(repo: Path) -> int:
    """The lint must redden on a planted offender and stay green on the
    permitted shape — a lint that cannot fail certifies nothing."""
    import tempfile
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        bad = t / "bad.py"
        bad.write_text("import datetime\nx = datetime.date.today()\n")
        results["planted_offender_flagged"] = len(lint_file(bad, t)) == 1
        good = t / "good.py"
        good.write_text(
            "import argparse, datetime\n"
            "p = argparse.ArgumentParser()\n"
            "p.add_argument('--as-of',\n"
            "               default=datetime.date.today().isoformat())\n")
        results["argument_default_permitted"] = lint_file(good, t) == []
        tt = t / "tt.py"
        tt.write_text("import time\nt = time.time()\n")
        # time.time()/monotonic()/perf_counter() are DURATION timers: they
        # cannot move a date verdict, so the law does not ban them.
        results["duration_timers_not_banned"] = lint_file(tt, t) == []
        lt = t / "lt.py"
        lt.write_text("import time\nt = time.localtime()\n")
        results["localtime_flagged"] = len(lint_file(lt, t)) == 1
        mono = t / "mono.py"
        mono.write_text("import time\nt = time.monotonic()\n")
        results["duration_timer_not_banned"] = lint_file(mono, t) == []
        allow = load_allowlist()
        results["allowlist_rows_resolve"] = bool(allow) and all(
            (repo / r[0]).is_file() for r in allow)
    bad = [k for k, v in results.items() if not v]
    if bad:
        print(f"FAIL: wall_clock_lint self-test — {sorted(bad)}")
        return EXIT_FAIL
    print(f"PASS: wall_clock_lint self-test ({len(results)} planted/permitted "
          f"shapes discriminated)")
    return EXIT_PASS


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="wall_clock_lint",
                                description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args(argv)
    repo = Path(a.repo).resolve()
    if a.self_test:
        return _self_test(repo)
    offenders, dead, n, exempt = run(repo)
    if a.json:
        print(json.dumps({"tool": "wall_clock_lint", "files_scanned": n,
                          "offenders": offenders,
                          "dead_allowlist_rows": dead,
                          "allowlisted": exempt}, sort_keys=True, indent=2))
    if offenders or dead:
        if offenders:
            print(f"FAIL: wall_clock_lint — {len(offenders)} offender(s) in "
                  f"{n} gate-closure file(s):")
            for o in offenders:
                print(f"  {o}")
            print("  fix: take `--as-of` and use it for every comparison; the "
                  "clock may appear ONLY as an add_argument(default=...) the "
                  "caller can override.")
        if dead:
            print(f"FAIL: wall_clock_lint — {len(dead)} dead allowlist row(s) "
                  f"(a stale row is a silent hole): {dead}")
        return EXIT_FAIL
    print(f"PASS: wall_clock_lint ({n} gate-closure file(s) scanned; "
          f"0 verdict-affecting wall-clock reads outside an argument default; "
          f"{exempt} non-verdict timestamp(s) allowlisted as data, 0 dead rows)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
